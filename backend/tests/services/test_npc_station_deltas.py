from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

from app.models.all_models import (
    EsiMarketOrder,
    Item,
    Location,
    NpcStationOrderDelta,
    Region,
    System,
)
from app.services.npc_stations.deltas import NpcStationDeltaService
from tests.db_test_utils import build_test_session

pytestmark = pytest.mark.integration


def build_session() -> Session:
    return build_test_session()


def seed_foundation(session: Session) -> tuple[int, int, int]:
    """Seed minimal foundation data and return (location_id, item_id_a, item_id_b)."""
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    session.add(system)
    session.flush()

    location = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=system.id,
        region_id=region.id,
        name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    )
    session.add(location)
    session.flush()

    item_a = Item(type_id=92019, name="Federation Defense Booster IV", volume_m3=1.0)
    item_b = Item(type_id=34, name="Tritanium", volume_m3=0.01)
    session.add_all([item_a, item_b])
    session.flush()

    return location.id, item_a.id, item_b.id


def insert_esi_order(
    session: Session,
    *,
    order_id: int,
    location_id: int,
    type_id: int,
    region_id: int,
    system_id: int,
    is_buy_order: bool,
    price: float,
    volume_remain: int,
) -> None:
    session.add(
        EsiMarketOrder(
            order_id=order_id,
            region_id=region_id,
            location_id=location_id,
            type_id=type_id,
            system_id=system_id,
            is_buy_order=is_buy_order,
            price=price,
            volume_total=volume_remain,
            volume_remain=volume_remain,
            min_volume=1,
            order_range="station",
            issued=datetime(2026, 4, 1, tzinfo=UTC),
            duration=90,
        )
    )


def create_valid_stage(session: Session) -> None:
    """Create the temp staging table used by ESI ingestion."""
    session.execute(
        text(
            """
            CREATE TEMP TABLE IF NOT EXISTS esi_market_orders_valid_stage (
                order_id BIGINT NOT NULL,
                region_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                type_id INTEGER NOT NULL,
                system_id INTEGER NOT NULL,
                is_buy_order BOOLEAN NOT NULL,
                price DOUBLE PRECISION NOT NULL,
                volume_total INTEGER NOT NULL,
                volume_remain INTEGER NOT NULL,
                min_volume INTEGER NOT NULL,
                order_range TEXT NOT NULL,
                issued TIMESTAMP WITH TIME ZONE NOT NULL,
                duration INTEGER NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL
            ) ON COMMIT DROP
            """
        )
    )
    session.execute(text("TRUNCATE TABLE esi_market_orders_valid_stage"))


def insert_staged_order(
    session: Session,
    *,
    order_id: int,
    location_id: int,
    type_id: int,
    region_id: int,
    system_id: int,
    is_buy_order: bool,
    price: float,
    volume_remain: int,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO esi_market_orders_valid_stage
                (order_id, region_id, location_id, type_id, system_id,
                 is_buy_order, price, volume_total, volume_remain,
                 min_volume, order_range, issued, duration, updated_at)
            VALUES
                (:order_id, :region_id, :location_id, :type_id, :system_id,
                 :is_buy_order, :price, :volume_remain, :volume_remain,
                 1, 'station', :issued, 90, :updated_at)
            """
        ),
        {
            "order_id": order_id,
            "region_id": region_id,
            "location_id": location_id,
            "type_id": type_id,
            "system_id": system_id,
            "is_buy_order": is_buy_order,
            "price": price,
            "volume_remain": volume_remain,
            "issued": datetime(2026, 4, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 4, 9, 12, 0, tzinfo=UTC),
        },
    )


def test_sell_order_volume_decrease_is_buy_from_sell():
    session = build_session()
    loc_id, item_a, _ = seed_foundation(session)
    region = session.scalars(select(Region)).first()
    system = session.scalars(select(System)).first()

    # Previous: sell order with 100 units
    insert_esi_order(
        session, order_id=1001, location_id=loc_id, type_id=item_a,
        region_id=region.id, system_id=system.id,
        is_buy_order=False, price=12_000_000, volume_remain=100,
    )
    session.commit()

    create_valid_stage(session)
    # New: same order with 80 units (20 sold)
    insert_staged_order(
        session, order_id=1001, location_id=loc_id, type_id=item_a,
        region_id=region.id, system_id=system.id,
        is_buy_order=False, price=12_000_000, volume_remain=80,
    )

    snapshot_time = datetime(2026, 4, 9, 12, 10, tzinfo=UTC)
    result = NpcStationDeltaService().compute_and_persist_deltas(
        session, target_location_ids=[loc_id], snapshot_time=snapshot_time,
    )
    session.commit()

    assert result.delta_count == 1
    deltas = session.scalars(select(NpcStationOrderDelta)).all()
    assert len(deltas) == 1
    d = deltas[0]
    assert d.inferred_trade_side == "buy_from_sell"
    assert d.inferred_trade_units == 20
    assert d.old_volume == 100
    assert d.new_volume == 80
    assert d.delta_volume == -20
    assert d.disappeared is False


def test_buy_order_volume_decrease_is_sell_to_buy():
    session = build_session()
    loc_id, item_a, _ = seed_foundation(session)
    region = session.scalars(select(Region)).first()
    system = session.scalars(select(System)).first()

    insert_esi_order(
        session, order_id=2001, location_id=loc_id, type_id=item_a,
        region_id=region.id, system_id=system.id,
        is_buy_order=True, price=10_000_000, volume_remain=50,
    )
    session.commit()

    create_valid_stage(session)
    insert_staged_order(
        session, order_id=2001, location_id=loc_id, type_id=item_a,
        region_id=region.id, system_id=system.id,
        is_buy_order=True, price=10_000_000, volume_remain=30,
    )

    result = NpcStationDeltaService().compute_and_persist_deltas(
        session, target_location_ids=[loc_id],
        snapshot_time=datetime(2026, 4, 9, 12, 10, tzinfo=UTC),
    )
    session.commit()

    assert result.delta_count == 1
    d = session.scalars(select(NpcStationOrderDelta)).first()
    assert d.inferred_trade_side == "sell_to_buy"
    assert d.inferred_trade_units == 20


def test_disappeared_order_has_no_inference():
    session = build_session()
    loc_id, item_a, _ = seed_foundation(session)
    region = session.scalars(select(Region)).first()
    system = session.scalars(select(System)).first()

    insert_esi_order(
        session, order_id=3001, location_id=loc_id, type_id=item_a,
        region_id=region.id, system_id=system.id,
        is_buy_order=False, price=15_000_000, volume_remain=10,
    )
    session.commit()

    create_valid_stage(session)
    # Don't insert into staging — order disappeared

    result = NpcStationDeltaService().compute_and_persist_deltas(
        session, target_location_ids=[loc_id],
        snapshot_time=datetime(2026, 4, 9, 12, 10, tzinfo=UTC),
    )
    session.commit()

    assert result.delta_count == 1
    d = session.scalars(select(NpcStationOrderDelta)).first()
    assert d.disappeared is True
    assert d.inferred_trade_side is None
    assert d.inferred_trade_units == 0
    assert d.old_volume == 10
    assert d.new_volume == 0


def test_volume_increase_is_skipped():
    session = build_session()
    loc_id, item_a, _ = seed_foundation(session)
    region = session.scalars(select(Region)).first()
    system = session.scalars(select(System)).first()

    insert_esi_order(
        session, order_id=4001, location_id=loc_id, type_id=item_a,
        region_id=region.id, system_id=system.id,
        is_buy_order=True, price=10_000_000, volume_remain=50,
    )
    session.commit()

    create_valid_stage(session)
    # Volume increased (shouldn't happen normally, but test the logic)
    insert_staged_order(
        session, order_id=4001, location_id=loc_id, type_id=item_a,
        region_id=region.id, system_id=system.id,
        is_buy_order=True, price=10_000_000, volume_remain=60,
    )

    result = NpcStationDeltaService().compute_and_persist_deltas(
        session, target_location_ids=[loc_id],
        snapshot_time=datetime(2026, 4, 9, 12, 10, tzinfo=UTC),
    )
    session.commit()

    # Volume increase produces a delta row (delta_volume > 0) but with no trade inference
    deltas = session.scalars(select(NpcStationOrderDelta)).all()
    assert len(deltas) == 1
    d = deltas[0]
    assert d.inferred_trade_side is None
    assert d.inferred_trade_units == 0
    assert d.delta_volume == 10


def test_unchanged_volume_is_skipped():
    session = build_session()
    loc_id, item_a, _ = seed_foundation(session)
    region = session.scalars(select(Region)).first()
    system = session.scalars(select(System)).first()

    insert_esi_order(
        session, order_id=5001, location_id=loc_id, type_id=item_a,
        region_id=region.id, system_id=system.id,
        is_buy_order=False, price=12_000_000, volume_remain=100,
    )
    session.commit()

    create_valid_stage(session)
    insert_staged_order(
        session, order_id=5001, location_id=loc_id, type_id=item_a,
        region_id=region.id, system_id=system.id,
        is_buy_order=False, price=12_000_000, volume_remain=100,
    )

    result = NpcStationDeltaService().compute_and_persist_deltas(
        session, target_location_ids=[loc_id],
        snapshot_time=datetime(2026, 4, 9, 12, 10, tzinfo=UTC),
    )
    session.commit()

    assert result.delta_count == 0
    assert session.scalars(select(NpcStationOrderDelta)).all() == []


def test_sorted_merge_handles_multiple_items():
    """Test that the sorted merge correctly handles orders across multiple item types."""
    session = build_session()
    loc_id, item_a, item_b = seed_foundation(session)
    region = session.scalars(select(Region)).first()
    system = session.scalars(select(System)).first()

    # Item A: sell order, volume decreases
    insert_esi_order(
        session, order_id=6001, location_id=loc_id, type_id=item_a,
        region_id=region.id, system_id=system.id,
        is_buy_order=False, price=12_000_000, volume_remain=100,
    )
    # Item B: buy order, volume decreases
    insert_esi_order(
        session, order_id=6002, location_id=loc_id, type_id=item_b,
        region_id=region.id, system_id=system.id,
        is_buy_order=True, price=5.0, volume_remain=10000,
    )
    session.commit()

    create_valid_stage(session)
    insert_staged_order(
        session, order_id=6001, location_id=loc_id, type_id=item_a,
        region_id=region.id, system_id=system.id,
        is_buy_order=False, price=12_000_000, volume_remain=90,
    )
    insert_staged_order(
        session, order_id=6002, location_id=loc_id, type_id=item_b,
        region_id=region.id, system_id=system.id,
        is_buy_order=True, price=5.0, volume_remain=9500,
    )

    result = NpcStationDeltaService().compute_and_persist_deltas(
        session, target_location_ids=[loc_id],
        snapshot_time=datetime(2026, 4, 9, 12, 10, tzinfo=UTC),
    )
    session.commit()

    assert result.delta_count == 2
    deltas = session.scalars(
        select(NpcStationOrderDelta).order_by(NpcStationOrderDelta.order_id)
    ).all()
    assert deltas[0].inferred_trade_side == "buy_from_sell"
    assert deltas[0].inferred_trade_units == 10
    assert deltas[1].inferred_trade_side == "sell_to_buy"
    assert deltas[1].inferred_trade_units == 500


def test_no_previous_orders_produces_no_deltas():
    session = build_session()
    loc_id, item_a, _ = seed_foundation(session)
    region = session.scalars(select(Region)).first()
    system = session.scalars(select(System)).first()
    session.commit()

    create_valid_stage(session)
    insert_staged_order(
        session, order_id=7001, location_id=loc_id, type_id=item_a,
        region_id=region.id, system_id=system.id,
        is_buy_order=False, price=12_000_000, volume_remain=100,
    )

    result = NpcStationDeltaService().compute_and_persist_deltas(
        session, target_location_ids=[loc_id],
        snapshot_time=datetime(2026, 4, 9, 12, 10, tzinfo=UTC),
    )
    session.commit()

    assert result.delta_count == 0
