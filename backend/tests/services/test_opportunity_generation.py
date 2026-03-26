from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import (
    EsiMarketOrder,
    Item,
    Location,
    MarketDemandResolved,
    MarketPricePeriod,
    OpportunityItem,
    OpportunitySourceSummary,
    Region,
    System,
)
from app.services.opportunities.generation import OpportunityGenerationService
from tests.db_test_utils import build_test_session


def build_session() -> Session:
    return build_test_session()


def seed_trade_inputs(session: Session) -> dict[str, int]:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    target_system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    source_system = System(system_id=30002187, region_id=region.id, name="Amarr", security_status=0.7)
    session.add_all([target_system, source_system])
    session.flush()

    target = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=target_system.id,
        region_id=region.id,
        name="Jita IV - Moon 4",
    )
    source = Location(
        location_id=60008494,
        location_type="npc_station",
        system_id=source_system.id,
        region_id=region.id,
        name="Amarr VIII",
    )
    tritanium = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    pyerite = Item(type_id=35, name="Pyerite", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all([target, source, tritanium, pyerite])
    session.flush()

    session.add_all(
        [
            MarketPricePeriod(
                location_id=target.id,
                type_id=tritanium.id,
                period_days=14,
                current_price=120.0,
                period_avg_price=150.0,
                price_min=100.0,
                price_max=155.0,
            ),
            MarketPricePeriod(
                location_id=target.id,
                type_id=pyerite.id,
                period_days=14,
                current_price=200.0,
                period_avg_price=80.0,
                price_min=75.0,
                price_max=205.0,
            ),
            MarketPricePeriod(
                location_id=source.id,
                type_id=tritanium.id,
                period_days=14,
                current_price=100.0,
                period_avg_price=98.0,
                price_min=97.0,
                price_max=101.0,
            ),
            MarketPricePeriod(
                location_id=source.id,
                type_id=pyerite.id,
                period_days=14,
                current_price=150.0,
                period_avg_price=140.0,
                price_min=135.0,
                price_max=151.0,
            ),
            MarketDemandResolved(
                location_id=target.id,
                type_id=tritanium.id,
                period_days=14,
                demand_source="adam4eve",
                confidence_score=0.9,
                demand_day=10.0,
            ),
            MarketDemandResolved(
                location_id=target.id,
                type_id=pyerite.id,
                period_days=14,
                demand_source="adam4eve",
                confidence_score=0.8,
                demand_day=5.0,
            ),
        ]
    )
    now = datetime.now(UTC)
    session.add_all(
        [
            # Source sell orders for tritanium (total volume_remain = 500)
            EsiMarketOrder(
                order_id=1001,
                region_id=region.id,
                location_id=source.id,
                type_id=tritanium.id,
                system_id=source_system.id,
                is_buy_order=False,
                price=100.0,
                volume_total=300,
                volume_remain=300,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
            EsiMarketOrder(
                order_id=1002,
                region_id=region.id,
                location_id=source.id,
                type_id=tritanium.id,
                system_id=source_system.id,
                is_buy_order=False,
                price=105.0,
                volume_total=200,
                volume_remain=200,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
            # Source sell orders for pyerite (total volume_remain = 100)
            EsiMarketOrder(
                order_id=1003,
                region_id=region.id,
                location_id=source.id,
                type_id=pyerite.id,
                system_id=source_system.id,
                is_buy_order=False,
                price=150.0,
                volume_total=100,
                volume_remain=100,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
            # Target sell orders for tritanium (total volume_remain = 50)
            EsiMarketOrder(
                order_id=2001,
                region_id=region.id,
                location_id=target.id,
                type_id=tritanium.id,
                system_id=target_system.id,
                is_buy_order=False,
                price=120.0,
                volume_total=50,
                volume_remain=50,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
            # Target sell orders for pyerite (total volume_remain = 20)
            EsiMarketOrder(
                order_id=2002,
                region_id=region.id,
                location_id=target.id,
                type_id=pyerite.id,
                system_id=target_system.id,
                is_buy_order=False,
                price=200.0,
                volume_total=20,
                volume_remain=20,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
            # Source buy order (should NOT count toward sell-side volume)
            EsiMarketOrder(
                order_id=3001,
                region_id=region.id,
                location_id=source.id,
                type_id=tritanium.id,
                system_id=source_system.id,
                is_buy_order=True,
                price=90.0,
                volume_total=1000,
                volume_remain=1000,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
        ]
    )

    session.commit()

    return {
        "target_location_id": target.id,
        "source_location_id": source.id,
        "tritanium_id": tritanium.id,
        "pyerite_id": pyerite.id,
    }


def test_generate_opportunities_persists_items_and_source_summary() -> None:
    session = build_session()
    ids = seed_trade_inputs(session)

    result = OpportunityGenerationService().generate_for_target(
        session,
        target_location_id=ids["target_location_id"],
        source_location_ids=[ids["source_location_id"]],
        type_ids=[ids["tritanium_id"], ids["pyerite_id"]],
        period_days=14,
        shipping_cost_per_m3=1000.0,
    )

    item_rows = session.scalars(select(OpportunityItem).order_by(OpportunityItem.type_id.asc())).all()
    summary_rows = session.scalars(select(OpportunitySourceSummary)).all()

    assert result.item_count == 2
    assert result.summary_count == 1
    assert len(item_rows) == 2
    assert len(summary_rows) == 1

    first_item = item_rows[0]
    # Tritanium: source_units_available=500 (300+200), target_supply_units=50
    # purchase_units = min(500, 10.0) = 10.0
    assert first_item.source_units_available == 500.0
    assert first_item.target_supply_units == 50.0
    assert first_item.purchase_units == 10.0
    assert first_item.target_dos == pytest.approx(5.0)
    assert first_item.target_demand_day == 10.0
    assert first_item.target_now_profit == pytest.approx(12.08)
    assert first_item.target_period_profit == pytest.approx(40.1)
    assert first_item.capital_required == 1000.0
    assert first_item.roi_now == pytest.approx(0.1208)

    # Pyerite: source_units_available=100, target_supply_units=20
    second_item = item_rows[1]
    assert second_item.source_units_available == 100.0
    assert second_item.target_supply_units == 20.0
    assert second_item.purchase_units == 5.0  # min(100, 5.0)
    assert second_item.target_dos == pytest.approx(4.0)

    summary = summary_rows[0]
    # purchase_units_total = 10.0 + 5.0 = 15.0
    assert summary.purchase_units_total == 15.0
    assert summary.capital_required_total == pytest.approx(1750.0)
    assert summary.source_security_status == 0.7
    assert summary.demand_source_summary == "adam4eve"
    assert summary.confidence_score_summary == 0.8


def test_generate_opportunities_replaces_prior_rows_on_rerun() -> None:
    session = build_session()
    ids = seed_trade_inputs(session)
    service = OpportunityGenerationService()

    service.generate_for_target(
        session,
        target_location_id=ids["target_location_id"],
        source_location_ids=[ids["source_location_id"]],
        type_ids=[ids["tritanium_id"]],
        period_days=14,
    )

    source_price = session.scalar(
        select(MarketPricePeriod).where(
            MarketPricePeriod.location_id == ids["source_location_id"],
            MarketPricePeriod.type_id == ids["tritanium_id"],
            MarketPricePeriod.period_days == 14,
        )
    )
    demand = session.scalar(
        select(MarketDemandResolved).where(
            MarketDemandResolved.location_id == ids["target_location_id"],
            MarketDemandResolved.type_id == ids["tritanium_id"],
            MarketDemandResolved.period_days == 14,
        )
    )
    assert source_price is not None
    assert demand is not None
    source_price.current_price = 80.0
    demand.demand_day = 4.0
    session.commit()

    result = service.generate_for_target(
        session,
        target_location_id=ids["target_location_id"],
        source_location_ids=[ids["source_location_id"]],
        type_ids=[ids["tritanium_id"]],
        period_days=14,
    )

    item_rows = session.scalars(select(OpportunityItem)).all()
    summary_rows = session.scalars(select(OpportunitySourceSummary)).all()

    assert result.item_count == 1
    assert result.summary_count == 1
    assert len(item_rows) == 1
    assert len(summary_rows) == 1
    assert item_rows[0].source_station_sell_price == 80.0
    assert item_rows[0].capital_required == pytest.approx(320.0)
    assert summary_rows[0].capital_required_total == pytest.approx(320.0)


def test_generate_opportunities_zero_orders_fallback() -> None:
    """When no EsiMarketOrder rows exist, liquidity fields should be zero."""
    session = build_test_session()
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    target_sys = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    source_sys = System(system_id=30002187, region_id=region.id, name="Amarr", security_status=0.7)
    session.add_all([target_sys, source_sys])
    session.flush()

    target = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=target_sys.id,
        region_id=region.id,
        name="Jita IV",
    )
    source = Location(
        location_id=60008494,
        location_type="npc_station",
        system_id=source_sys.id,
        region_id=region.id,
        name="Amarr VIII",
    )
    item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all([target, source, item])
    session.flush()

    session.add_all(
        [
            MarketPricePeriod(
                location_id=target.id,
                type_id=item.id,
                period_days=14,
                current_price=120.0,
                period_avg_price=150.0,
                price_min=100.0,
                price_max=155.0,
            ),
            MarketPricePeriod(
                location_id=source.id,
                type_id=item.id,
                period_days=14,
                current_price=100.0,
                period_avg_price=98.0,
                price_min=97.0,
                price_max=101.0,
            ),
            MarketDemandResolved(
                location_id=target.id,
                type_id=item.id,
                period_days=14,
                demand_source="adam4eve",
                confidence_score=0.9,
                demand_day=10.0,
            ),
        ]
    )
    session.commit()

    # No EsiMarketOrder rows seeded — should gracefully default to 0
    result = OpportunityGenerationService().generate_for_target(
        session,
        target_location_id=target.id,
        source_location_ids=[source.id],
        type_ids=[item.id],
        period_days=14,
    )

    assert result.item_count == 1
    opp = session.scalars(select(OpportunityItem)).all()[0]
    assert opp.source_units_available == 0.0
    assert opp.target_supply_units == 0.0
    assert opp.purchase_units == 0.0
    assert opp.target_dos == 0.0
