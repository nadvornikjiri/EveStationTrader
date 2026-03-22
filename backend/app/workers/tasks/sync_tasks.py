import logging
from datetime import UTC, datetime

from apscheduler.schedulers.base import BaseScheduler  # type: ignore[import-untyped]

from app.services.sync.service import SyncService

logger = logging.getLogger(__name__)


def heartbeat_job() -> None:
    logger.info("worker heartbeat at %s", datetime.now(UTC).isoformat())


def rebuild_opportunities_job() -> None:
    result = SyncService().trigger_job("opportunity_rebuild")
    logger.info(
        "opportunity rebuild completed: job_id=%s status=%s records=%s",
        result.id,
        result.status,
        result.records_processed,
    )


def register_jobs(scheduler: BaseScheduler) -> None:
    scheduler.add_job(heartbeat_job, "interval", minutes=5, id="heartbeat", replace_existing=True)
    scheduler.add_job(
        rebuild_opportunities_job,
        "interval",
        minutes=10,
        id="rebuild_opportunities",
        replace_existing=True,
    )
