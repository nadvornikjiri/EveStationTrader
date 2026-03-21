import logging
from datetime import UTC, datetime

from apscheduler.schedulers.base import BaseScheduler  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


def heartbeat_job() -> None:
    logger.info("worker heartbeat at %s", datetime.now(UTC).isoformat())


def rebuild_opportunities_job() -> None:
    logger.info("opportunity rebuild placeholder executed")


def register_jobs(scheduler: BaseScheduler) -> None:
    scheduler.add_job(heartbeat_job, "interval", minutes=5, id="heartbeat", replace_existing=True)
    scheduler.add_job(
        rebuild_opportunities_job,
        "interval",
        minutes=10,
        id="rebuild_opportunities",
        replace_existing=True,
    )
