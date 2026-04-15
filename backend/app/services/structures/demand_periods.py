from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import StructureDemandPeriod, StructureOrderDelta


@dataclass
class StructureDemandPeriodResult:
    created: bool
    row: StructureDemandPeriod
    delta_count: int


class StructureDemandPeriodService:
    def upsert_period(
        self,
        session: Session,
        *,
        structure_id: int,
        type_id: int,
        period_days: int,
        as_of: datetime | None = None,
    ) -> StructureDemandPeriodResult:
        computed_at = self._ensure_utc(as_of or datetime.now(UTC))
        window_start = computed_at - timedelta(days=period_days)
        yesterday_start = computed_at - timedelta(days=1)
        deltas = session.scalars(
            select(StructureOrderDelta)
            .where(
                StructureOrderDelta.structure_id == structure_id,
                StructureOrderDelta.type_id == type_id,
                StructureOrderDelta.to_snapshot_time >= window_start,
                StructureOrderDelta.to_snapshot_time <= computed_at,
            )
            .order_by(StructureOrderDelta.to_snapshot_time.desc(), StructureOrderDelta.id.desc())
        ).all()

        buy_from_sell_period = float(
            sum(
                delta.inferred_trade_units
                for delta in deltas
                if delta.inferred_trade_side == "buy_from_sell" and delta.inferred_trade_units > 0
            )
        )
        sell_to_buy_period = float(
            sum(
                delta.inferred_trade_units
                for delta in deltas
                if delta.inferred_trade_side == "sell_to_buy" and delta.inferred_trade_units > 0
            )
        )
        del yesterday_start

        coverage_pct = min(len(deltas) / max(period_days, 1), 1.0)

        record = session.scalar(
            select(StructureDemandPeriod).where(
                StructureDemandPeriod.structure_id == structure_id,
                StructureDemandPeriod.type_id == type_id,
                StructureDemandPeriod.period_days == period_days,
            )
        )
        created = record is None
        if record is None:
            record = StructureDemandPeriod(
                structure_id=structure_id,
                type_id=type_id,
                period_days=period_days,
                computed_at=computed_at,
                buy_from_sell_period=buy_from_sell_period,
                sell_to_buy_period=sell_to_buy_period,
                coverage_pct=coverage_pct,
            )
            session.add(record)
        else:
            record.computed_at = computed_at
            record.buy_from_sell_period = buy_from_sell_period
            record.sell_to_buy_period = sell_to_buy_period
            record.coverage_pct = coverage_pct

        session.commit()
        session.refresh(record)
        return StructureDemandPeriodResult(created=created, row=record, delta_count=len(deltas))

    @staticmethod
    def _ensure_utc(timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)
