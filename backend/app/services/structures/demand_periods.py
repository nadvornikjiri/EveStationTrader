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

        certain_units = float(sum(delta.inferred_trade_units for delta in deltas if not delta.disappeared))
        max_units = float(sum(delta.inferred_trade_units for delta in deltas))
        demand_min = certain_units / period_days
        demand_max = max_units / period_days
        demand_chosen = demand_max if demand_max == demand_min else (demand_min + demand_max) / 2

        coverage_pct = min(len(deltas) / max(period_days, 1), 1.0)
        latest_delta_time = max((self._ensure_utc(delta.to_snapshot_time) for delta in deltas), default=None)
        earliest_delta_time = min((self._ensure_utc(delta.to_snapshot_time) for delta in deltas), default=None)

        # Recency factor: 1.0 if latest delta within 24h, 0.5 if older, 0.0 if none
        if latest_delta_time is None:
            recency_factor = 0.0
        elif latest_delta_time >= computed_at - timedelta(hours=24):
            recency_factor = 1.0
        else:
            recency_factor = 0.5

        # Observation window factor: require >= 72h of observation (MVP gate)
        if earliest_delta_time is not None and latest_delta_time is not None:
            observation_window_hours = (latest_delta_time - earliest_delta_time).total_seconds() / 3600
            observation_factor = min(observation_window_hours / 72.0, 1.0)
        else:
            observation_factor = 0.0

        confidence_score = coverage_pct * recency_factor * observation_factor

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
                demand_min=demand_min,
                demand_max=demand_max,
                demand_chosen=demand_chosen,
                coverage_pct=coverage_pct,
                confidence_score=confidence_score,
            )
            session.add(record)
        else:
            record.computed_at = computed_at
            record.demand_min = demand_min
            record.demand_max = demand_max
            record.demand_chosen = demand_chosen
            record.coverage_pct = coverage_pct
            record.confidence_score = confidence_score

        session.commit()
        session.refresh(record)
        return StructureDemandPeriodResult(created=created, row=record, delta_count=len(deltas))

    @staticmethod
    def _ensure_utc(timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)
