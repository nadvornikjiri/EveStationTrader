from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import-untyped]

from app.workers.tasks.sync_tasks import register_jobs


def main() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    register_jobs(scheduler)
    scheduler.start()


if __name__ == "__main__":
    main()
