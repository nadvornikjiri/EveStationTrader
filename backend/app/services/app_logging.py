"""Structured application logging to the database."""

from __future__ import annotations

import logging
from time import perf_counter

from sqlalchemy.orm import Session

from app.models.all_models import AppLogEntry

logger = logging.getLogger(__name__)


def write_log(
    session: Session,
    *,
    source: str,
    message: str,
    level: str = "DEBUG",
    commit: bool = False,
) -> AppLogEntry:
    """Write a log entry to the database and mirror to Python logging."""
    entry = AppLogEntry(
        log_level=level,
        source=source,
        message=message,
    )
    session.add(entry)
    session.flush()
    if commit:
        session.commit()

    py_level = getattr(logging, level.upper(), logging.DEBUG)
    logger.log(py_level, "%s | %s", source, message)

    return entry


def write_timing_log(
    session: Session,
    *,
    source: str,
    started_at: float,
    commit: bool = False,
    **context: object,
) -> AppLogEntry:
    """Write a timing log entry at DEBUG level.

    Computes elapsed_s from *started_at* (a ``perf_counter()`` value) and
    formats all *context* key-value pairs into the message string.

    Example message::

        phase=copy_to_staging elapsed_s=2.341 file=export.csv file_size_mb=47.21
    """
    elapsed = perf_counter() - started_at
    parts = [f"elapsed_s={elapsed:.3f}"]
    for key, value in context.items():
        parts.append(f"{key}={value}")
    message = " ".join(parts)

    return write_log(
        session,
        source=source,
        message=message,
        level="DEBUG",
        commit=commit,
    )


def purge_old_entries(session: Session, *, max_age_days: int = 30) -> int:
    """Delete log entries older than *max_age_days*. Returns count deleted."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete

    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    result = session.execute(
        delete(AppLogEntry).where(AppLogEntry.created_at < cutoff)
    )
    session.commit()
    return result.rowcount  # type: ignore[return-value]
