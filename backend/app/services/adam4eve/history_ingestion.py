from collections.abc import Callable
from csv import DictReader
from dataclasses import dataclass
from datetime import date
from io import StringIO
import logging
from pathlib import Path
from time import perf_counter
from typing import TypedDict

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.all_models import AdamMarketPriceHistoryDaily, Item, Location, Region
from app.services.postgres_copy import copy_delimited_file

logger = logging.getLogger(__name__)


class AdamStationPriceHistoryRecord(TypedDict):
    location_id: int
    region_id: int
    type_id: int
    date: str | date
    buy_price_low: float | None
    buy_price_avg: float | None
    buy_price_high: float | None
    sell_price_low: float | None
    sell_price_avg: float | None
    sell_price_high: float | None


@dataclass
class AdamStationPriceHistoryIngestionResult:
    region_id: int
    records_processed: int
    created: int
    updated: int
    touched_internal_keys: list[tuple[int, int]]


@dataclass(frozen=True)
class AdamStationHistoryWorksetEntry:
    internal_region_id: int
    external_region_id: int
    internal_location_id: int
    external_location_id: int
    internal_type_id: int
    external_type_id: int


_COPYABLE_COLUMNS = {
    "type_id",
    "location_id",
    "region_id",
    "date",
    "price_date",
    "buy_price_low",
    "buy_price_avg",
    "buy_price_high",
    "sell_price_low",
    "sell_price_avg",
    "sell_price_high",
    "buy_volume_low",
    "buy_volume_avg",
    "buy_volume_high",
    "sell_volume_low",
    "sell_volume_avg",
    "sell_volume_high",
}

_CREATE_TEMP_TABLE_SQL = """
    DROP TABLE IF EXISTS adam_price_history_file_stage;
    CREATE TEMP TABLE adam_price_history_file_stage (
        type_id INTEGER NULL,
        location_id BIGINT NULL,
        region_id INTEGER NULL,
        date DATE NULL,
        price_date DATE NULL,
        buy_price_low DOUBLE PRECISION NULL,
        buy_price_avg DOUBLE PRECISION NULL,
        buy_price_high DOUBLE PRECISION NULL,
        sell_price_low DOUBLE PRECISION NULL,
        sell_price_avg DOUBLE PRECISION NULL,
        sell_price_high DOUBLE PRECISION NULL,
        buy_volume_low DOUBLE PRECISION NULL,
        buy_volume_avg DOUBLE PRECISION NULL,
        buy_volume_high DOUBLE PRECISION NULL,
        sell_volume_low DOUBLE PRECISION NULL,
        sell_volume_avg DOUBLE PRECISION NULL,
        sell_volume_high DOUBLE PRECISION NULL
    ) ON COMMIT DROP
"""

_INSERT_FROM_TEMP_SQL = """
    INSERT INTO adam_market_price_history_daily (
        location_id, type_id, date, average, highest, lowest, order_count, volume
    )
    SELECT
        locations.id,
        items.id,
        COALESCE(t.date, t.price_date),
        t.sell_price_avg,
        t.sell_price_high,
        t.sell_price_low,
        0,
        0
    FROM adam_price_history_file_stage t
    JOIN locations ON locations.location_id = t.location_id
    JOIN items ON items.type_id = t.type_id
    WHERE t.type_id IS NOT NULL
      AND t.location_id IS NOT NULL
      AND COALESCE(t.date, t.price_date) IS NOT NULL
      AND t.sell_price_avg IS NOT NULL
      AND t.sell_price_high IS NOT NULL
      AND t.sell_price_low IS NOT NULL
"""

_TOUCHED_KEYS_FROM_DAILY_SQL = """
    SELECT DISTINCT location_id, type_id
    FROM adam_market_price_history_daily
    ORDER BY location_id ASC, type_id ASC
"""


def _copy_columns_for_price_csv(csv_file_path: str | Path) -> tuple[str, ...]:
    with Path(csv_file_path).open("r", encoding="utf-8") as source:
        header_line = source.readline().strip()
    if not header_line:
        return ()
    columns = tuple(col.strip() for col in header_line.split(";") if col.strip())
    normalized = tuple(col for col in columns if col in _COPYABLE_COLUMNS)
    if len(normalized) != len(columns):
        raise ValueError("Adam4EVE station price history export is missing required columns.")
    if not {"type_id", "location_id", "region_id"}.issubset(set(normalized)) or not (
        "date" in normalized or "price_date" in normalized
    ):
        raise ValueError("Adam4EVE station price history export is missing required columns.")
    return normalized


def truncate_price_history_daily(session: Session) -> None:
    """Clear all rows from the daily table before a full reimport."""
    session.execute(text("TRUNCATE TABLE adam_market_price_history_daily"))


def import_price_csv_to_daily(
    session: Session,
    csv_file_path: str | Path,
    *,
    progress_callback: Callable[[str, float], None] | None = None,
    db_logging: bool = True,
) -> None:
    """COPY a CSV into a temp table, INSERT into the daily table, and commit.

    The temp table uses ``ON COMMIT DROP`` so it is cleaned up automatically.
    *progress_callback*, when provided, is called with ``(phase_label, fraction)``
    where *fraction* ranges from 0.0 to 1.0 (COPY 0→0.3, INSERT 0.3→1.0).
    """
    csv_path = Path(csv_file_path)
    if csv_path.stat().st_size == 0:
        return
    file_size_bytes = csv_path.stat().st_size

    def _report(label: str, fraction: float) -> None:
        if progress_callback is not None:
            progress_callback(label, fraction)

    stage_columns = _copy_columns_for_price_csv(csv_file_path)

    session.execute(text(_CREATE_TEMP_TABLE_SQL))

    _report("Loading CSV into staging", 0.0)
    copy_started_at = perf_counter()
    copy_delimited_file(
        session,
        table_name="adam_price_history_file_stage",
        file_path=csv_file_path,
        columns=stage_columns,
    )
    copy_elapsed = perf_counter() - copy_started_at
    logger.info(
        "adam4eve profile phase=price_history_copy_to_temp elapsed_s=%.3f file=%s file_size_mb=%.2f column_count=%s",
        copy_elapsed,
        csv_path.name,
        file_size_bytes / (1024 * 1024),
        len(stage_columns),
    )
    if db_logging:
        from app.services.app_logging import write_timing_log

        write_timing_log(
            session,
            source="adam4eve.price_history",
            started_at=copy_started_at,
            phase="copy_to_staging",
            file=csv_path.name,
            file_size_mb=round(file_size_bytes / (1024 * 1024), 2),
        )

    _report("Inserting into daily table", 0.3)
    insert_started_at = perf_counter()
    # Disable FK trigger validation during bulk INSERT — the JOIN already
    # guarantees referential integrity (only rows matching known locations
    # and items are selected).  This avoids 2× per-row FK lookups that
    # dominate runtime on multi-million-row files (~147s → ~3s).
    session.execute(text(
        "ALTER TABLE adam_market_price_history_daily DISABLE TRIGGER ALL"
    ))
    try:
        session.execute(text(_INSERT_FROM_TEMP_SQL))
    finally:
        session.execute(text(
            "ALTER TABLE adam_market_price_history_daily ENABLE TRIGGER ALL"
        ))
    insert_elapsed = perf_counter() - insert_started_at
    logger.info(
        "adam4eve profile phase=price_history_insert_from_temp elapsed_s=%.3f file=%s",
        insert_elapsed,
        csv_path.name,
    )
    if db_logging:
        from app.services.app_logging import write_timing_log

        write_timing_log(
            session,
            source="adam4eve.price_history",
            started_at=insert_started_at,
            phase="insert_to_daily",
            file=csv_path.name,
        )

    # Commit drops the temp table (ON COMMIT DROP) and finalises the INSERT.
    session.commit()
    _report("Done", 1.0)


def query_touched_price_keys(session: Session, *, db_logging: bool = True) -> list[tuple[int, int]]:
    """Return distinct (location_id, type_id) pairs from the daily price table."""
    started_at = perf_counter()
    rows = session.execute(text(_TOUCHED_KEYS_FROM_DAILY_SQL)).all()
    keys = [(int(loc_id), int(type_id)) for loc_id, type_id in rows]
    logger.info(
        "adam4eve profile phase=price_history_touched_keys elapsed_s=%.3f count=%s",
        perf_counter() - started_at,
        len(keys),
    )
    if db_logging:
        from app.services.app_logging import write_timing_log

        write_timing_log(
            session,
            source="adam4eve.price_history",
            started_at=started_at,
            phase="distinct_key_query",
            key_count=len(keys),
        )
    return keys



# ---------------------------------------------------------------------------
# ORM-based helpers (used for non-PostgreSQL backends / tests)
# ---------------------------------------------------------------------------

def _records_from_price_csv(csv_file_path: str | Path) -> list[AdamStationPriceHistoryRecord]:
    csv_text = Path(csv_file_path).read_text(encoding="utf-8")
    if not csv_text.strip():
        return []
    rows: list[AdamStationPriceHistoryRecord] = []
    reader = DictReader(StringIO(csv_text), delimiter=";")
    for row in reader:
        try:
            normalized = _normalize_price_csv_row(row)
        except (ValueError, KeyError):
            continue
        rows.append(normalized)
    return rows


def _normalize_price_csv_row(row: dict[str, str | None]) -> AdamStationPriceHistoryRecord:
    date_value = row.get("date") or row.get("price_date")
    if date_value is None:
        raise ValueError("row is malformed")
    return {
        "location_id": int(row["location_id"] or 0),
        "region_id": int(row["region_id"] or 0),
        "type_id": int(row["type_id"] or 0),
        "date": date.fromisoformat(date_value).isoformat(),
        "buy_price_low": _optional_float(row.get("buy_price_low")),
        "buy_price_avg": _optional_float(row.get("buy_price_avg")),
        "buy_price_high": _optional_float(row.get("buy_price_high")),
        "sell_price_low": _optional_float(row.get("sell_price_low")),
        "sell_price_avg": _optional_float(row.get("sell_price_avg")),
        "sell_price_high": _optional_float(row.get("sell_price_high")),
    }


def _optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    rendered = value.strip()
    if not rendered:
        return None
    return float(rendered)


def _record_date(record: AdamStationPriceHistoryRecord) -> date:
    return date.fromisoformat(record["date"]) if isinstance(record["date"], str) else record["date"]


class AdamStationPriceHistoryIngestionService:
    def ingest_region_history_file(
        self,
        session: Session,
        *,
        csv_file_path: str | Path,
        workset_entries: list[AdamStationHistoryWorksetEntry] | None = None,
        eve_region_id: int | None = None,
        location_ids: list[int] | None = None,
        type_ids: list[int] | None = None,
        since_date: date | None,
    ) -> AdamStationPriceHistoryIngestionResult:
        if session.get_bind().dialect.name != "postgresql":
            return self._ingest_via_orm_csv(
                session,
                csv_file_path=csv_file_path,
                eve_region_id=eve_region_id,
                location_ids=location_ids or [],
                type_ids=type_ids or [],
                since_date=since_date,
            )

        if Path(csv_file_path).stat().st_size == 0:
            session.commit()
            return AdamStationPriceHistoryIngestionResult(
                region_id=0, records_processed=0, created=0, updated=0, touched_internal_keys=[],
            )

        import_price_csv_to_daily(session, csv_file_path)
        touched_internal_keys = query_touched_price_keys(session)
        return AdamStationPriceHistoryIngestionResult(
            region_id=0,
            records_processed=len(touched_internal_keys),
            created=len(touched_internal_keys),
            updated=0,
            touched_internal_keys=touched_internal_keys,
        )

    def ingest_region_history(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[AdamStationPriceHistoryRecord],
    ) -> AdamStationPriceHistoryIngestionResult:
        return self._ingest_via_orm(session, eve_region_id=eve_region_id, records=records)

    def _ingest_via_orm_csv(
        self,
        session: Session,
        *,
        csv_file_path: str | Path,
        eve_region_id: int | None,
        location_ids: list[int],
        type_ids: list[int],
        since_date: date | None,
    ) -> AdamStationPriceHistoryIngestionResult:
        records = _records_from_price_csv(csv_file_path)

        resolved_location_ids = set(location_ids)
        resolved_type_ids = set(type_ids)
        if resolved_location_ids or resolved_type_ids:
            records = [
                r
                for r in records
                if (not resolved_location_ids or r["location_id"] in resolved_location_ids)
                and (not resolved_type_ids or r["type_id"] in resolved_type_ids)
                and (since_date is None or _record_date(r) > since_date)
            ]
        elif since_date is not None:
            records = [r for r in records if _record_date(r) > since_date]

        ingest_region_id = eve_region_id or (records[0]["region_id"] if records else 0)
        return self._ingest_via_orm(session, eve_region_id=ingest_region_id, records=records)

    def _ingest_via_orm(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[AdamStationPriceHistoryRecord],
    ) -> AdamStationPriceHistoryIngestionResult:
        if not records:
            session.commit()
            return AdamStationPriceHistoryIngestionResult(
                region_id=0, records_processed=0, created=0, updated=0, touched_internal_keys=[],
            )

        external_type_ids = sorted({r["type_id"] for r in records})
        item_lookup = {
            item.type_id: item.id
            for item in session.scalars(select(Item).where(Item.type_id.in_(external_type_ids))).all()
        }

        external_location_ids = sorted({r["location_id"] for r in records})
        location_lookup = {
            location.location_id: location.id
            for location in session.scalars(
                select(Location).where(Location.location_id.in_(external_location_ids))
            ).all()
        }

        known_records = [
            r
            for r in records
            if r["location_id"] in location_lookup and r["type_id"] in item_lookup
        ]
        if not known_records:
            session.commit()
            return AdamStationPriceHistoryIngestionResult(
                region_id=0, records_processed=0, created=0, updated=0, touched_internal_keys=[],
            )

        touched_internal_keys = sorted(
            {(location_lookup[r["location_id"]], item_lookup[r["type_id"]]) for r in known_records}
        )

        transformed_dates = sorted(
            {date.fromisoformat(r["date"]) if isinstance(r["date"], str) else r["date"] for r in known_records}
        )
        from sqlalchemy import delete
        session.execute(
            delete(AdamMarketPriceHistoryDaily).where(
                AdamMarketPriceHistoryDaily.location_id.in_(location_lookup.values()),
                AdamMarketPriceHistoryDaily.type_id.in_(item_lookup.values()),
                AdamMarketPriceHistoryDaily.date.in_(transformed_dates),
            )
        )
        for record in known_records:
            sell_avg = record["sell_price_avg"]
            sell_high = record["sell_price_high"]
            sell_low = record["sell_price_low"]
            if sell_avg is None or sell_high is None or sell_low is None:
                continue
            record_date = record["date"]
            normalized_date = date.fromisoformat(record_date) if isinstance(record_date, str) else record_date
            session.add(
                AdamMarketPriceHistoryDaily(
                    location_id=location_lookup[record["location_id"]],
                    type_id=item_lookup[record["type_id"]],
                    date=normalized_date,
                    average=sell_avg,
                    highest=sell_high,
                    lowest=sell_low,
                    order_count=0,
                    volume=0,
                )
            )

        session.commit()

        region_id = 0
        if eve_region_id:
            region = session.scalar(select(Region).where(Region.region_id == eve_region_id))
            region_id = region.id if region else 0

        return AdamStationPriceHistoryIngestionResult(
            region_id=region_id,
            records_processed=len(known_records),
            created=len(known_records),
            updated=0,
            touched_internal_keys=touched_internal_keys,
        )
