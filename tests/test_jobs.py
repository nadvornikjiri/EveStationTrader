import tempfile
import unittest
from pathlib import Path

from eve_station_trader.ingestion import IngestionService
from eve_station_trader.jobs import IngestionJobManager
from eve_station_trader.models import Hub
from eve_station_trader.service import TraderService


class FakeIngestionService(IngestionService):
    def __init__(self) -> None:
        self.trader_service = type(
            "FakeTraderService",
            (),
            {
                "known_hubs": lambda self: [
                    Hub(key="jita", name="Jita", region_id=1, location_id=11),
                    Hub(key="amarr", name="Amarr", region_id=2, location_id=22),
                ],
                "resolve_hub": lambda self, hub_key, _region, _location: Hub(
                    key=hub_key or "jita",
                    name=(hub_key or "jita").title(),
                    region_id=1,
                    location_id=11,
                ),
            },
        )()

    def ingest_hub_region(self, hub: Hub, *, refresh: bool = True) -> dict[str, object]:
        return {"hub": {"key": hub.key}, "region_id": hub.region_id, "orders_written": 10, "refresh": refresh}


class JobTests(unittest.TestCase):
    def test_single_hub_job_completes_with_progress(self) -> None:
        jobs = IngestionJobManager(FakeIngestionService())
        job = jobs.start_job(mode="single-hub", hub_key="jita", refresh=True)

        for _ in range(50):
            current = jobs.get_job(job.job_id)
            if current.status != "running":
                break
        current = jobs.get_job(job.job_id)

        self.assertEqual(current.status, "completed")
        self.assertEqual(current.completed_steps, 1)
        self.assertEqual(current.total_steps, 1)
        self.assertEqual(len(current.results), 1)


if __name__ == "__main__":
    unittest.main()
