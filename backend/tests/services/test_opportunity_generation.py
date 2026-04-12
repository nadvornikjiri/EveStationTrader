from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import (
    CharacterAsset,
    CharacterOrder,
    EsiHistoryDaily,
    EsiCharacter,
    EsiMarketOrder,
    InTransitAsset,
    Item,
    Location,
    MarketDemandResolved,
    MarketPricePeriod,
    OpportunityItem,
    OpportunitySourceSummary,
    Region,
    System,
    User,
)
from app.services.opportunities.generation import OpportunityGenerationService
from tests.db_test_utils import build_test_session

pytestmark = pytest.mark.integration


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
            MarketDemandResolved(
                location_id=target.id,
                type_id=tritanium.id,
                period_days=14,
                demand_source="adam4eve",
                buy_from_sell_period=40.0,
                sell_to_buy_period=8.0,
                buy_from_sell_yesterday=10.0,
                sell_to_buy_yesterday=2.0,
            ),
            MarketDemandResolved(
                location_id=target.id,
                type_id=pyerite.id,
                period_days=14,
                demand_source="adam4eve",
                buy_from_sell_period=20.0,
                sell_to_buy_period=5.0,
                buy_from_sell_yesterday=5.0,
                sell_to_buy_yesterday=1.0,
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
    # purchase_units still uses latest-day demand sizing = min(500, 10.0) = 10.0
    assert first_item.source_units_available == 500.0
    assert first_item.target_supply_units == 50.0
    assert first_item.purchase_units == pytest.approx(10.0)
    assert first_item.target_dos == pytest.approx(50.0 / (40.0 / 14.0))
    assert first_item.target_demand_day == pytest.approx(40.0 / 14.0)
    assert first_item.target_now_profit == pytest.approx(20.0)
    assert first_item.target_period_profit == pytest.approx(50.0)
    assert first_item.capital_required == pytest.approx(1000.0)
    assert first_item.roi_now == pytest.approx(0.2)
    assert first_item.source_station_sell_price == pytest.approx(100.0)
    assert first_item.target_station_sell_price == pytest.approx(120.0)

    # Pyerite: source_units_available=100, target_supply_units=20
    second_item = item_rows[1]
    assert second_item.source_units_available == 100.0
    assert second_item.target_supply_units == 20.0
    assert second_item.purchase_units == pytest.approx(5.0)
    assert second_item.target_dos == pytest.approx(20.0 / (20.0 / 14.0))
    assert second_item.target_now_profit == pytest.approx(50.0)
    assert second_item.target_period_profit == pytest.approx(-70.0)

    summary = summary_rows[0]
    # purchase_units_total = 10.0 + 5.0
    assert summary.purchase_units_total == pytest.approx(15.0)
    assert summary.capital_required_total == pytest.approx(1750.0)
    assert summary.target_now_profit_weighted == pytest.approx(
        first_item.target_now_profit * first_item.purchase_units + second_item.target_now_profit * second_item.purchase_units
    )
    assert summary.target_period_profit_weighted == pytest.approx(
        first_item.target_period_profit * first_item.purchase_units
        + second_item.target_period_profit * second_item.purchase_units
    )
    assert summary.source_security_status == pytest.approx(0.7)
    assert summary.demand_source_summary == "adam4eve"


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
        select(EsiMarketOrder).where(
            EsiMarketOrder.location_id == ids["source_location_id"],
            EsiMarketOrder.type_id == ids["tritanium_id"],
            EsiMarketOrder.is_buy_order.is_(False),
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
    source_price.price = 80.0
    demand.buy_from_sell_period = 56.0
    demand.buy_from_sell_yesterday = 4.0
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
    assert item_rows[0].target_demand_day == pytest.approx(4.0)
    assert summary_rows[0].capital_required_total == pytest.approx(320.0)


def test_generate_opportunities_uses_regionwide_esi_history_volume() -> None:
    session = build_session()
    ids = seed_trade_inputs(session)

    target_location = session.get(Location, ids["target_location_id"])
    assert target_location is not None

    session.add_all(
        [
            EsiHistoryDaily(
                region_id=target_location.region_id,
                type_id=ids["tritanium_id"],
                date=datetime(2026, 4, 9, tzinfo=UTC).date(),
                average=97.0,
                highest=103.0,
                lowest=92.0,
                order_count=10,
                volume=70,
            ),
            EsiHistoryDaily(
                region_id=target_location.region_id,
                type_id=ids["tritanium_id"],
                date=datetime(2026, 4, 8, tzinfo=UTC).date(),
                average=99.0,
                highest=104.0,
                lowest=94.0,
                order_count=12,
                volume=44,
            ),
        ]
    )
    session.commit()

    OpportunityGenerationService().generate_for_target(
        session,
        target_location_id=ids["target_location_id"],
        source_location_ids=[ids["source_location_id"]],
        type_ids=[ids["tritanium_id"]],
        period_days=14,
    )

    row = session.scalars(select(OpportunityItem)).one()
    assert row.esi_demand_day == pytest.approx((70 + 44) / 14.0)


def test_generate_opportunities_populates_assets_target_orders_and_in_transit_metrics() -> None:
    session = build_session()
    ids = seed_trade_inputs(session)

    user = User(primary_character_id=None)
    session.add(user)
    session.flush()
    characters = [
        EsiCharacter(
            user_id=user.id,
            character_id=90000042,
            character_name="Audit Trader",
            corporation_name="Signal Cartel",
            granted_scopes="esi-assets.read_assets.v1 esi-markets.read_character_orders.v1",
            sync_enabled=True,
        ),
        EsiCharacter(
            user_id=user.id,
            character_id=90000077,
            character_name="Alt Hauler",
            corporation_name="PushX",
            granted_scopes="esi-assets.read_assets.v1 esi-markets.read_character_orders.v1",
            sync_enabled=True,
        ),
    ]
    session.add_all(characters)
    session.flush()

    session.add_all(
        [
            CharacterAsset(
                character_id=characters[0].id,
                type_id=ids["tritanium_id"],
                quantity=12,
                external_location_id=7_000_000_001,
                location_name="Asset Hangar",
            ),
            CharacterAsset(
                character_id=characters[1].id,
                type_id=ids["tritanium_id"],
                quantity=8,
                external_location_id=7_000_000_002,
                location_name="Freighter Hold",
            ),
            CharacterOrder(
                character_id=characters[0].id,
                order_id=8001,
                type_id=ids["tritanium_id"],
                volume_remain=21,
                is_buy_order=False,
                price=119.0,
                external_location_id=60003760,
                resolved_location_id=ids["target_location_id"],
            ),
            CharacterOrder(
                character_id=characters[1].id,
                order_id=8002,
                type_id=ids["tritanium_id"],
                volume_remain=5,
                is_buy_order=False,
                price=118.0,
                external_location_id=60008494,
                resolved_location_id=ids["source_location_id"],
            ),
            InTransitAsset(
                source_location_id=ids["source_location_id"],
                target_location_id=ids["target_location_id"],
                type_id=ids["tritanium_id"],
                quantity=6,
                note="Courier contract",
            ),
        ]
    )
    session.commit()

    OpportunityGenerationService().generate_for_target(
        session,
        target_location_id=ids["target_location_id"],
        source_location_ids=[ids["source_location_id"]],
        type_ids=[ids["tritanium_id"]],
        period_days=14,
    )

    row = session.scalar(select(OpportunityItem).where(OpportunityItem.type_id == ids["tritanium_id"]))
    summary = session.scalar(select(OpportunitySourceSummary))

    assert row is not None
    assert summary is not None
    assert row.assets_units == pytest.approx(20.0)
    assert row.active_sell_orders_units == pytest.approx(21.0)
    assert row.in_transit_units == pytest.approx(6.0)
    assert summary.assets_units == pytest.approx(20.0)
    assert summary.active_sell_orders_units == pytest.approx(21.0)
    assert summary.in_transit_units == pytest.approx(6.0)


def test_generate_opportunities_uses_weighted_source_acquisition_price_when_lowest_order_cannot_fill_purchase_units() -> None:
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
                current_price=160.0,
                period_avg_price=180.0,
                price_min=150.0,
                price_max=185.0,
            ),
            MarketDemandResolved(
                location_id=target.id,
                type_id=item.id,
                period_days=14,
                demand_source="adam4eve",
                buy_from_sell_period=25.0,
                sell_to_buy_period=4.0,
                buy_from_sell_yesterday=5.0,
                sell_to_buy_yesterday=1.0,
            ),
        ]
    )
    now = datetime.now(UTC)
    session.add_all(
        [
            EsiMarketOrder(
                order_id=5001,
                region_id=region.id,
                location_id=source.id,
                type_id=item.id,
                system_id=source_sys.id,
                is_buy_order=False,
                price=100.0,
                volume_total=3,
                volume_remain=3,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
            EsiMarketOrder(
                order_id=5002,
                region_id=region.id,
                location_id=source.id,
                type_id=item.id,
                system_id=source_sys.id,
                is_buy_order=False,
                price=130.0,
                volume_total=10,
                volume_remain=10,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
            EsiMarketOrder(
                order_id=5003,
                region_id=region.id,
                location_id=target.id,
                type_id=item.id,
                system_id=target_sys.id,
                is_buy_order=False,
                price=160.0,
                volume_total=12,
                volume_remain=12,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
        ]
    )
    session.commit()

    result = OpportunityGenerationService().generate_for_target(
        session,
        target_location_id=target.id,
        source_location_ids=[source.id],
        type_ids=[item.id],
        period_days=14,
    )

    row = session.scalar(select(OpportunityItem))
    assert result.item_count == 1
    assert row is not None
    assert row.purchase_units == pytest.approx(5.0)
    assert row.source_station_sell_price == pytest.approx(112.0)
    assert row.target_station_sell_price == pytest.approx(160.0)
    assert row.target_now_profit == pytest.approx(48.0)
    assert row.target_period_profit == pytest.approx(68.0)
    assert row.capital_required == pytest.approx(560.0)
    assert row.roi_now == pytest.approx(48.0 / 112.0)


def test_generate_opportunities_uses_period_average_demand_per_day() -> None:
    session = build_session()
    ids = seed_trade_inputs(session)

    OpportunityGenerationService().generate_for_target(
        session,
        target_location_id=ids["target_location_id"],
        source_location_ids=[ids["source_location_id"]],
        type_ids=[ids["tritanium_id"]],
        period_days=14,
    )

    row = session.scalar(select(OpportunityItem))

    assert row is not None
    assert row.target_demand_day == pytest.approx(40.0 / 14.0)
    assert row.purchase_units == pytest.approx(10.0)


def test_generate_opportunities_replace_entire_target_scope_prunes_stale_rows() -> None:
    session = build_session()
    ids = seed_trade_inputs(session)
    stale_source = Location(
        location_id=60011866,
        location_type="npc_station",
        system_id=session.scalar(select(Location.system_id).where(Location.id == ids["source_location_id"])),
        region_id=session.scalar(select(Location.region_id).where(Location.id == ids["source_location_id"])),
        name="Stale Source",
    )
    session.add(stale_source)
    session.flush()
    session.add(
        OpportunityItem(
            target_location_id=ids["target_location_id"],
            source_location_id=stale_source.id,
            type_id=ids["tritanium_id"],
            period_days=14,
            purchase_units=9.0,
            source_units_available=9.0,
            target_demand_day=99.0,
            target_supply_units=9.0,
            target_dos=1.0,
            in_transit_units=0.0,
            assets_units=0.0,
            active_sell_orders_units=0.0,
            source_station_sell_price=1.0,
            target_station_sell_price=2.0,
            target_period_avg_price=3.0,
            target_now_profit=1.0,
            target_period_profit=2.0,
            capital_required=9.0,
            roi_now=1.0,
            roi_period=2.0,
            source_security_status=0.7,
            item_volume_m3=0.01,
            shipping_cost=0.0,
            demand_source="adam4eve",
            computed_at=datetime(2026, 4, 1, tzinfo=UTC),
        )
    )
    session.add(
        OpportunitySourceSummary(
            target_location_id=ids["target_location_id"],
            source_location_id=stale_source.id,
            source_security_status=0.7,
            period_days=14,
            purchase_units_total=9.0,
            source_units_available_total=9.0,
            target_demand_day_total=99.0,
            target_supply_units_total=9.0,
            target_dos_weighted=1.0,
            in_transit_units=0.0,
            assets_units=0.0,
            active_sell_orders_units=0.0,
            source_avg_price_weighted=1.0,
            target_now_price_weighted=2.0,
            target_period_avg_price_weighted=3.0,
            target_now_profit_weighted=9.0,
            target_period_profit_weighted=18.0,
            capital_required_total=9.0,
            roi_now_weighted=1.0,
            roi_period_weighted=2.0,
            total_item_volume_m3=0.09,
            shipping_cost_total=0.0,
            demand_source_summary="adam4eve",
            computed_at=datetime(2026, 4, 1, tzinfo=UTC),
        )
    )
    session.commit()

    OpportunityGenerationService().generate_for_target(
        session,
        target_location_id=ids["target_location_id"],
        source_location_ids=[ids["source_location_id"]],
        type_ids=[ids["tritanium_id"]],
        period_days=14,
        replace_entire_target_scope=True,
    )

    stale_items = session.scalars(
        select(OpportunityItem).where(
            OpportunityItem.target_location_id == ids["target_location_id"],
            OpportunityItem.source_location_id == stale_source.id,
            OpportunityItem.period_days == 14,
        )
    ).all()
    stale_summaries = session.scalars(
        select(OpportunitySourceSummary).where(
            OpportunitySourceSummary.target_location_id == ids["target_location_id"],
            OpportunitySourceSummary.source_location_id == stale_source.id,
            OpportunitySourceSummary.period_days == 14,
        )
    ).all()

    assert stale_items == []
    assert stale_summaries == []


def test_generate_opportunities_uses_lowest_live_target_sell_order_for_now_price_and_period_history_for_avg() -> None:
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
                current_price=155.0,
                period_avg_price=180.0,
                price_min=140.0,
                price_max=195.0,
            ),
            MarketDemandResolved(
                location_id=target.id,
                type_id=item.id,
                period_days=14,
                demand_source="adam4eve",
                buy_from_sell_period=35.0,
                sell_to_buy_period=6.0,
                buy_from_sell_yesterday=5.0,
                sell_to_buy_yesterday=1.0,
            ),
        ]
    )
    now = datetime.now(UTC)
    session.add_all(
        [
            EsiMarketOrder(
                order_id=6001,
                region_id=region.id,
                location_id=source.id,
                type_id=item.id,
                system_id=source_sys.id,
                is_buy_order=False,
                price=100.0,
                volume_total=10,
                volume_remain=10,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
            EsiMarketOrder(
                order_id=7001,
                region_id=region.id,
                location_id=target.id,
                type_id=item.id,
                system_id=target_sys.id,
                is_buy_order=False,
                price=160.0,
                volume_total=20,
                volume_remain=20,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
            EsiMarketOrder(
                order_id=7002,
                region_id=region.id,
                location_id=target.id,
                type_id=item.id,
                system_id=target_sys.id,
                is_buy_order=False,
                price=140.0,
                volume_total=4,
                volume_remain=4,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
            EsiMarketOrder(
                order_id=7003,
                region_id=region.id,
                location_id=target.id,
                type_id=item.id,
                system_id=target_sys.id,
                is_buy_order=True,
                price=500.0,
                volume_total=50,
                volume_remain=50,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
        ]
    )
    session.commit()

    result = OpportunityGenerationService().generate_for_target(
        session,
        target_location_id=target.id,
        source_location_ids=[source.id],
        type_ids=[item.id],
        period_days=14,
    )

    row = session.scalar(select(OpportunityItem))
    assert result.item_count == 1
    assert row is not None
    assert row.target_station_sell_price == pytest.approx(140.0)
    assert row.target_period_avg_price == pytest.approx(180.0)
    assert row.target_now_profit == pytest.approx(40.0)
    assert row.target_period_profit == pytest.approx(80.0)


def test_generate_opportunities_skips_items_without_live_source_and_target_sell_orders() -> None:
    """Live source and target sell prices are required to compute a shipping opportunity."""
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
            MarketDemandResolved(
                location_id=target.id,
                type_id=item.id,
                period_days=14,
                demand_source="adam4eve",
                buy_from_sell_period=40.0,
                sell_to_buy_period=8.0,
                buy_from_sell_yesterday=10.0,
                sell_to_buy_yesterday=2.0,
            ),
        ]
    )
    session.commit()

    result = OpportunityGenerationService().generate_for_target(
        session,
        target_location_id=target.id,
        source_location_ids=[source.id],
        type_ids=[item.id],
        period_days=14,
    )

    assert result.item_count == 0
    assert session.scalars(select(OpportunityItem)).all() == []


def test_generate_opportunities_falls_back_to_live_target_price_without_period_history() -> None:
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

    session.add(
        MarketDemandResolved(
            location_id=target.id,
            type_id=item.id,
            period_days=14,
            demand_source="adam4eve",
            buy_from_sell_period=40.0,
            sell_to_buy_period=8.0,
            buy_from_sell_yesterday=10.0,
            sell_to_buy_yesterday=2.0,
        )
    )
    now = datetime.now(UTC)
    session.add_all(
        [
            EsiMarketOrder(
                order_id=4001,
                region_id=region.id,
                location_id=source.id,
                type_id=item.id,
                system_id=source_sys.id,
                is_buy_order=False,
                price=100.0,
                volume_total=100,
                volume_remain=100,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
            EsiMarketOrder(
                order_id=4002,
                region_id=region.id,
                location_id=target.id,
                type_id=item.id,
                system_id=target_sys.id,
                is_buy_order=False,
                price=120.0,
                volume_total=25,
                volume_remain=25,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
        ]
    )
    session.commit()

    result = OpportunityGenerationService().generate_for_target(
        session,
        target_location_id=target.id,
        source_location_ids=[source.id],
        type_ids=[item.id],
        period_days=14,
    )

    row = session.scalar(select(OpportunityItem))
    assert result.item_count == 1
    assert row is not None
    assert row.target_station_sell_price == 120.0
    assert row.target_period_avg_price == 120.0
    assert row.target_period_profit == row.target_now_profit
