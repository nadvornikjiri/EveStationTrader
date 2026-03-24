from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import (
    Item,
    Location,
    OpportunityItem,
    OpportunitySourceSummary,
    Region,
    System,
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
    session.add_all([target_location, source_location, item])
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
    session.commit()

    repo = TradeRepository(session_factory=lambda: session)
    targets = repo.list_targets()

    assert [target.location_id for target in targets] == [60008494, 60003760]


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
            risk_pct_weighted=0.04,
            warning_count=0,
            target_now_profit_weighted=12.0,
            target_period_profit_weighted=15.0,
            capital_required_total=1500.0,
            roi_now_weighted=0.12,
            roi_period_weighted=0.15,
            total_item_volume_m3=5.0,
            shipping_cost_total=20.0,
            demand_source_summary="adam4eve",
            confidence_score_summary=1.0,
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
            risk_pct_weighted=0.04,
            warning_count=0,
            target_now_profit_weighted=12.0,
            target_period_profit_weighted=15.0,
            capital_required_total=1500.0,
            roi_now_weighted=0.12,
            roi_period_weighted=0.15,
            total_item_volume_m3=5.0,
            shipping_cost_total=20.0,
            demand_source_summary="adam4eve",
            confidence_score_summary=1.0,
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
            risk_pct=0.04,
            warning_flag=False,
            target_now_profit=16.75,
            target_period_profit=21.4,
            capital_required=1200.0,
            roi_now=0.1675,
            roi_period=0.214,
            source_security_status=1.0,
            item_volume_m3=0.01,
            shipping_cost=15.0,
            demand_source="adam4eve",
            confidence_score=1.0,
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
            risk_pct_weighted=0.04,
            warning_count=0,
            target_now_profit_weighted=12.0,
            target_period_profit_weighted=15.0,
            capital_required_total=1500.0,
            roi_now_weighted=0.12,
            roi_period_weighted=0.15,
            total_item_volume_m3=5.0,
            shipping_cost_total=20.0,
            demand_source_summary="adam4eve",
            confidence_score_summary=1.0,
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
            risk_pct=0.04,
            warning_flag=False,
            target_now_profit=16.75,
            target_period_profit=21.4,
            capital_required=1200.0,
            roi_now=0.1675,
            roi_period=0.214,
            source_security_status=1.0,
            item_volume_m3=0.01,
            shipping_cost=15.0,
            demand_source="adam4eve",
            confidence_score=1.0,
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
            risk_pct=0.041666666666666664,
            warning_flag=False,
            target_now_profit=24.08,
            target_period_profit=28.75,
            capital_required=792.0,
            roi_now=0.2736363636363636,
            roi_period=0.32670454545454547,
            source_security_status=1.0,
            item_volume_m3=0.01,
            shipping_cost=12.0,
            demand_source="adam4eve",
            confidence_score=1.0,
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
    assert detail.target_market_sell_orders == []
    assert detail.source_market_sell_orders == []
    assert detail.source_market_buy_orders == []


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
