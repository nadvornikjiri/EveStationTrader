from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.models.all_models import (
    AdamMarketOrdersTradeRaw,
    AdamMarketPriceHistoryDaily,
    EsiMarketOrder,
    Item,
    Location,
    MarketDemandResolved,
    MarketPricePeriod,
    OpportunityItem,
    OpportunitySourceSummary,
    Region,
    Station,
    System,
    UserSetting,
)
from app.repositories.trade_repository import TradeRepository
from tests.db_test_utils import build_test_session


def build_session() -> Session:
    return build_test_session()


def seed_trade_entities(session: Session) -> tuple[int, int, int]:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    jita = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    amarr = System(system_id=30002187, region_id=region.id, name="Amarr", security_status=1.0)
    session.add_all([jita, amarr])
    session.flush()

    target_location = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=jita.id,
        region_id=region.id,
        name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    )
    source_location = Location(
        location_id=60008494,
        location_type="npc_station",
        system_id=amarr.id,
        region_id=region.id,
        name="Amarr VIII (Oris) - Emperor Family Academy",
    )
    item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all(
        [
            target_location,
            source_location,
            Station(station_id=60003760, system_id=jita.id, region_id=region.id, name=target_location.name),
            Station(station_id=60008494, system_id=amarr.id, region_id=region.id, name=source_location.name),
            item,
        ]
    )
    session.commit()
    return target_location.id, source_location.id, item.id


def test_list_targets_returns_only_curated_seed_station_targets() -> None:
    session = build_session()
    seed_trade_entities(session)

    region = session.scalar(select(Region).where(Region.region_id == 10000002))
    assert region is not None
    imported_system = System(system_id=30009999, region_id=region.id, name="Imported", security_status=0.9)
    session.add(imported_system)
    session.flush()
    session.add(
        Location(
            location_id=60099999,
            location_type="npc_station",
            system_id=imported_system.id,
            region_id=region.id,
            name="Imported NPC Station",
        )
    )
    session.add(UserSetting(user_id=None, key="defaults", value={"target_market_location_ids": [60008494, 60003760]}))
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)
    targets = repo.list_targets()

    assert [target.location_id for target in targets] == [60008494, 60003760]


def test_list_targets_prefers_resolved_station_name_over_placeholder_number() -> None:
    session = build_session()
    seed_trade_entities(session)
    session.add(UserSetting(user_id=None, key="defaults", value={"target_market_location_ids": [60008494, 60003760]}))

    station = session.scalar(select(Station).where(Station.station_id == 60003760))
    location = session.scalar(select(Location).where(Location.location_id == 60003760))
    assert station is not None
    assert location is not None

    station.name = "Station 60003760"
    location.name = "Jita IV - Moon 4 - Caldari Navy Assembly Plant"
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)
    targets = repo.list_targets()

    assert targets[1].location_id == 60003760
    assert targets[1].name == "Jita IV - Moon 4 - Caldari Navy Assembly Plant"


def test_list_target_options_returns_all_station_and_structure_locations() -> None:
    session = build_session()
    seed_trade_entities(session)

    region = session.scalar(select(Region).where(Region.region_id == 10000002))
    assert region is not None
    perimeter = System(system_id=30000144, region_id=region.id, name="Perimeter", security_status=0.9)
    session.add(perimeter)
    session.flush()
    session.add(
        Location(
            location_id=1022734985679,
            location_type="structure",
            system_id=perimeter.id,
            region_id=region.id,
            name="Perimeter Tranquility Trading Tower",
        )
    )
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)
    rows = repo.list_target_options()

    assert [row.location_id for row in rows] == [60008494, 60003760, 1022734985679]


def test_list_source_summaries_reads_computed_rows_when_present() -> None:
    session = build_session()
    target_location_id, source_location_id, _item_id = seed_trade_entities(session)
    session.add(
        OpportunitySourceSummary(
            target_location_id=target_location_id,
            source_location_id=source_location_id,
            source_security_status=1.0,
            period_days=14,
            purchase_units_total=20.0,
            source_units_available_total=40.0,
            target_demand_day_total=15.0,
            target_supply_units_total=30.0,
            target_dos_weighted=2.0,
            in_transit_units=1.0,
            assets_units=2.0,
            active_sell_orders_units=3.0,
            source_avg_price_weighted=100.0,
            target_now_price_weighted=120.0,
            target_period_avg_price_weighted=125.0,
            target_now_profit_weighted=12.0,
            target_period_profit_weighted=15.0,
            capital_required_total=1500.0,
            roi_now_weighted=0.12,
            roi_period_weighted=0.15,
            total_item_volume_m3=5.0,
            shipping_cost_total=20.0,
            demand_source_summary="adam4eve",
            computed_at=datetime(2026, 3, 20, tzinfo=UTC),
        )
    )
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)
    rows = repo.list_source_summaries(target_location_id, 14)

    assert len(rows) == 1
    assert rows[0].source_location_id == source_location_id
    assert rows[0].source_market_name == "Amarr VIII (Oris) - Emperor Family Academy"
    assert rows[0].roi_now_weighted == 0.12


def test_list_source_summaries_falls_back_from_placeholder_station_name() -> None:
    session = build_session()
    target_location_id, source_location_id, _item_id = seed_trade_entities(session)
    station = session.scalar(select(Station).where(Station.station_id == 60008494))
    location = session.scalar(select(Location).where(Location.id == source_location_id))
    assert station is not None
    assert location is not None
    station.name = "Station 60008494"
    location.name = "Amarr VIII (Oris) - Emperor Family Academy"
    session.add(
        OpportunitySourceSummary(
            target_location_id=target_location_id,
            source_location_id=source_location_id,
            source_security_status=1.0,
            period_days=14,
            purchase_units_total=20.0,
            source_units_available_total=40.0,
            target_demand_day_total=15.0,
            target_supply_units_total=30.0,
            target_dos_weighted=2.0,
            in_transit_units=1.0,
            assets_units=2.0,
            active_sell_orders_units=3.0,
            source_avg_price_weighted=100.0,
            target_now_price_weighted=120.0,
            target_period_avg_price_weighted=125.0,
            target_now_profit_weighted=12.0,
            target_period_profit_weighted=15.0,
            capital_required_total=1500.0,
            roi_now_weighted=0.12,
            roi_period_weighted=0.15,
            total_item_volume_m3=5.0,
            shipping_cost_total=20.0,
            demand_source_summary="adam4eve",
            computed_at=datetime(2026, 3, 20, tzinfo=UTC),
        )
    )
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)
    rows = repo.list_source_summaries(target_location_id, 14)

    assert len(rows) == 1
    assert rows[0].source_market_name == "Amarr VIII (Oris) - Emperor Family Academy"


def test_list_sources_reads_computed_source_locations_when_present() -> None:
    session = build_session()
    target_location_id, source_location_id, _item_id = seed_trade_entities(session)
    session.add(
        OpportunitySourceSummary(
            target_location_id=target_location_id,
            source_location_id=source_location_id,
            source_security_status=1.0,
            period_days=14,
            purchase_units_total=20.0,
            source_units_available_total=40.0,
            target_demand_day_total=15.0,
            target_supply_units_total=30.0,
            target_dos_weighted=2.0,
            in_transit_units=1.0,
            assets_units=2.0,
            active_sell_orders_units=3.0,
            source_avg_price_weighted=100.0,
            target_now_price_weighted=120.0,
            target_period_avg_price_weighted=125.0,
            target_now_profit_weighted=12.0,
            target_period_profit_weighted=15.0,
            capital_required_total=1500.0,
            roi_now_weighted=0.12,
            roi_period_weighted=0.15,
            total_item_volume_m3=5.0,
            shipping_cost_total=20.0,
            demand_source_summary="adam4eve",
            computed_at=datetime(2026, 3, 20, tzinfo=UTC),
        )
    )
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)
    rows = repo.list_sources(target_location_id, 14)

    assert len(rows) == 1
    assert rows[0].location_id == 60008494
    assert rows[0].name == "Amarr VIII (Oris) - Emperor Family Academy"
    assert rows[0].location_type == "npc_station"


def test_list_items_reads_computed_rows_when_present() -> None:
    session = build_session()
    target_location_id, source_location_id, item_id = seed_trade_entities(session)
    session.add(
        OpportunityItem(
            target_location_id=target_location_id,
            source_location_id=source_location_id,
            type_id=item_id,
            period_days=14,
            purchase_units=10.0,
            source_units_available=25.0,
            target_demand_day=12.0,
            target_supply_units=24.0,
            target_dos=2.0,
            in_transit_units=1.0,
            assets_units=2.0,
            active_sell_orders_units=3.0,
            source_station_sell_price=100.0,
            target_station_sell_price=125.0,
            target_period_avg_price=130.0,
            target_now_profit=16.75,
            target_period_profit=21.4,
            capital_required=1200.0,
            roi_now=0.1675,
            roi_period=0.214,
            source_security_status=1.0,
            item_volume_m3=0.01,
            shipping_cost=15.0,
            demand_source="adam4eve",
            computed_at=datetime(2026, 3, 20, tzinfo=UTC),
        )
    )
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)
    rows = repo.list_items(target_location_id, source_location_id, 14)

    assert len(rows) == 1
    assert rows[0].item_name == "Tritanium"
    assert rows[0].purchase_units == 10.0
    assert rows[0].demand_source == "adam4eve"


def test_list_target_items_reads_computed_rows_when_present() -> None:
    session = build_session()
    target_location_id, source_location_id, item_id = seed_trade_entities(session)
    session.add(
        OpportunityItem(
            target_location_id=target_location_id,
            source_location_id=source_location_id,
            type_id=item_id,
            period_days=14,
            purchase_units=10.0,
            source_units_available=25.0,
            target_demand_day=12.0,
            target_supply_units=24.0,
            target_dos=2.0,
            in_transit_units=1.0,
            assets_units=2.0,
            active_sell_orders_units=3.0,
            source_station_sell_price=100.0,
            target_station_sell_price=125.0,
            target_period_avg_price=130.0,
            target_now_profit=16.75,
            target_period_profit=21.4,
            capital_required=1200.0,
            roi_now=0.1675,
            roi_period=0.214,
            source_security_status=1.0,
            item_volume_m3=0.01,
            shipping_cost=15.0,
            demand_source="adam4eve",
            computed_at=datetime(2026, 3, 20, tzinfo=UTC),
        )
    )
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)
    rows = repo.list_target_items(60003760, 14)

    assert len(rows) == 1
    assert rows[0].source_location_id == source_location_id
    assert rows[0].item_name == "Tritanium"


def test_repository_returns_empty_data_when_no_computed_rows_exist() -> None:
    session = build_session()
    target_location_id, source_location_id, _item_id = seed_trade_entities(session)
    repo = TradeRepository(session_factory=lambda: session)

    source_locations = repo.list_sources(target_location_id, 14)
    source_rows = repo.list_source_summaries(target_location_id, 14)
    item_rows = repo.list_items(target_location_id, source_location_id, 14)

    assert source_locations == []
    assert source_rows == []
    assert item_rows == []


def test_get_last_refresh_uses_latest_computed_timestamp() -> None:
    session = build_session()
    target_location_id, source_location_id, item_id = seed_trade_entities(session)
    older = datetime(2026, 3, 19, tzinfo=UTC)
    newer = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
    session.add(
        OpportunitySourceSummary(
            target_location_id=target_location_id,
            source_location_id=source_location_id,
            source_security_status=1.0,
            period_days=14,
            purchase_units_total=20.0,
            source_units_available_total=40.0,
            target_demand_day_total=15.0,
            target_supply_units_total=30.0,
            target_dos_weighted=2.0,
            in_transit_units=1.0,
            assets_units=2.0,
            active_sell_orders_units=3.0,
            source_avg_price_weighted=100.0,
            target_now_price_weighted=120.0,
            target_period_avg_price_weighted=125.0,
            target_now_profit_weighted=12.0,
            target_period_profit_weighted=15.0,
            capital_required_total=1500.0,
            roi_now_weighted=0.12,
            roi_period_weighted=0.15,
            total_item_volume_m3=5.0,
            shipping_cost_total=20.0,
            demand_source_summary="adam4eve",
            computed_at=older,
        )
    )
    session.add(
        OpportunityItem(
            target_location_id=target_location_id,
            source_location_id=source_location_id,
            type_id=item_id,
            period_days=14,
            purchase_units=10.0,
            source_units_available=25.0,
            target_demand_day=12.0,
            target_supply_units=24.0,
            target_dos=2.0,
            in_transit_units=1.0,
            assets_units=2.0,
            active_sell_orders_units=3.0,
            source_station_sell_price=100.0,
            target_station_sell_price=125.0,
            target_period_avg_price=130.0,
            target_now_profit=16.75,
            target_period_profit=21.4,
            capital_required=1200.0,
            roi_now=0.1675,
            roi_period=0.214,
            source_security_status=1.0,
            item_volume_m3=0.01,
            shipping_cost=15.0,
            demand_source="adam4eve",
            computed_at=newer,
        )
    )
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)

    assert repo.get_last_refresh() == newer


def test_get_item_detail_reads_requested_computed_row() -> None:
    session = build_session()
    target_location_id, source_location_id, _item_id = seed_trade_entities(session)
    pyerite = Item(type_id=35, name="Pyerite", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add(pyerite)
    session.flush()
    session.add(
        OpportunityItem(
            target_location_id=target_location_id,
            source_location_id=source_location_id,
            type_id=pyerite.id,
            period_days=14,
            purchase_units=7.0,
            source_units_available=15.0,
            target_demand_day=9.0,
            target_supply_units=18.0,
            target_dos=2.0,
            in_transit_units=1.0,
            assets_units=2.0,
            active_sell_orders_units=0.0,
            source_station_sell_price=88.0,
            target_station_sell_price=120.0,
            target_period_avg_price=125.0,
            target_now_profit=24.08,
            target_period_profit=28.75,
            capital_required=792.0,
            roi_now=0.2736363636363636,
            roi_period=0.32670454545454547,
            source_security_status=1.0,
            item_volume_m3=0.01,
            shipping_cost=12.0,
            demand_source="adam4eve",
            computed_at=datetime(2026, 3, 20, tzinfo=UTC),
        )
    )
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)
    detail = repo.get_item_detail(target_location_id, source_location_id, pyerite.type_id, 14)

    assert detail.type_id == pyerite.type_id
    assert detail.item_name == "Pyerite"
    assert detail.metrics.type_id == pyerite.type_id
    assert detail.metrics.item_name == "Pyerite"
    assert detail.metrics.source_station_sell_price == 88.0
    # No EsiMarketOrder rows seeded, so order lists should be empty
    assert detail.target_market_sell_orders == []
    assert detail.source_market_sell_orders == []
    assert detail.source_market_buy_orders == []


def test_get_item_detail_returns_live_order_book() -> None:
    """When EsiMarketOrder rows exist, detail panel returns real order book data."""
    session = build_session()
    target_location_id, source_location_id, _item_id = seed_trade_entities(session)
    now = datetime(2026, 3, 20, tzinfo=UTC)
    region = session.scalar(select(Region).where(Region.region_id == 10000002))
    assert region is not None

    pyerite = Item(type_id=35, name="Pyerite", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add(pyerite)
    session.flush()

    session.add(
        OpportunityItem(
            target_location_id=target_location_id,
            source_location_id=source_location_id,
            type_id=pyerite.id,
            period_days=14,
            purchase_units=7.0,
            source_units_available=15.0,
            target_demand_day=9.0,
            target_supply_units=18.0,
            target_dos=2.0,
            in_transit_units=0.0,
            assets_units=0.0,
            active_sell_orders_units=0.0,
            source_station_sell_price=88.0,
            target_station_sell_price=120.0,
            target_period_avg_price=125.0,
            target_now_profit=24.08,
            target_period_profit=28.75,
            capital_required=792.0,
            roi_now=0.27,
            roi_period=0.33,
            source_security_status=1.0,
            item_volume_m3=0.01,
            shipping_cost=0.0,
            demand_source="adam4eve",
            computed_at=now,
        )
    )

    # Target sell orders
    session.add_all(
        [
            EsiMarketOrder(
                order_id=5001,
                region_id=region.id,
                location_id=target_location_id,
                type_id=pyerite.id,
                system_id=1,
                is_buy_order=False,
                price=120.0,
                volume_total=50,
                volume_remain=50,
                min_volume=1,
                order_range="station",
                issued=now,
                duration=90,
            ),
            EsiMarketOrder(
                order_id=5002,
                region_id=region.id,
                location_id=target_location_id,
                type_id=pyerite.id,
                system_id=1,
                is_buy_order=False,
                price=125.0,
                volume_total=30,
                volume_remain=30,
                min_volume=1,
                order_range="station",
                issued=now,
                duration=90,
            ),
            # Source sell order
            EsiMarketOrder(
                order_id=5003,
                region_id=region.id,
                location_id=source_location_id,
                type_id=pyerite.id,
                system_id=2,
                is_buy_order=False,
                price=88.0,
                volume_total=100,
                volume_remain=100,
                min_volume=1,
                order_range="station",
                issued=now,
                duration=90,
            ),
            # Source buy order
            EsiMarketOrder(
                order_id=5004,
                region_id=region.id,
                location_id=source_location_id,
                type_id=pyerite.id,
                system_id=2,
                is_buy_order=True,
                price=80.0,
                volume_total=200,
                volume_remain=200,
                min_volume=1,
                order_range="station",
                issued=now,
                duration=90,
            ),
        ]
    )
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)
    detail = repo.get_item_detail(target_location_id, source_location_id, pyerite.type_id, 14)

    # Target sell orders sorted ascending by price
    assert len(detail.target_market_sell_orders) == 2
    assert detail.target_market_sell_orders[0].price == 120.0
    assert detail.target_market_sell_orders[0].volume == 50
    assert detail.target_market_sell_orders[0].order_value == 6000.0
    assert detail.target_market_sell_orders[0].cumulative_volume == 50
    assert detail.target_market_sell_orders[1].price == 125.0
    assert detail.target_market_sell_orders[1].cumulative_volume == 80

    # Source sell orders
    assert len(detail.source_market_sell_orders) == 1
    assert detail.source_market_sell_orders[0].price == 88.0
    assert detail.source_market_sell_orders[0].volume == 100

    # Source buy orders (no cumulative_volume)
    assert len(detail.source_market_buy_orders) == 1
    assert detail.source_market_buy_orders[0].price == 80.0
    assert detail.source_market_buy_orders[0].volume == 200
    assert detail.source_market_buy_orders[0].cumulative_volume is None


def test_get_item_detail_raises_when_requested_row_is_missing() -> None:
    session = build_session()
    target_location_id, source_location_id, _item_id = seed_trade_entities(session)
    mexallon = Item(type_id=36, name="Mexallon", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add(mexallon)
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)
    try:
        repo.get_item_detail(target_location_id, source_location_id, mexallon.type_id, 14)
    except LookupError as exc:
        assert "derived opportunity rows" in str(exc)
    else:
        raise AssertionError("expected missing detail row to raise LookupError")


def test_list_source_summaries_prepares_requested_period_on_demand() -> None:
    session = build_session()
    target_location_id, source_location_id, item_id = seed_trade_entities(session)
    session.add_all(
        [
            EsiMarketOrder(
                order_id=9001,
                region_id=1,
                location_id=source_location_id,
                type_id=item_id,
                system_id=2,
                is_buy_order=False,
                price=100.0,
                volume_total=100,
                volume_remain=100,
                min_volume=1,
                order_range="region",
                issued=datetime(2026, 3, 20, tzinfo=UTC),
                duration=90,
            ),
            EsiMarketOrder(
                order_id=9002,
                region_id=1,
                location_id=target_location_id,
                type_id=item_id,
                system_id=1,
                is_buy_order=False,
                price=120.0,
                volume_total=100,
                volume_remain=100,
                min_volume=1,
                order_range="region",
                issued=datetime(2026, 3, 20, tzinfo=UTC),
                duration=90,
            ),
            AdamMarketPriceHistoryDaily(
                location_id=target_location_id,
                type_id=item_id,
                date=datetime(2026, 3, 20, tzinfo=UTC).date(),
                average=120.0,
                highest=130.0,
                lowest=110.0,
                order_count=10,
                volume=1000,
            ),
            AdamMarketPriceHistoryDaily(
                location_id=target_location_id,
                type_id=item_id,
                date=datetime(2026, 3, 19, tzinfo=UTC).date(),
                average=140.0,
                highest=150.0,
                lowest=100.0,
                order_count=10,
                volume=1000,
            ),
            AdamMarketPriceHistoryDaily(
                location_id=source_location_id,
                type_id=item_id,
                date=datetime(2026, 3, 20, tzinfo=UTC).date(),
                average=100.0,
                highest=105.0,
                lowest=95.0,
                order_count=10,
                volume=1000,
            ),
            AdamMarketPriceHistoryDaily(
                location_id=source_location_id,
                type_id=item_id,
                date=datetime(2026, 3, 19, tzinfo=UTC).date(),
                average=110.0,
                highest=115.0,
                lowest=90.0,
                order_count=10,
                volume=1000,
            ),
        ]
    )
    session.execute(
        insert(AdamMarketOrdersTradeRaw).values(
            location_id=60003760,
            region_id=10000002,
            type_id=34,
            is_buy_order=0,
            has_gone=0,
            scanDate=datetime(2026, 3, 20, tzinfo=UTC).date(),
            amount=12.0,
            high=5.0,
            low=5.0,
            avg=5.0,
            orderNum=1,
            iskValue=60.0,
        )
    )
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)
    rows = repo.list_source_summaries(target_location_id, 2)

    assert len(rows) == 1
    assert rows[0].source_location_id == source_location_id
    assert rows[0].target_period_avg_price_weighted == 130.0


def test_list_source_summaries_prepares_universe_wide_sources_for_selected_target() -> None:
    session = build_session()
    target_location_id, source_location_id, item_id = seed_trade_entities(session)
    domain = session.scalar(select(Region).where(Region.region_id == 10000002))
    assert domain is not None
    forge = Region(region_id=10000032, name="Sinq Laison")
    session.add(forge)
    session.flush()
    dodixie = System(system_id=30002659, region_id=forge.id, name="Dodixie", security_status=0.9)
    session.add(dodixie)
    session.flush()
    remote_source = Location(
        location_id=60011866,
        location_type="npc_station",
        system_id=dodixie.id,
        region_id=forge.id,
        name="Dodixie IX - Moon 20 - Federation Navy Assembly Plant",
    )
    session.add(remote_source)
    session.flush()

    now = datetime(2026, 3, 20, tzinfo=UTC)
    session.add_all(
        [
            EsiMarketOrder(
                order_id=9101,
                region_id=domain.id,
                location_id=source_location_id,
                type_id=item_id,
                system_id=2,
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
                order_id=9102,
                region_id=forge.id,
                location_id=remote_source.id,
                type_id=item_id,
                system_id=dodixie.id,
                is_buy_order=False,
                price=95.0,
                volume_total=100,
                volume_remain=100,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
            EsiMarketOrder(
                order_id=9103,
                region_id=domain.id,
                location_id=target_location_id,
                type_id=item_id,
                system_id=1,
                is_buy_order=False,
                price=120.0,
                volume_total=100,
                volume_remain=100,
                min_volume=1,
                order_range="region",
                issued=now,
                duration=90,
            ),
            AdamMarketPriceHistoryDaily(
                location_id=target_location_id,
                type_id=item_id,
                date=now.date(),
                average=120.0,
                highest=130.0,
                lowest=110.0,
                order_count=10,
                volume=1000,
            ),
            AdamMarketPriceHistoryDaily(
                location_id=target_location_id,
                type_id=item_id,
                date=datetime(2026, 3, 19, tzinfo=UTC).date(),
                average=140.0,
                highest=150.0,
                lowest=100.0,
                order_count=10,
                volume=1000,
            ),
        ]
    )
    session.execute(
        insert(AdamMarketOrdersTradeRaw).values(
            location_id=60003760,
            region_id=10000002,
            type_id=34,
            is_buy_order=0,
            has_gone=0,
            scanDate=now.date(),
            amount=12.0,
            high=5.0,
            low=5.0,
            avg=5.0,
            orderNum=1,
            iskValue=60.0,
        )
    )
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)
    rows = repo.list_source_summaries(target_location_id, 2)

    assert [row.source_location_id for row in rows] == [remote_source.id, source_location_id]


def test_refresh_opportunities_uses_fast_rebuild_when_target_inputs_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    session = build_session()
    target_location_id, source_location_id, item_id = seed_trade_entities(session)
    session.add(
        OpportunityItem(
            target_location_id=target_location_id,
            source_location_id=source_location_id,
            type_id=item_id,
            period_days=14,
            purchase_units=5.0,
            source_units_available=10.0,
            target_demand_day=1.0,
            target_supply_units=2.0,
            target_dos=2.0,
            in_transit_units=0.0,
            assets_units=0.0,
            active_sell_orders_units=0.0,
            source_station_sell_price=100.0,
            target_station_sell_price=125.0,
            target_period_avg_price=130.0,
            target_now_profit=25.0,
            target_period_profit=30.0,
            capital_required=500.0,
            roi_now=0.25,
            roi_period=0.3,
            source_security_status=1.0,
            item_volume_m3=0.01,
            shipping_cost=0.0,
            demand_source="adam4eve",
            computed_at=datetime(2026, 3, 20, tzinfo=UTC),
        )
    )
    session.add(
        MarketPricePeriod(
            location_id=target_location_id,
            type_id=item_id,
            period_days=14,
            current_price=120.0,
            period_avg_price=125.0,
            price_min=110.0,
            price_max=130.0,
        )
    )
    session.add(
        MarketDemandResolved(
            location_id=target_location_id,
            type_id=item_id,
            period_days=14,
            demand_source="adam4eve",
            buy_from_sell_period=14.0,
            sell_to_buy_period=7.0,
            buy_from_sell_yesterday=1.0,
            sell_to_buy_yesterday=0.5,
        )
    )
    session.commit()

    captured: dict[str, object] = {}
    prepare_called = False

    def fake_refresh_trade_scope_from_existing_rows(self, db_session, **kwargs) -> bool:
        captured["session"] = db_session
        captured.update(kwargs)
        return True

    def fake_prepare_trade_period(self, db_session, **kwargs) -> None:
        nonlocal prepare_called
        del db_session, kwargs
        prepare_called = True

    monkeypatch.setattr(
        "app.services.sync.service.SyncService.refresh_trade_scope_from_existing_rows",
        fake_refresh_trade_scope_from_existing_rows,
    )
    monkeypatch.setattr("app.services.sync.service.SyncService.prepare_trade_period", fake_prepare_trade_period)

    repo = TradeRepository(session_factory=lambda: session)
    repo.refresh_opportunities(60003760, 14, source_location_id=60008494, type_id=34)

    assert captured["session"] is session
    assert captured["target_location_id"] == target_location_id
    assert captured["source_location_id"] == source_location_id
    assert captured["type_id"] == 34
    assert captured["period_days"] == 14
    assert prepare_called is False
