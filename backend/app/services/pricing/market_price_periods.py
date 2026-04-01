from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.all_models import AdamMarketPriceHistoryDaily, Location, MarketPricePeriod


@dataclass
class MarketPriceComputationResult:
    created: bool
    row: MarketPricePeriod | None
    history_points_used: int


class MarketPricePeriodService:
    def refresh_region_periods_from_history(
        self,
        session: Session,
        *,
        region_id: int,
        location_ids: list[int],
        type_ids: list[int],
        period_days_list: list[int],
    ) -> int:
        if not location_ids or not type_ids or not period_days_list:
            return 0

        normalized_type_ids = sorted(set(type_ids))
        normalized_period_days = sorted(set(period_days_list))
        max_period_days = max(normalized_period_days)
        history_rows = list(
            session.scalars(
                select(AdamMarketPriceHistoryDaily)
                .where(
                    AdamMarketPriceHistoryDaily.location_id.in_(location_ids),
                    AdamMarketPriceHistoryDaily.type_id.in_(normalized_type_ids),
                )
                .order_by(
                    AdamMarketPriceHistoryDaily.location_id.asc(),
                    AdamMarketPriceHistoryDaily.type_id.asc(),
                    AdamMarketPriceHistoryDaily.date.desc(),
                )
            ).all()
        )

        history_by_location_and_type: dict[tuple[int, int], list[AdamMarketPriceHistoryDaily]] = {}
        for row in history_rows:
            key = (row.location_id, row.type_id)
            rows_for_key = history_by_location_and_type.setdefault(key, [])
            if len(rows_for_key) < max_period_days:
                rows_for_key.append(row)

        stats_by_location_type_and_period: dict[tuple[int, int, int], dict[str, float]] = {}
        for (location_id, type_id), rows in history_by_location_and_type.items():
            for period_days in normalized_period_days:
                sample = rows[:period_days]
                if not sample:
                    continue
                stats_by_location_type_and_period[(location_id, type_id, period_days)] = {
                    "current_price": sample[0].average,
                    "period_avg_price": sum(row.average for row in sample) / len(sample),
                    "price_min": min(row.lowest for row in sample),
                    "price_max": max(row.highest for row in sample),
                }

        if not stats_by_location_type_and_period:
            session.execute(
                delete(MarketPricePeriod).where(
                    MarketPricePeriod.location_id.in_(location_ids),
                    MarketPricePeriod.type_id.in_(normalized_type_ids),
                    MarketPricePeriod.period_days.in_(normalized_period_days),
                )
            )
            session.commit()
            return 0

        session.execute(
            delete(MarketPricePeriod).where(
                MarketPricePeriod.location_id.in_(location_ids),
                MarketPricePeriod.type_id.in_(normalized_type_ids),
                MarketPricePeriod.period_days.in_(normalized_period_days),
            )
        )
        computed_at = datetime.now(UTC)
        insert_mappings: list[dict[str, object]] = []
        for (location_id, type_id, period_days), stats in stats_by_location_type_and_period.items():
            insert_mappings.append(
                {
                    "location_id": location_id,
                    "type_id": type_id,
                    "period_days": period_days,
                    "current_price": stats["current_price"],
                    "period_avg_price": stats["period_avg_price"],
                    "price_min": stats["price_min"],
                    "price_max": stats["price_max"],
                    "computed_at": computed_at,
                }
            )
        if insert_mappings:
            session.bulk_insert_mappings(MarketPricePeriod.__mapper__, insert_mappings)
        session.commit()
        return len(stats_by_location_type_and_period)

    def refresh_region_from_history(
        self,
        session: Session,
        *,
        region_id: int,
        location_ids: list[int],
        type_ids: list[int],
        period_days: int,
    ) -> int:
        return self.refresh_region_periods_from_history(
            session,
            region_id=region_id,
            location_ids=location_ids,
            type_ids=type_ids,
            period_days_list=[period_days],
        )

    def upsert_from_history(
        self,
        session: Session,
        *,
        location_id: int,
        type_id: int,
        period_days: int,
    ) -> MarketPriceComputationResult:
        location = session.get(Location, location_id)
        if location is None:
            raise ValueError(f"location_id {location_id} was not found")

        history_rows = (
            session.execute(
                select(AdamMarketPriceHistoryDaily)
                .where(
                    AdamMarketPriceHistoryDaily.location_id == location_id,
                    AdamMarketPriceHistoryDaily.type_id == type_id,
                )
                .order_by(AdamMarketPriceHistoryDaily.date.desc())
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
            )
            session.add(record)
        else:
            record.current_price = current_price
            record.period_avg_price = period_avg_price
            record.price_min = price_min
            record.price_max = price_max
            record.computed_at = datetime.now(UTC)

        session.commit()
        session.refresh(record)
        return MarketPriceComputationResult(created=created, row=record, history_points_used=len(history_rows))
