from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import DemandSource, LocationType
from app.models.all_models import AdamNpcDemandDaily, Location, MarketDemandResolved, StructureDemandPeriod


@dataclass
class MarketDemandResolutionResult:
    created: bool
    row: MarketDemandResolved | None
    points_used: int


class MarketDemandResolutionService:
    MIN_STRUCTURE_COVERAGE_PCT = 0.75
    MIN_STRUCTURE_CONFIDENCE_SCORE = 0.75

    def upsert_for_location(
        self,
        session: Session,
        *,
        location_id: int,
        type_id: int,
        period_days: int,
    ) -> MarketDemandResolutionResult:
        location = session.get(Location, location_id)
        if location is None:
            raise ValueError(f"location_id {location_id} was not found")

        if location.location_type == LocationType.NPC_STATION.value:
            return self._upsert_npc_from_adam(
                session,
                location_id=location_id,
                type_id=type_id,
                period_days=period_days,
            )

        structure_period = session.scalar(
            select(StructureDemandPeriod).where(
                StructureDemandPeriod.structure_id == location.location_id,
                StructureDemandPeriod.type_id == type_id,
                StructureDemandPeriod.period_days == period_days,
            )
        )
        if (
            structure_period is not None
            and structure_period.coverage_pct >= self.MIN_STRUCTURE_COVERAGE_PCT
            and structure_period.confidence_score >= self.MIN_STRUCTURE_CONFIDENCE_SCORE
        ):
            return self._upsert_row(
                session,
                location_id=location_id,
                type_id=type_id,
                period_days=period_days,
                demand_source=DemandSource.LOCAL_STRUCTURE.value,
                confidence_score=structure_period.confidence_score,
                demand_day=structure_period.demand_chosen,
                points_used=1,
            )

        return self._upsert_structure_fallback(
            session,
            location_id=location_id,
            type_id=type_id,
            period_days=period_days,
        )

    def _upsert_npc_from_adam(
        self,
        session: Session,
        *,
        location_id: int,
        type_id: int,
        period_days: int,
    ) -> MarketDemandResolutionResult:
        history_rows = (
            session.execute(
                select(AdamNpcDemandDaily)
                .where(AdamNpcDemandDaily.location_id == location_id, AdamNpcDemandDaily.type_id == type_id)
                .order_by(AdamNpcDemandDaily.date.desc())
                .limit(period_days)
            )
            .scalars()
            .all()
        )

        if not history_rows:
            return self._delete_existing(session, location_id=location_id, type_id=type_id, period_days=period_days)

        demand_day = sum(row.demand_day for row in history_rows) / len(history_rows)
        return self._upsert_row(
            session,
            location_id=location_id,
            type_id=type_id,
            period_days=period_days,
            demand_source=DemandSource.ADAM4EVE.value,
            confidence_score=1.0,
            demand_day=demand_day,
            points_used=len(history_rows),
        )

    def _upsert_structure_fallback(
        self,
        session: Session,
        *,
        location_id: int,
        type_id: int,
        period_days: int,
    ) -> MarketDemandResolutionResult:
        existing = session.scalar(
            select(MarketDemandResolved).where(
                MarketDemandResolved.location_id == location_id,
                MarketDemandResolved.type_id == type_id,
                MarketDemandResolved.period_days == period_days,
            )
        )
        if existing is None:
            existing = MarketDemandResolved(
                location_id=location_id,
                type_id=type_id,
                period_days=period_days,
                demand_source=DemandSource.REGIONAL_FALLBACK.value,
                confidence_score=0.0,
                demand_day=0.0,
                computed_at=datetime.now(UTC),
            )
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return MarketDemandResolutionResult(created=True, row=existing, points_used=0)

        existing.demand_source = DemandSource.REGIONAL_FALLBACK.value
        existing.confidence_score = 0.0
        existing.demand_day = 0.0
        existing.computed_at = datetime.now(UTC)
        session.commit()
        session.refresh(existing)
        return MarketDemandResolutionResult(created=False, row=existing, points_used=0)

    def _delete_existing(
        self,
        session: Session,
        *,
        location_id: int,
        type_id: int,
        period_days: int,
    ) -> MarketDemandResolutionResult:
        existing = session.scalar(
            select(MarketDemandResolved).where(
                MarketDemandResolved.location_id == location_id,
                MarketDemandResolved.type_id == type_id,
                MarketDemandResolved.period_days == period_days,
            )
        )
        if existing is not None:
            session.delete(existing)
            session.commit()
        return MarketDemandResolutionResult(created=False, row=None, points_used=0)

    def _upsert_row(
        self,
        session: Session,
        *,
        location_id: int,
        type_id: int,
        period_days: int,
        demand_source: str,
        confidence_score: float,
        demand_day: float,
        points_used: int,
    ) -> MarketDemandResolutionResult:
        record = session.scalar(
            select(MarketDemandResolved).where(
                MarketDemandResolved.location_id == location_id,
                MarketDemandResolved.type_id == type_id,
                MarketDemandResolved.period_days == period_days,
            )
        )
        created = record is None
        if record is None:
            record = MarketDemandResolved(
                location_id=location_id,
                type_id=type_id,
                period_days=period_days,
                demand_source=demand_source,
                confidence_score=confidence_score,
                demand_day=demand_day,
                computed_at=datetime.now(UTC),
            )
            session.add(record)
        else:
            record.demand_source = demand_source
            record.confidence_score = confidence_score
            record.demand_day = demand_day
            record.computed_at = datetime.now(UTC)

        session.commit()
        session.refresh(record)
        return MarketDemandResolutionResult(created=created, row=record, points_used=points_used)
