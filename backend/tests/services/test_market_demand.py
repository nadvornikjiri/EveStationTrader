import csv
from datetime import date, timedelta
from typing import TypedDict

import pytest
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.models.all_models import (
    AdamMarketOrdersTradeRaw,
    EsiHistoryDaily,
    Item,
    Location,
    MarketDemandResolved,
    Region,
    StructureDemandPeriod,
    System,
)
from app.services.adam4eve.ingestion import AdamMarketOrdersIngestionService
from app.services.demand.market_demand import MarketDemandResolutionService
from tests.db_test_utils import build_test_session

pytestmark = pytest.mark.integration


class CsvDemandRow(TypedDict):
    scan_date: date
    is_buy_order: int
    amount: float


def build_session() -> Session:
    return build_test_session()


def seed_locations_and_item(session: Session) -> tuple[int, int, int]:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    session.add(system)
    session.flush()

    npc_location = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=system.id,
        region_id=region.id,
        name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    )
    structure_location = Location(
        location_id=1022734985679,
        location_type="structure",
        system_id=system.id,
        region_id=region.id,
        name="Perimeter Market Keepstar",
    )
    item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all([npc_location, structure_location, item])
    session.commit()
    return npc_location.id, structure_location.id, item.id


def add_adam_raw_history(
    session: Session,
    *,
    location_id: int,
    values: list[tuple[str, int, float]],
) -> None:
    rows = [
        {
            "location_id": 60003760,
            "region_id": 10000002,
            "type_id": 34,
            "is_buy_order": is_buy_order,
            "has_gone": 0,
            "scanDate": date.fromisoformat(row_date),
            "amount": amount,
            "high": 5.0,
            "low": 5.0,
            "avg": 5.0,
            "orderNum": 1,
            "iskValue": amount * 5.0,
        }
        for row_date, is_buy_order, amount in values
    ]
    del location_id
    session.execute(insert(AdamMarketOrdersTradeRaw), rows)
    session.commit()


def add_esi_history(
    session: Session,
    *,
    region_id: int,
    type_id: int,
    values: list[tuple[str, float, float, float, int]],
) -> None:
    resolved_region_id = session.scalar(
        select(Region.id).where((Region.id == region_id) | (Region.region_id == region_id))
    )
    resolved_type_id = session.scalar(
        select(Item.id).where((Item.id == type_id) | (Item.type_id == type_id))
    )
    assert resolved_region_id is not None
    assert resolved_type_id is not None
    session.execute(
        insert(EsiHistoryDaily),
        [
            {
                "region_id": resolved_region_id,
                "type_id": resolved_type_id,
                "date": date.fromisoformat(row_date),
                "average": average,
                "highest": highest,
                "lowest": lowest,
                "order_count": 1,
                "volume": volume,
            }
            for row_date, average, highest, lowest, volume in values
        ],
    )
    session.commit()


def test_upsert_market_demand_uses_adam4eve_for_npc_targets() -> None:
    session = build_session()
    npc_location_id, _structure_location_id, item_id = seed_locations_and_item(session)
    add_adam_raw_history(
        session,
        location_id=npc_location_id,
        values=[
            ("2026-03-20", 0, 12.0),
            ("2026-03-20", 1, 3.0),
            ("2026-03-19", 0, 18.0),
            ("2026-03-19", 1, 4.0),
        ],
    )

    result = MarketDemandResolutionService().upsert_for_location(
        session,
        location_id=npc_location_id,
        type_id=item_id,
        period_days=2,
    )

    assert result.created is True
    assert result.points_used == 2
    assert result.row is not None
    assert result.row.demand_source == "adam4eve"
    assert result.row.buy_from_sell_period == 30.0
    assert result.row.sell_to_buy_period == 7.0
    assert result.row.buy_from_sell_yesterday == 12.0
    assert result.row.sell_to_buy_yesterday == 3.0
    assert result.row.esi_live_valid_days is None
    assert result.row.esi_live_buy_from_sell_ratio_period is None
    assert result.row.esi_live_buy_from_sell_ratio_yesterday is None
    assert result.row.esi_live_fallback_reason is None


def test_upsert_row_result_has_correct_fields_without_refresh() -> None:
    session = build_session()
    npc_location_id, _structure_location_id, item_id = seed_locations_and_item(session)
    add_adam_raw_history(
        session,
        location_id=npc_location_id,
        values=[
            ("2026-03-20", 0, 12.0),
            ("2026-03-20", 1, 3.0),
        ],
    )
    add_esi_history(
        session,
        region_id=10000002,
        type_id=34,
        values=[("2026-03-20", 108.0, 110.0, 100.0, 10)],
    )

    result = MarketDemandResolutionService().upsert_for_location(
        session,
        location_id=npc_location_id,
        type_id=item_id,
        period_days=1,
    )

    assert result.row is not None
    assert result.row.buy_from_sell_period == 12.0
    assert result.row.demand_source == "adam4eve"
    assert result.row.computed_at is not None


def test_upsert_market_demand_deletes_stale_npc_row_when_no_history_exists() -> None:
    session = build_session()
    npc_location_id, _structure_location_id, item_id = seed_locations_and_item(session)
    session.add(
        MarketDemandResolved(
            location_id=npc_location_id,
            type_id=item_id,
            period_days=14,
            demand_source="adam4eve",
            buy_from_sell_period=12.0,
            sell_to_buy_period=3.0,
            buy_from_sell_yesterday=12.0,
            sell_to_buy_yesterday=3.0,
        )
    )
    session.commit()

    result = MarketDemandResolutionService().upsert_for_location(
        session,
        location_id=npc_location_id,
        type_id=item_id,
        period_days=14,
    )

    assert result.created is False
    assert result.row is None
    assert result.points_used == 0
    assert session.query(MarketDemandResolved).count() == 0


def test_upsert_market_demand_uses_local_structure_period_when_period_exists() -> None:
    session = build_session()
    _npc_location_id, structure_location_id, item_id = seed_locations_and_item(session)
    session.add(
        StructureDemandPeriod(
            structure_id=1022734985679,
            type_id=item_id,
            period_days=14,
            buy_from_sell_period=20.0,
            sell_to_buy_period=8.0,
            buy_from_sell_yesterday=4.0,
            sell_to_buy_yesterday=2.0,
            coverage_pct=0.8,
        )
    )
    session.commit()

    result = MarketDemandResolutionService().upsert_for_location(
        session,
        location_id=structure_location_id,
        type_id=item_id,
        period_days=14,
    )

    assert result.row is not None
    assert result.points_used == 1
    assert result.row.demand_source == "local_structure"
    assert result.row.buy_from_sell_period == 20.0
    assert result.row.sell_to_buy_period == 8.0
    assert result.row.buy_from_sell_yesterday == 4.0
    assert result.row.sell_to_buy_yesterday == 2.0
    assert result.row.esi_live_valid_days is None


def test_upsert_market_demand_falls_back_for_structure_when_period_is_missing() -> None:
    session = build_session()
    _npc_location_id, structure_location_id, item_id = seed_locations_and_item(session)

    result = MarketDemandResolutionService().upsert_for_location(
        session,
        location_id=structure_location_id,
        type_id=item_id,
        period_days=14,
    )

    assert result.row is not None
    assert result.points_used == 0
    assert result.row.demand_source == "regional_fallback"
    assert result.row.buy_from_sell_period == 0.0
    assert result.row.sell_to_buy_period == 0.0
    assert result.row.buy_from_sell_yesterday == 0.0
    assert result.row.sell_to_buy_yesterday == 0.0
    assert result.row.esi_live_valid_days == 0
    assert result.row.esi_live_fallback_reason == "missing_structure_period_and_esi_history"


def test_upsert_market_demand_uses_esi_live_fallback_when_adam_resolves_to_zero() -> None:
    session = build_session()
    npc_location_id, _structure_location_id, item_id = seed_locations_and_item(session)
    add_esi_history(
        session,
        region_id=10000002,
        type_id=34,
        values=[
            ("2026-03-20", 108.0, 110.0, 100.0, 10),
            ("2026-03-19", 101.0, 110.0, 100.0, 20),
        ],
    )

    result = MarketDemandResolutionService().upsert_for_location(
        session,
        location_id=npc_location_id,
        type_id=item_id,
        period_days=2,
    )

    assert result.row is not None
    assert result.points_used == 2
    assert result.row.demand_source == "esi_live"
    assert result.row.buy_from_sell_yesterday == pytest.approx(8.0)
    assert result.row.sell_to_buy_yesterday == pytest.approx(2.0)
    assert result.row.buy_from_sell_period == pytest.approx(10.0)
    assert result.row.sell_to_buy_period == pytest.approx(20.0)
    assert result.row.esi_live_valid_days == 2
    assert result.row.esi_live_buy_from_sell_ratio_yesterday == pytest.approx(0.8)
    assert result.row.esi_live_buy_from_sell_ratio_period == pytest.approx(10.0 / 30.0)
    assert result.row.esi_live_fallback_reason == "adam_zero_buy_from_sell"


def test_upsert_market_demand_uses_esi_live_for_structures_without_local_period() -> None:
    session = build_session()
    _npc_location_id, structure_location_id, item_id = seed_locations_and_item(session)
    add_esi_history(
        session,
        region_id=10000002,
        type_id=34,
        values=[
            ("2026-03-20", 105.0, 110.0, 100.0, 10),
            ("2026-03-19", 102.0, 110.0, 100.0, 5),
        ],
    )

    result = MarketDemandResolutionService().upsert_for_location(
        session,
        location_id=structure_location_id,
        type_id=item_id,
        period_days=2,
    )

    assert result.row is not None
    assert result.row.demand_source == "esi_live"
    assert result.row.buy_from_sell_yesterday == pytest.approx(5.0)
    assert result.row.sell_to_buy_yesterday == pytest.approx(5.0)
    assert result.row.esi_live_fallback_reason == "missing_structure_period"


def test_upsert_market_demand_esi_live_uses_half_split_when_daily_range_is_flat() -> None:
    session = build_session()
    npc_location_id, _structure_location_id, item_id = seed_locations_and_item(session)
    add_esi_history(
        session,
        region_id=10000002,
        type_id=34,
        values=[("2026-03-20", 100.0, 100.0, 100.0, 12)],
    )

    result = MarketDemandResolutionService().upsert_for_location(
        session,
        location_id=npc_location_id,
        type_id=item_id,
        period_days=1,
    )

    assert result.row is not None
    assert result.row.demand_source == "esi_live"
    assert result.row.buy_from_sell_yesterday == pytest.approx(6.0)
    assert result.row.sell_to_buy_yesterday == pytest.approx(6.0)
    assert result.row.esi_live_buy_from_sell_ratio_yesterday == pytest.approx(0.5)


def test_upsert_market_demand_esi_live_keeps_yesterday_zero_when_latest_day_has_no_volume() -> None:
    session = build_session()
    npc_location_id, _structure_location_id, item_id = seed_locations_and_item(session)
    add_esi_history(
        session,
        region_id=10000002,
        type_id=34,
        values=[
            ("2026-03-20", 105.0, 110.0, 100.0, 0),
            ("2026-03-19", 109.0, 110.0, 100.0, 10),
        ],
    )

    result = MarketDemandResolutionService().upsert_for_location(
        session,
        location_id=npc_location_id,
        type_id=item_id,
        period_days=2,
    )

    assert result.row is not None
    assert result.row.demand_source == "esi_live"
    assert result.row.buy_from_sell_yesterday == 0.0
    assert result.row.sell_to_buy_yesterday == 0.0
    assert result.row.buy_from_sell_period == pytest.approx(9.0)
    assert result.row.sell_to_buy_period == pytest.approx(1.0)
    assert result.row.esi_live_buy_from_sell_ratio_yesterday is None
    assert result.row.esi_live_valid_days == 1


def test_refresh_npc_keys_from_adam_aggregates_all_requested_keys_in_bulk() -> None:
    session = build_session()
    npc_location_id, _structure_location_id, item_id = seed_locations_and_item(session)
    extra_item = Item(type_id=35, name="Pyerite", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add(extra_item)
    session.flush()
    extra_item_id = extra_item.id
    add_adam_raw_history(
        session,
        location_id=npc_location_id,
        values=[
            ("2026-03-20", 0, 12.0),
            ("2026-03-20", 1, 3.0),
            ("2026-03-19", 0, 18.0),
            ("2026-03-19", 1, 4.0),
        ],
    )
    session.execute(
        insert(AdamMarketOrdersTradeRaw),
        [
            {
                "location_id": 60003760,
                "region_id": 10000002,
                "type_id": 35,
                "is_buy_order": 0,
                "has_gone": 0,
                "scanDate": date(2026, 3, 20),
                "amount": 7.0,
                "high": 5.0,
                "low": 5.0,
                "avg": 5.0,
                "orderNum": 1,
                "iskValue": 35.0,
            }
        ],
    )
    session.commit()

    refreshed = MarketDemandResolutionService().refresh_npc_keys_from_adam(
        session,
        demand_keys=[(npc_location_id, item_id), (npc_location_id, extra_item_id)],
        period_days=2,
    )
    rows = session.scalars(
        select(MarketDemandResolved)
        .where(MarketDemandResolved.period_days == 2)
        .order_by(MarketDemandResolved.type_id.asc())
    ).all()

    assert refreshed == 2
    assert len(rows) == 2
    assert rows[0].type_id == item_id
    assert rows[0].buy_from_sell_period == 30.0
    assert rows[0].sell_to_buy_period == 7.0
    assert rows[0].buy_from_sell_yesterday == 12.0
    assert rows[0].sell_to_buy_yesterday == 3.0
    assert rows[1].type_id == extra_item_id
    assert rows[1].buy_from_sell_period == 7.0
    assert rows[1].sell_to_buy_period == 0.0


def test_refresh_npc_keys_from_adam_deletes_stale_rows_for_keys_without_history() -> None:
    session = build_session()
    npc_location_id, _structure_location_id, item_id = seed_locations_and_item(session)
    session.add(
        MarketDemandResolved(
            location_id=npc_location_id,
            type_id=item_id,
            period_days=14,
            demand_source="adam4eve",
            buy_from_sell_period=99.0,
            sell_to_buy_period=11.0,
            buy_from_sell_yesterday=33.0,
            sell_to_buy_yesterday=5.0,
        )
    )
    session.commit()

    refreshed = MarketDemandResolutionService().refresh_npc_keys_from_adam(
        session,
        demand_keys=[(npc_location_id, item_id)],
        period_days=14,
    )

    assert refreshed == 0
    assert session.query(MarketDemandResolved).count() == 0


def test_refresh_npc_keys_from_adam_matches_manual_csv_rollup(tmp_path) -> None:
    session = build_session()
    npc_location_id, _structure_location_id, item_id = seed_locations_and_item(session)
    csv_path = tmp_path / "marketOrderTrades_weekly_2026-12.csv"
    csv_path.write_text(
        "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
        "60003760;10000002;34;1;0;2026-03-10;999.0;5.0;5.0;5.0;1;4995.0\n"
        "60003760;10000002;34;0;0;2026-03-12;12.0;5.0;5.0;5.0;1;60.0\n"
        "60003760;10000002;34;1;0;2026-03-12;3.0;5.0;5.0;5.0;1;15.0\n"
        "60003760;10000002;34;0;0;2026-03-20;18.0;5.0;5.0;5.0;1;90.0\n"
        "60003760;10000002;34;1;0;2026-03-20;4.0;5.0;5.0;5.0;1;20.0\n"
        "60003760;10000002;34;0;0;2026-03-25;5.0;5.0;5.0;5.0;1;25.0\n"
        "60003760;10000002;34;1;0;2026-03-25;7.0;5.0;5.0;5.0;1;35.0\n",
        encoding="utf-8",
    )

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        relevant_rows: list[CsvDemandRow] = [
            {
                "scan_date": date.fromisoformat(row["scanDate"]),
                "is_buy_order": int(row["is_buy_order"]),
                "amount": float(row["amount"]),
            }
            for row in reader
            if int(row["location_id"]) == 60003760 and int(row["type_id"]) == 34
        ]

    latest_scan_date = max(row["scan_date"] for row in relevant_rows)
    window_start = latest_scan_date - timedelta(days=13)
    window_rows = [
        row
        for row in relevant_rows
        if window_start <= row["scan_date"] <= latest_scan_date
    ]

    expected_buy_period = sum(row["amount"] for row in window_rows if row["is_buy_order"] == 0)
    expected_sell_period = sum(row["amount"] for row in window_rows if row["is_buy_order"] == 1)
    expected_buy_latest = sum(
        row["amount"]
        for row in window_rows
        if row["is_buy_order"] == 0 and row["scan_date"] == latest_scan_date
    )
    expected_sell_latest = sum(
        row["amount"]
        for row in window_rows
        if row["is_buy_order"] == 1 and row["scan_date"] == latest_scan_date
    )

    AdamMarketOrdersIngestionService().ingest_market_orders_export(session, csv_file_path=csv_path)

    refreshed = MarketDemandResolutionService().refresh_npc_keys_from_adam(
        session,
        demand_keys=[(npc_location_id, item_id)],
        period_days=14,
    )
    row = session.scalar(
        select(MarketDemandResolved).where(
            MarketDemandResolved.location_id == npc_location_id,
            MarketDemandResolved.type_id == item_id,
            MarketDemandResolved.period_days == 14,
        )
    )

    assert refreshed == 1
    assert row is not None
    assert row.buy_from_sell_period == expected_buy_period
    assert row.sell_to_buy_period == expected_sell_period
    assert row.buy_from_sell_yesterday == expected_buy_latest
    assert row.sell_to_buy_yesterday == expected_sell_latest
