from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import Item, StructureOrderDelta, StructureSnapshot, StructureSnapshotOrder
from app.services.structures.snapshots import StructureOrderInput, StructureSnapshotService
from tests.db_test_utils import build_test_session


def build_session() -> Session:
    return build_test_session()


def test_persist_snapshot_stores_snapshot_and_orders() -> None:
    session = build_session()
    service = StructureSnapshotService()
    first_item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    second_item = Item(type_id=35, name="Pyerite", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all([first_item, second_item])
    session.flush()

    result = service.persist_snapshot(
        session,
        structure_id=1022734985679,
        snapshot_time=datetime(2026, 3, 20, 10, 0, tzinfo=UTC),
        orders=[
            StructureOrderInput(order_id=1, type_id=first_item.id, is_buy_order=False, price=100.0, volume_remain=50),
            StructureOrderInput(order_id=2, type_id=second_item.id, is_buy_order=True, price=90.0, volume_remain=20),
        ],
    )

    snapshot = session.get(StructureSnapshot, result.snapshot_id)
    orders = session.scalars(
        select(StructureSnapshotOrder).where(StructureSnapshotOrder.snapshot_id == result.snapshot_id)
    ).all()

    assert snapshot is not None
    assert snapshot.structure_id == 1022734985679
    assert result.order_count == 2
    assert len(orders) == 2
    assert orders[0].structure_id == 1022734985679


def test_persist_deltas_stores_volume_reductions_and_disappeared_orders() -> None:
    session = build_session()
    service = StructureSnapshotService()
    structure_id = 1022734985679
    first_item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    second_item = Item(type_id=35, name="Pyerite", volume_m3=0.01, group_name="Mineral", category_name="Material")
    third_item = Item(type_id=36, name="Mexallon", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all([first_item, second_item, third_item])
    session.flush()
    previous = service.persist_snapshot(
        session,
        structure_id=structure_id,
        snapshot_time=datetime(2026, 3, 20, 10, 0, tzinfo=UTC),
        orders=[
            StructureOrderInput(order_id=1, type_id=first_item.id, is_buy_order=False, price=100.0, volume_remain=50),
            StructureOrderInput(order_id=2, type_id=second_item.id, is_buy_order=True, price=90.0, volume_remain=40),
            StructureOrderInput(order_id=3, type_id=third_item.id, is_buy_order=False, price=80.0, volume_remain=10),
        ],
    )
    current = service.persist_snapshot(
        session,
        structure_id=structure_id,
        snapshot_time=datetime(2026, 3, 20, 10, 10, tzinfo=UTC),
        orders=[
            StructureOrderInput(order_id=1, type_id=first_item.id, is_buy_order=False, price=100.0, volume_remain=20),
            StructureOrderInput(order_id=2, type_id=second_item.id, is_buy_order=True, price=90.0, volume_remain=15),
        ],
    )

    result = service.persist_deltas_for_snapshots(
        session,
        structure_id=structure_id,
        previous_snapshot_id=previous.snapshot_id,
        current_snapshot_id=current.snapshot_id,
    )

    deltas = session.scalars(select(StructureOrderDelta).order_by(StructureOrderDelta.order_id.asc())).all()

    assert result.delta_count == 3
    assert len(deltas) == 3

    sell_delta = deltas[0]
    assert sell_delta.order_id == 1
    assert sell_delta.delta_volume == -30
    assert sell_delta.disappeared is False
    assert sell_delta.inferred_trade_side == "buy_from_sell"
    assert sell_delta.inferred_trade_units == 30

    buy_delta = deltas[1]
    assert buy_delta.order_id == 2
    assert buy_delta.delta_volume == -25
    assert buy_delta.disappeared is False
    assert buy_delta.inferred_trade_side == "sell_to_buy"
    assert buy_delta.inferred_trade_units == 25

    disappeared_delta = deltas[2]
    assert disappeared_delta.order_id == 3
    assert disappeared_delta.disappeared is True
    assert disappeared_delta.new_volume == 0
    assert disappeared_delta.inferred_trade_side is None
    assert disappeared_delta.inferred_trade_units == 0
