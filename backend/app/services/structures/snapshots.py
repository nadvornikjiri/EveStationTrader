from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import StructureOrderDelta, StructureSnapshot, StructureSnapshotOrder
from app.services.structures.inference import compute_order_delta


@dataclass
class StructureOrderInput:
    order_id: int
    type_id: int
    is_buy_order: bool
    price: float
    volume_remain: int
    issued: datetime | None = None
    duration: int | None = None


@dataclass
class StructureSnapshotPersistResult:
    snapshot_id: int
    order_count: int


@dataclass
class StructureDeltaPersistResult:
    delta_count: int


class StructureSnapshotService:
    def persist_snapshot(
        self,
        session: Session,
        *,
        structure_id: int,
        snapshot_time: datetime,
        orders: list[StructureOrderInput],
    ) -> StructureSnapshotPersistResult:
        snapshot = StructureSnapshot(
            structure_id=structure_id,
            snapshot_time=self._ensure_utc(snapshot_time),
        )
        session.add(snapshot)
        session.flush()

        for order in orders:
            session.add(
                StructureSnapshotOrder(
                    snapshot_id=snapshot.id,
                    structure_id=structure_id,
                    type_id=order.type_id,
                    order_id=order.order_id,
                    is_buy_order=order.is_buy_order,
                    price=order.price,
                    volume_remain=order.volume_remain,
                    issued=self._ensure_utc(order.issued) if order.issued is not None else None,
                    duration=order.duration,
                )
            )

        session.commit()
        return StructureSnapshotPersistResult(snapshot_id=snapshot.id, order_count=len(orders))

    def persist_deltas_for_snapshots(
        self,
        session: Session,
        *,
        structure_id: int,
        previous_snapshot_id: int,
        current_snapshot_id: int,
    ) -> StructureDeltaPersistResult:
        previous_snapshot = session.get(StructureSnapshot, previous_snapshot_id)
        current_snapshot = session.get(StructureSnapshot, current_snapshot_id)
        if previous_snapshot is None or current_snapshot is None:
            raise ValueError("snapshot ids must exist")
        if previous_snapshot.structure_id != structure_id or current_snapshot.structure_id != structure_id:
            raise ValueError("snapshots must belong to the requested structure")

        previous_orders = {
            order.order_id: order
            for order in session.scalars(
                select(StructureSnapshotOrder).where(StructureSnapshotOrder.snapshot_id == previous_snapshot_id)
            ).all()
        }
        current_orders = {
            order.order_id: order
            for order in session.scalars(
                select(StructureSnapshotOrder).where(StructureSnapshotOrder.snapshot_id == current_snapshot_id)
            ).all()
        }

        delta_count = 0
        for order_id, previous_order in previous_orders.items():
            current_order = current_orders.get(order_id)
            if current_order is not None:
                delta_data = compute_order_delta(previous_order, current_order)
                if delta_data["delta_volume"] == 0:
                    continue
            else:
                delta_data = {
                    "structure_id": structure_id,
                    "type_id": previous_order.type_id,
                    "order_id": previous_order.order_id,
                    "old_volume": previous_order.volume_remain,
                    "new_volume": 0,
                    "delta_volume": -previous_order.volume_remain,
                    "disappeared": True,
                    "inferred_trade_side": None,
                    "inferred_trade_units": 0,
                    "price": previous_order.price,
                }

            session.add(
                StructureOrderDelta(
                    structure_id=structure_id,
                    type_id=delta_data["type_id"],
                    order_id=delta_data["order_id"],
                    from_snapshot_time=self._ensure_utc(previous_snapshot.snapshot_time),
                    to_snapshot_time=self._ensure_utc(current_snapshot.snapshot_time),
                    old_volume=delta_data["old_volume"],
                    new_volume=delta_data["new_volume"],
                    delta_volume=delta_data["delta_volume"],
                    disappeared=delta_data["disappeared"],
                    inferred_trade_side=delta_data["inferred_trade_side"],
                    inferred_trade_units=delta_data["inferred_trade_units"],
                    price=delta_data["price"],
                )
            )
            delta_count += 1

        session.commit()
        return StructureDeltaPersistResult(delta_count=delta_count)

    @staticmethod
    def _ensure_utc(timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)
