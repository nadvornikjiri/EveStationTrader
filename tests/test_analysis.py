import unittest

from eve_station_trader.analysis import AnalysisSettings, find_opportunities
from eve_station_trader.models import BestOrders, Hub


SOURCE_HUB = Hub(key="jita", name="Jita", region_id=10000002, location_id=60003760)
DESTINATION_HUB = Hub(key="amarr", name="Amarr", region_id=10000043, location_id=60008494)


class AnalysisTests(unittest.TestCase):
    def test_finds_instant_opportunity(self) -> None:
        settings = AnalysisSettings(
            sales_tax=0.036,
            destination_broker_fee=0.03,
            minimum_profit=50_000,
            minimum_roi_percent=1.0,
            top_n=10,
            strategy="instant",
        )
        source_orders = {
            34: BestOrders(best_sell_price=100.0, best_sell_volume=20_000, best_buy_price=99.0, best_buy_volume=1000)
        }
        destination_orders = {
            34: BestOrders(best_sell_price=112.0, best_sell_volume=10_000, best_buy_price=110.0, best_buy_volume=15_000)
        }

        opportunities = find_opportunities(
            source_hub=SOURCE_HUB,
            destination_hub=DESTINATION_HUB,
            source_orders=source_orders,
            destination_orders=destination_orders,
            item_names={34: "Tritanium"},
            settings=settings,
        )

        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].item_name, "Tritanium")
        self.assertEqual(opportunities[0].tradable_units, 15_000)
        self.assertGreater(opportunities[0].estimated_profit, 0)

    def test_filters_unprofitable_relist_candidate(self) -> None:
        settings = AnalysisSettings(
            sales_tax=0.036,
            destination_broker_fee=0.03,
            minimum_profit=1,
            minimum_roi_percent=0.0,
            top_n=10,
            strategy="relist",
        )
        source_orders = {
            35: BestOrders(best_sell_price=100.0, best_sell_volume=500, best_buy_price=95.0, best_buy_volume=500)
        }
        destination_orders = {
            35: BestOrders(best_sell_price=101.0, best_sell_volume=500, best_buy_price=98.0, best_buy_volume=500)
        }

        opportunities = find_opportunities(
            source_hub=SOURCE_HUB,
            destination_hub=DESTINATION_HUB,
            source_orders=source_orders,
            destination_orders=destination_orders,
            item_names={35: "Pyerite"},
            settings=settings,
        )

        self.assertEqual(opportunities, [])


if __name__ == "__main__":
    unittest.main()
