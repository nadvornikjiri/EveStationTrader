import tempfile
import unittest
from pathlib import Path

from eve_station_trader.db import MarketDatabase
from eve_station_trader.models import MarketOrder
from eve_station_trader.service import TraderService


class DatabaseTests(unittest.TestCase):
    def test_replace_region_orders_updates_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = MarketDatabase(Path(temp_dir) / "market.sqlite3")
            orders = [
                MarketOrder(
                    type_id=34,
                    location_id=60003760,
                    is_buy_order=False,
                    price=100.0,
                    volume_remain=2500,
                    min_volume=1,
                    range="station",
                )
            ]

            written = database.replace_region_orders(10000002, orders, source="test")
            snapshot = database.region_snapshot(10000002)

            self.assertEqual(written, 1)
            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot["orders_written"], 1)
            self.assertEqual(snapshot["source"], "test")
            self.assertEqual(len(database.get_region_orders(10000002)), 1)

    def test_service_prefers_database_orders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = TraderService(
                cache_dir=root / "cache",
                database_path=root / "market.sqlite3",
            )
            service.database.replace_region_orders(
                10000002,
                [
                    MarketOrder(
                        type_id=34,
                        location_id=60003760,
                        is_buy_order=False,
                        price=101.0,
                        volume_remain=4000,
                        min_volume=1,
                        range="station",
                    )
                ],
                source="test",
            )

            orders = service.fetch_region_orders(10000002, refresh=False, prefer_database=True)

            self.assertEqual(len(orders), 1)
            self.assertEqual(orders[0].price, 101.0)


if __name__ == "__main__":
    unittest.main()
