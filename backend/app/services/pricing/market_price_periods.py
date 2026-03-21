from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.rules import calculate_risk_pct, calculate_warning_flag
from app.models.all_models import EsiHistoryDaily, Location, MarketPricePeriod


@dataclass
class MarketPriceComputationResult:
    created: bool
    row: MarketPricePeriod | None
    history_points_used: int


class MarketPricePeriodService:
    def upsert_from_history(
        self,
        session: Session,
        *,
        location_id: int,
        type_id: int,
        period_days: int,
        warning_threshold: float = 0.5,
    ) -> MarketPriceComputationResult:
        location = session.get(Location, location_id)
        if location is None:
            raise ValueError(f"location_id {location_id} was not found")

        history_rows = (
            session.execute(
                select(EsiHistoryDaily)
                .where(EsiHistoryDaily.region_id == location.region_id, EsiHistoryDaily.type_id == type_id)
                .order_by(EsiHistoryDaily.date.desc())
                .limit(period_days)
            )
            .scalars()
            .all()
        )

        if not history_rows:
            existing = session.scalar(
                select(MarketPricePeriod).where(
                    MarketPricePeriod.location_id == location_id,
                    MarketPricePeriod.type_id == type_id,
                    MarketPricePeriod.period_days == period_days,
                )
            )
            if existing is not None:
                session.delete(existing)
                session.commit()
            return MarketPriceComputationResult(created=False, row=None, history_points_used=0)

        latest_row = history_rows[0]
        current_price = latest_row.average
        period_avg_price = sum(row.average for row in history_rows) / len(history_rows)
        price_min = min(row.lowest for row in history_rows)
        price_max = max(row.highest for row in history_rows)
        risk_pct = calculate_risk_pct(period_avg_price, current_price)
        warning_flag = calculate_warning_flag(risk_pct, warning_threshold)

        record = session.scalar(
            select(MarketPricePeriod).where(
                MarketPricePeriod.location_id == location_id,
                MarketPricePeriod.type_id == type_id,
                MarketPricePeriod.period_days == period_days,
            )
        )
        created = record is None
        if record is None:
            record = MarketPricePeriod(
                location_id=location_id,
                type_id=type_id,
                period_days=period_days,
                current_price=current_price,
                period_avg_price=period_avg_price,
                price_min=price_min,
                price_max=price_max,
                computed_at=datetime.now(UTC),
                risk_pct=risk_pct,
                warning_flag=warning_flag,
            )
            session.add(record)
        else:
            record.current_price = current_price
            record.period_avg_price = period_avg_price
            record.price_min = price_min
            record.price_max = price_max
            record.computed_at = datetime.now(UTC)
            record.risk_pct = risk_pct
            record.warning_flag = warning_flag

        session.commit()
        session.refresh(record)
        return MarketPriceComputationResult(created=created, row=record, history_points_used=len(history_rows))
