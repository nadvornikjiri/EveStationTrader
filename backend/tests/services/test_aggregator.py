import pytest

from app.api.schemas.trade import OpportunityItemRow
from app.services.opportunities.aggregator import aggregate_source_summary


def make_item(
    name: str,
    purchase_units: float,
    demand_source: str = "Adam4EVE",
    target_now_profit: float = 16.75,
    target_period_profit: float = 21.4,
) -> OpportunityItemRow:
    return OpportunityItemRow(
        type_id=1,
        item_name=name,
        source_security_status=0.9,
        purchase_units=purchase_units,
        source_units_available=20,
        target_demand_day=10,
        target_supply_units=25,
        target_dos=2.5,
        in_transit_units_item=1,
        assets_units_item=2,
        active_sell_orders_units_item=3,
        source_station_sell_price=100,
        target_station_sell_price=125,
        target_period_avg_price=130,
        target_now_profit=target_now_profit,
        target_period_profit=target_period_profit,
        capital_required=1000,
        roi_now=0.1675,
        roi_period=0.214,
        item_volume_m3=5,
        shipping_cost=10,
        demand_source=demand_source,
    )


def test_aggregate_source_summary_counts_and_group_profit_totals() -> None:
    summary = aggregate_source_summary(
        1,
        "Amarr",
        [
            make_item("A", 10, target_now_profit=16.75, target_period_profit=21.4),
            make_item("B", 5, target_now_profit=9.5, target_period_profit=12.0),
        ],
    )
    assert summary.purchase_units_total == 15
    assert summary.capital_required_total == 2000
    assert summary.target_now_profit_weighted == pytest.approx(215.0)
    assert summary.target_period_profit_weighted == pytest.approx(274.0)
    assert summary.demand_source_summary == "Adam4EVE"
