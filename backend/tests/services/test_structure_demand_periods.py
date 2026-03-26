import pytest
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import Item, StructureDemandPeriod, StructureOrderDelta
from app.services.structures.demand_periods import StructureDemandPeriodService
from tests.db_test_utils import build_test_session


def build_session() -> Session:
    return build_test_session()


def seed_deltas(session: Session) -> None:
    item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add(item)
    session.flush()
    session.add_all(
        [
            StructureOrderDelta(
                structure_id=1022734985679,
                type_id=item.id,
                order_id=1,
                from_snapshot_time=datetime(2026, 3, 16, 10, 0, tzinfo=UTC),
                to_snapshot_time=datetime(2026, 3, 16, 10, 10, tzinfo=UTC),
                old_volume=50,
                new_volume=20,
                delta_volume=-30,
                disappeared=False,
                inferred_trade_side="buy_from_sell",
                inferred_trade_units=30,
                price=100.0,
            ),
            StructureOrderDelta(
                structure_id=1022734985679,
                type_id=item.id,
                order_id=2,
                from_snapshot_time=datetime(2026, 3, 19, 10, 0, tzinfo=UTC),
                to_snapshot_time=datetime(2026, 3, 19, 10, 10, tzinfo=UTC),
                old_volume=40,
                new_volume=15,
                delta_volume=-25,
                disappeared=False,
                inferred_trade_side="sell_to_buy",
                inferred_trade_units=25,
                price=90.0,
            ),
            StructureOrderDelta(
                structure_id=1022734985679,
                type_id=item.id,
                order_id=3,
                from_snapshot_time=datetime(2026, 3, 20, 8, 0, tzinfo=UTC),
                to_snapshot_time=datetime(2026, 3, 20, 8, 10, tzinfo=UTC),
                old_volume=10,
                new_volume=0,
                delta_volume=-10,
                disappeared=True,
                inferred_trade_side=None,
                inferred_trade_units=0,
                price=80.0,
            ),
        ]
    )
    session.commit()


def test_upsert_period_aggregates_deltas_into_structure_demand_period() -> None:
    session = build_session()
    seed_deltas(session)
    item = session.scalar(select(Item).where(Item.type_id == 34))
    assert item is not None

    result = StructureDemandPeriodService().upsert_period(
        session,
        structure_id=1022734985679,
        type_id=item.id,
        period_days=5,
        as_of=datetime(2026, 3, 20, 12, 0, tzinfo=UTC),
    )

    row = result.row
    assert result.created is True
    assert result.delta_count == 3
    assert row.demand_min == pytest.approx(55 / 5)
    assert row.demand_max == pytest.approx(55 / 5)
    assert row.demand_chosen == pytest.approx(55 / 5)
    assert row.coverage_pct == pytest.approx(3 / 5)
    # observation_window = (2026-03-20 08:10 - 2026-03-16 10:10) ≈ 94h → factor = 1.0
    # recency = within 24h → 1.0
    # confidence = 0.6 * 1.0 * 1.0 = 0.6
    assert row.confidence_score == pytest.approx(0.6)


def test_confidence_penalized_when_observation_window_below_72h() -> None:
    session = build_session()
    item = Item(type_id=35, name="Pyerite", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add(item)
    session.flush()
    # Two deltas only 24h apart — observation window < 72h
    session.add_all(
        [
            StructureOrderDelta(
                structure_id=1022734985679,
                type_id=item.id,
                order_id=10,
                from_snapshot_time=datetime(2026, 3, 19, 10, 0, tzinfo=UTC),
                to_snapshot_time=datetime(2026, 3, 19, 10, 10, tzinfo=UTC),
                old_volume=100,
                new_volume=80,
                delta_volume=-20,
                disappeared=False,
                inferred_trade_side="buy_from_sell",
                inferred_trade_units=20,
                price=50.0,
            ),
            StructureOrderDelta(
                structure_id=1022734985679,
                type_id=item.id,
                order_id=11,
                from_snapshot_time=datetime(2026, 3, 20, 10, 0, tzinfo=UTC),
                to_snapshot_time=datetime(2026, 3, 20, 10, 10, tzinfo=UTC),
                old_volume=60,
                new_volume=40,
                delta_volume=-20,
                disappeared=False,
                inferred_trade_side="buy_from_sell",
                inferred_trade_units=20,
                price=50.0,
            ),
        ]
    )
    session.commit()

    result = StructureDemandPeriodService().upsert_period(
        session,
        structure_id=1022734985679,
        type_id=item.id,
        period_days=2,
        as_of=datetime(2026, 3, 20, 12, 0, tzinfo=UTC),
    )
    row = result.row
    # observation_window = 24h → factor = 24/72 = 0.333
    # coverage = 2/2 = 1.0, recency = 1.0
    # confidence = 1.0 * 1.0 * 0.333 ≈ 0.333 — below 0.75 threshold
    assert row.confidence_score == pytest.approx(24 / 72, abs=0.01)
    assert row.confidence_score < 0.75


def test_upsert_period_updates_existing_row_on_rerun() -> None:
    session = build_session()
    seed_deltas(session)
    service = StructureDemandPeriodService()
    item = session.scalar(select(Item).where(Item.type_id == 34))
    assert item is not None

    first = service.upsert_period(
        session,
        structure_id=1022734985679,
        type_id=item.id,
        period_days=7,
        as_of=datetime(2026, 3, 20, 12, 0, tzinfo=UTC),
    )

    session.add(
        StructureOrderDelta(
            structure_id=1022734985679,
            type_id=item.id,
            order_id=4,
            from_snapshot_time=datetime(2026, 3, 20, 9, 0, tzinfo=UTC),
            to_snapshot_time=datetime(2026, 3, 20, 9, 10, tzinfo=UTC),
            old_volume=70,
            new_volume=60,
            delta_volume=-10,
            disappeared=False,
            inferred_trade_side="buy_from_sell",
            inferred_trade_units=10,
            price=95.0,
        )
    )
    session.commit()

    second = service.upsert_period(
        session,
        structure_id=1022734985679,
        type_id=item.id,
        period_days=7,
        as_of=datetime(2026, 3, 20, 12, 0, tzinfo=UTC),
    )

    rows = session.scalars(select(StructureDemandPeriod)).all()

    assert first.created is True
    assert second.created is False
    assert len(rows) == 1
    assert rows[0].id == first.row.id
    assert rows[0].demand_chosen == pytest.approx(65 / 7)
