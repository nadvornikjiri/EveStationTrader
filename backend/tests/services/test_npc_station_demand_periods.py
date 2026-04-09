from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import (
    Item,
    Location,
    NpcStationDemandPeriod,
    NpcStationOrderDelta,
    Region,
    System,
)
from app.services.npc_stations.demand_periods import NpcStationDemandPeriodService
from tests.db_test_utils import build_test_session

pytestmark = pytest.mark.integration


def build_session() -> Session:
    return build_test_session()


def seed_foundation(session: Session) -> tuple[int, int, int]:
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
        name="Jita IV",
    )
    session.add(location)
    session.flush()

    item_a = Item(type_id=92019, name="Federation Defense Booster IV", volume_m3=1.0)
    item_b = Item(type_id=34, name="Tritanium", volume_m3=0.01)
    session.add_all([item_a, item_b])
    session.flush()

    return location.id, item_a.id, item_b.id


def add_delta(
    session: Session,
    *,
    location_id: int,
    type_id: int,
    order_id: int,
    trade_side: str | None,
    trade_units: int,
    snapshot_time: datetime,
) -> None:
    session.add(
        NpcStationOrderDelta(
            location_id=location_id,
            type_id=type_id,
            order_id=order_id,
            from_snapshot_time=snapshot_time - timedelta(minutes=10),
            to_snapshot_time=snapshot_time,
            old_volume=100,
            new_volume=100 - trade_units,
            delta_volume=-trade_units,
            disappeared=False,
            inferred_trade_side=trade_side,
            inferred_trade_units=trade_units,
            price=12_000_000,
        )
    )


def test_aggregates_deltas_into_demand_period():
    session = build_session()
    loc_id, item_a, _ = seed_foundation(session)

    now = datetime.now(UTC)
    # Multiple buy_from_sell deltas across different times
    add_delta(session, location_id=loc_id, type_id=item_a, order_id=1001,
              trade_side="buy_from_sell", trade_units=10, snapshot_time=now - timedelta(hours=2))
    add_delta(session, location_id=loc_id, type_id=item_a, order_id=1001,
              trade_side="buy_from_sell", trade_units=5, snapshot_time=now - timedelta(hours=1))
    # One sell_to_buy delta
    add_delta(session, location_id=loc_id, type_id=item_a, order_id=2001,
              trade_side="sell_to_buy", trade_units=8, snapshot_time=now - timedelta(minutes=30))
    session.commit()

    count = NpcStationDemandPeriodService().refresh_for_locations(
        session, target_location_ids=[loc_id], period_days=14,
    )
    session.commit()

    assert count == 1
    period = session.scalars(select(NpcStationDemandPeriod)).first()
    assert period is not None
    assert period.buy_from_sell_period == 15.0  # 10 + 5
    assert period.sell_to_buy_period == 8.0
    assert period.location_id == loc_id
    assert period.type_id == item_a
    assert period.period_days == 14


def test_excludes_deltas_outside_period_window():
    session = build_session()
    loc_id, item_a, _ = seed_foundation(session)

    now = datetime.now(UTC)
    # Delta within window
    add_delta(session, location_id=loc_id, type_id=item_a, order_id=1001,
              trade_side="buy_from_sell", trade_units=20, snapshot_time=now - timedelta(days=5))
    # Delta outside 14-day window
    add_delta(session, location_id=loc_id, type_id=item_a, order_id=1002,
              trade_side="buy_from_sell", trade_units=100, snapshot_time=now - timedelta(days=20))
    session.commit()

    NpcStationDemandPeriodService().refresh_for_locations(
        session, target_location_ids=[loc_id], period_days=14,
    )
    session.commit()

    period = session.scalars(select(NpcStationDemandPeriod)).first()
    assert period is not None
    assert period.buy_from_sell_period == 20.0  # only the in-window delta


def test_handles_multiple_items():
    session = build_session()
    loc_id, item_a, item_b = seed_foundation(session)

    now = datetime.now(UTC)
    add_delta(session, location_id=loc_id, type_id=item_a, order_id=1001,
              trade_side="buy_from_sell", trade_units=15, snapshot_time=now - timedelta(hours=1))
    add_delta(session, location_id=loc_id, type_id=item_b, order_id=2001,
              trade_side="buy_from_sell", trade_units=1000, snapshot_time=now - timedelta(hours=1))
    session.commit()

    count = NpcStationDemandPeriodService().refresh_for_locations(
        session, target_location_ids=[loc_id], period_days=14,
    )
    session.commit()

    assert count == 2
    periods = session.scalars(
        select(NpcStationDemandPeriod).order_by(NpcStationDemandPeriod.type_id)
    ).all()
    assert len(periods) == 2


def test_upsert_updates_existing_period():
    session = build_session()
    loc_id, item_a, _ = seed_foundation(session)

    now = datetime.now(UTC)
    add_delta(session, location_id=loc_id, type_id=item_a, order_id=1001,
              trade_side="buy_from_sell", trade_units=10, snapshot_time=now - timedelta(hours=2))
    session.commit()

    NpcStationDemandPeriodService().refresh_for_locations(
        session, target_location_ids=[loc_id], period_days=14,
    )
    session.commit()

    period = session.scalars(select(NpcStationDemandPeriod)).first()
    assert period.buy_from_sell_period == 10.0

    # Add more deltas and refresh again
    add_delta(session, location_id=loc_id, type_id=item_a, order_id=1001,
              trade_side="buy_from_sell", trade_units=25, snapshot_time=now - timedelta(hours=1))
    session.commit()

    NpcStationDemandPeriodService().refresh_for_locations(
        session, target_location_ids=[loc_id], period_days=14,
    )
    session.commit()
    session.expire_all()

    periods = session.scalars(select(NpcStationDemandPeriod)).all()
    assert len(periods) == 1  # upserted, not duplicated
    assert periods[0].buy_from_sell_period == 35.0  # 10 + 25
