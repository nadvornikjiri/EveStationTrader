import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.models.all_models import NpcStationOrderDelta
from app.services.postgres_copy import copy_rows

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NpcDeltaResult:
    delta_count: int
    stations_processed: int


class NpcStationDeltaService:
    """Computes order book deltas at NPC target stations by comparing
    the current esi_market_orders snapshot with the incoming
    esi_market_orders_valid_stage snapshot.

    Must be called AFTER _materialize_valid_stage() and BEFORE the
    DELETE of old orders in the ESI ingestion flow.
    """

    def compute_and_persist_deltas(
        self,
        session: Session,
        *,
        target_location_ids: Sequence[int],
        snapshot_time: datetime,
    ) -> NpcDeltaResult:
        if not target_location_ids:
            return NpcDeltaResult(delta_count=0, stations_processed=0)

        total_deltas = 0
        for location_id in target_location_ids:
            count = self._process_station(
                session,
                location_id=location_id,
                snapshot_time=snapshot_time,
            )
            total_deltas += count

        return NpcDeltaResult(
            delta_count=total_deltas,
            stations_processed=len(target_location_ids),
        )

    def _process_station(
        self,
        session: Session,
        *,
        location_id: int,
        snapshot_time: datetime,
    ) -> int:
        # Load previous orders sorted by (type_id, order_id)
        prev_rows = session.execute(
            text(
                """
                SELECT type_id, order_id, is_buy_order, price, volume_remain, updated_at
                FROM esi_market_orders
                WHERE location_id = :loc_id
                ORDER BY type_id, order_id
                """
            ),
            {"loc_id": location_id},
        ).all()

        # Load new orders from staging sorted by (type_id, order_id)
        new_rows = session.execute(
            text(
                """
                SELECT type_id, order_id, is_buy_order, price, volume_remain
                FROM esi_market_orders_valid_stage
                WHERE location_id = :loc_id
                ORDER BY type_id, order_id
                """
            ),
            {"loc_id": location_id},
        ).all()

        if not prev_rows:
            logger.info(
                "No previous orders for location_id=%d, skipping delta computation",
                location_id,
            )
            return 0

        # Sorted merge-diff: O(n) single pass
        delta_rows: list[tuple[object, ...]] = []
        pi, ni = 0, 0
        prev_len, new_len = len(prev_rows), len(new_rows)

        while pi < prev_len and ni < new_len:
            p = prev_rows[pi]
            n = new_rows[ni]
            prev_key = (p[0], p[1])  # (type_id, order_id)
            new_key = (n[0], n[1])

            if prev_key == new_key:
                # Same order in both snapshots — check volume change
                old_vol = p[4]  # volume_remain
                new_vol = n[4]
                delta_vol = new_vol - old_vol
                if delta_vol != 0:
                    is_buy = p[2]  # is_buy_order
                    if delta_vol < 0:
                        side = "sell_to_buy" if is_buy else "buy_from_sell"
                        units = -delta_vol
                    else:
                        side = None
                        units = 0
                    from_time = p[5]  # updated_at
                    delta_rows.append((
                        location_id,
                        p[0],       # type_id
                        p[1],       # order_id
                        from_time,
                        snapshot_time,
                        old_vol,
                        new_vol,
                        delta_vol,
                        False,      # disappeared
                        side,
                        units,
                        n[3],       # price (use new price)
                    ))
                pi += 1
                ni += 1
            elif prev_key < new_key:
                # Order disappeared
                is_buy = p[2]
                side = "sell_to_buy" if is_buy else "buy_from_sell"
                units = p[4]
                delta_rows.append((
                    location_id,
                    p[0],       # type_id
                    p[1],       # order_id
                    p[5],       # from_snapshot_time (updated_at)
                    snapshot_time,
                    p[4],       # old_volume
                    0,          # new_volume
                    -p[4],      # delta_volume
                    True,       # disappeared
                    side,
                    units,
                    p[3],       # price
                ))
                pi += 1
            else:
                # New order appeared — skip
                ni += 1

        # Remaining previous orders all disappeared
        while pi < prev_len:
            p = prev_rows[pi]
            is_buy = p[2]
            side = "sell_to_buy" if is_buy else "buy_from_sell"
            units = p[4]
            delta_rows.append((
                location_id,
                p[0], p[1], p[5], snapshot_time,
                p[4], 0, -p[4],
                True, side, units, p[3],
            ))
            pi += 1

        if not delta_rows:
            return 0

        copy_rows(
            session,
            table_name="npc_station_order_deltas",
            columns=(
                "location_id",
                "type_id",
                "order_id",
                "from_snapshot_time",
                "to_snapshot_time",
                "old_volume",
                "new_volume",
                "delta_volume",
                "disappeared",
                "inferred_trade_side",
                "inferred_trade_units",
                "price",
            ),
            rows=delta_rows,
        )

        logger.info(
            "Computed %d deltas for location_id=%d (prev=%d, new=%d)",
            len(delta_rows),
            location_id,
            prev_len,
            new_len,
        )
        return len(delta_rows)

    @staticmethod
    def cleanup_old_deltas(session: Session, *, retention_days: int = 30) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        result = session.execute(
            delete(NpcStationOrderDelta).where(
                NpcStationOrderDelta.to_snapshot_time < cutoff,
            )
        )
        deleted = getattr(result, "rowcount", 0) or 0
        if deleted:
            logger.info("Cleaned up %d old NPC station order deltas (>%d days)", deleted, retention_days)
        return deleted
