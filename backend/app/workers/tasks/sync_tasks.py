import logging
from datetime import UTC, datetime

from apscheduler.schedulers.base import BaseScheduler  # type: ignore[import-untyped]
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.all_models import JobScheduleConfig
from app.services.sync.service import SyncService

logger = logging.getLogger(__name__)

# Track last-seen updated_at per job so we can detect config changes.
_last_config_versions: dict[str, datetime] = {}


def heartbeat_job() -> None:
    logger.info("worker heartbeat at %s", datetime.now(UTC).isoformat())


def sync_esi_market_orders_job() -> None:
    result = SyncService().trigger_job("esi_market_orders_sync")
    logger.info(
        "esi market orders sync completed: job_id=%s status=%s records=%s",
        result.id,
        result.status,
        result.records_processed,
    )


def sync_everef_history_job() -> None:
    result = SyncService().trigger_job("everef_history_sync")
    logger.info(
        "everef history sync completed: job_id=%s status=%s records=%s",
        result.id,
        result.status,
        result.records_processed,
    )


def sync_adam4eve_job() -> None:
    result = SyncService().trigger_job("adam4eve_sync")
    logger.info(
        "adam4eve sync completed: job_id=%s status=%s records=%s",
        result.id,
        result.status,
        result.records_processed,
    )


def sync_characters_job() -> None:
    result = SyncService().trigger_job("character_sync")
    logger.info(
        "character sync completed: job_id=%s status=%s records=%s",
        result.id,
        result.status,
        result.records_processed,
    )


def opportunity_rebuild_job() -> None:
    result = SyncService().trigger_job("opportunity_rebuild")
    logger.info(
        "opportunity rebuild completed: job_id=%s status=%s records=%s",
        result.id,
        result.status,
        result.records_processed,
    )


# Map job_type -> callable
JOB_FUNCTIONS: dict[str, object] = {
    "esi_market_orders_sync": sync_esi_market_orders_job,
    "everef_history_sync": sync_everef_history_job,
    "adam4eve_sync": sync_adam4eve_job,
    "character_sync": sync_characters_job,
    "opportunity_rebuild": opportunity_rebuild_job,
}

# Hardcoded fallback defaults used when no DB row exists.
_FALLBACK_CONFIGS: dict[str, dict[str, object]] = {
    "esi_market_orders_sync": {"trigger": "interval", "minutes": 10},
    "everef_history_sync": {"trigger": "cron", "hour": 8, "minute": 0},
    "adam4eve_sync": {"trigger": "cron", "hour": 9, "minute": 0},
    "character_sync": {"trigger": "interval", "minutes": 15},
    "opportunity_rebuild": {"trigger": "interval", "minutes": 60},
}


def _apply_schedule(scheduler: BaseScheduler, config: JobScheduleConfig) -> None:
    """Add or reschedule a single job based on its DB config."""
    func = JOB_FUNCTIONS.get(config.job_type)
    if func is None:
        logger.warning("No function registered for job_type=%s, skipping", config.job_type)
        return

    if not config.enabled:
        # Remove the job if it exists
        try:
            scheduler.remove_job(config.job_type)
            logger.info("Disabled job %s removed from scheduler", config.job_type)
        except Exception:
            pass
        return

    if config.trigger_type == "interval" and config.interval_minutes:
        scheduler.add_job(
            func,
            "interval",
            minutes=config.interval_minutes,
            id=config.job_type,
            replace_existing=True,
        )
        logger.info("Scheduled %s: interval every %d min", config.job_type, config.interval_minutes)
    elif config.trigger_type == "cron" and config.cron_hour is not None:
        scheduler.add_job(
            func,
            "cron",
            hour=config.cron_hour,
            minute=config.cron_minute or 0,
            id=config.job_type,
            replace_existing=True,
        )
        logger.info(
            "Scheduled %s: cron at %02d:%02d UTC",
            config.job_type,
            config.cron_hour,
            config.cron_minute or 0,
        )
    else:
        logger.warning(
            "Invalid schedule config for %s (trigger=%s, interval=%s, hour=%s)",
            config.job_type,
            config.trigger_type,
            config.interval_minutes,
            config.cron_hour,
        )


def _load_and_apply_configs(scheduler: BaseScheduler) -> None:
    """Read all schedule configs from DB and apply them to the scheduler."""
    session = SessionLocal()
    try:
        rows = session.scalars(select(JobScheduleConfig)).all()
        for row in rows:
            _apply_schedule(scheduler, row)
            _last_config_versions[row.job_type] = row.updated_at
    except Exception:
        logger.exception("Failed to load schedule configs from DB, using fallback defaults")
        _apply_fallback_configs(scheduler)
    finally:
        session.close()


def _apply_fallback_configs(scheduler: BaseScheduler) -> None:
    """Apply hardcoded defaults when DB is unavailable."""
    for job_type, cfg in _FALLBACK_CONFIGS.items():
        func = JOB_FUNCTIONS.get(job_type)
        if func is None:
            continue
        if cfg["trigger"] == "interval":
            scheduler.add_job(
                func,
                "interval",
                minutes=cfg["minutes"],
                id=job_type,
                replace_existing=True,
            )
        elif cfg["trigger"] == "cron":
            scheduler.add_job(
                func,
                "cron",
                hour=cfg["hour"],
                minute=cfg.get("minute", 0),
                id=job_type,
                replace_existing=True,
            )


def _check_config_changes(scheduler: BaseScheduler) -> None:
    """Called on each heartbeat to detect and apply schedule config changes."""
    session = SessionLocal()
    try:
        rows = session.scalars(select(JobScheduleConfig)).all()
        for row in rows:
            last_seen = _last_config_versions.get(row.job_type)
            if last_seen is None or row.updated_at > last_seen:
                logger.info("Schedule config changed for %s, rescheduling", row.job_type)
                _apply_schedule(scheduler, row)
                _last_config_versions[row.job_type] = row.updated_at
    except Exception:
        logger.exception("Failed to check schedule config changes")
    finally:
        session.close()


def register_jobs(scheduler: BaseScheduler) -> None:
    # Always register the heartbeat (internal, not user-configurable)
    scheduler.add_job(heartbeat_job, "interval", minutes=5, id="heartbeat", replace_existing=True)

    # Load user-configurable schedules from DB
    _load_and_apply_configs(scheduler)

    # Register a periodic config-change checker (piggyback on heartbeat cadence)
    scheduler.add_job(
        lambda: _check_config_changes(scheduler),
        "interval",
        minutes=5,
        id="_config_reload",
        replace_existing=True,
    )
