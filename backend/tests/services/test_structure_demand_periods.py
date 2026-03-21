import pytest
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.all_models import StructureDemandPeriod, StructureOrderDelta
from app.services.structures.demand_periods import StructureDemandPeriodService


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def seed_deltas(session: Session) -> None:
    session.add_all(
        [
            StructureOrderDelta(
                structure_id=1022734985679,
                type_id=34,
                order_id=1,
                from_snapshot_time=datetime(2026, 3, 18, 10, 0, tzinfo=UTC),
                to_snapshot_time=datetime(2026, 3, 18, 10, 10, tzinfo=UTC),
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
                type_id=34,
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
                type_id=34,
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

    result = StructureDemandPeriodService().upsert_period(
        session,
        structure_id=1022734985679,
        type_id=34,
        period_days=3,
        as_of=datetime(2026, 3, 20, 12, 0, tzinfo=UTC),
    )

    row = result.row
    assert result.created is True
    assert result.delta_count == 3
    assert row.demand_min == pytest.approx(55 / 3)
    assert row.demand_max == pytest.approx(55 / 3)
    assert row.demand_chosen == pytest.approx(55 / 3)
    assert row.coverage_pct == 1.0
    assert row.confidence_score == 1.0


def test_upsert_period_updates_existing_row_on_rerun() -> None:
    session = build_session()
    seed_deltas(session)
    service = StructureDemandPeriodService()

    first = service.upsert_period(
        session,
        structure_id=1022734985679,
        type_id=34,
        period_days=7,
        as_of=datetime(2026, 3, 20, 12, 0, tzinfo=UTC),
    )

    session.add(
        StructureOrderDelta(
            structure_id=1022734985679,
            type_id=34,
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
        type_id=34,
        period_days=7,
        as_of=datetime(2026, 3, 20, 12, 0, tzinfo=UTC),
    )

    rows = session.scalars(select(StructureDemandPeriod)).all()

    assert first.created is True
    assert second.created is False
    assert len(rows) == 1
    assert rows[0].id == first.row.id
    assert rows[0].demand_chosen == pytest.approx(65 / 7)
