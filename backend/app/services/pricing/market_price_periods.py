from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.all_models import EsiHistoryDaily, Location, MarketPricePeriod


@dataclass
class MarketPriceComputationResult:
    created: bool
    row: MarketPricePeriod | None
    history_points_used: int


class MarketPricePeriodService:
    def refresh_region_from_history(
        self,
        session: Session,
        *,
        region_id: int,
        location_ids: list[int],
        type_ids: list[int],
        period_days: int,
    ) -> int:
        if not location_ids or not type_ids:
            return 0

        normalized_type_ids = sorted(set(type_ids))
        history_rows = list(
            session.scalars(
                select(EsiHistoryDaily)
                .where(
                    EsiHistoryDaily.region_id == region_id,
                    EsiHistoryDaily.type_id.in_(normalized_type_ids),
                )
                .order_by(EsiHistoryDaily.type_id.asc(), EsiHistoryDaily.date.desc())
            ).all()
        )

        history_by_type: dict[int, list[EsiHistoryDaily]] = {}
        for row in history_rows:
            rows_for_type = history_by_type.setdefault(row.type_id, [])
            if len(rows_for_type) < period_days:
                rows_for_type.append(row)

        stats_by_type = {
            type_id: {
                "current_price": rows[0].average,
                "period_avg_price": sum(row.average for row in rows) / len(rows),
                "price_min": min(row.lowest for row in rows),
                "price_max": max(row.highest for row in rows),
            }
            for type_id, rows in history_by_type.items()
            if rows
        }
        if not stats_by_type:
            session.execute(
                delete(MarketPricePeriod).where(
                    MarketPricePeriod.location_id.in_(location_ids),
                    MarketPricePeriod.type_id.in_(normalized_type_ids),
                    MarketPricePeriod.period_days == period_days,
                )
            )
            session.commit()
            return 0

        stale_type_ids = [type_id for type_id in normalized_type_ids if type_id not in stats_by_type]
        if stale_type_ids:
            session.execute(
                delete(MarketPricePeriod).where(
                    MarketPricePeriod.location_id.in_(location_ids),
                    MarketPricePeriod.type_id.in_(stale_type_ids),
                    MarketPricePeriod.period_days == period_days,
                )
            )

        existing_rows = session.execute(
            select(MarketPricePeriod.id, MarketPricePeriod.location_id, MarketPricePeriod.type_id).where(
                MarketPricePeriod.location_id.in_(location_ids),
                MarketPricePeriod.type_id.in_(list(stats_by_type)),
                MarketPricePeriod.period_days == period_days,
            )
        ).all()
        existing_by_key = {(row.location_id, row.type_id): row.id for row in existing_rows}

        computed_at = datetime.now(UTC)
        update_mappings: list[dict[str, object]] = []
        insert_mappings: list[dict[str, object]] = []
        for location_id in location_ids:
            for type_id, stats in stats_by_type.items():
                mapping = {
                    "location_id": location_id,
                    "type_id": type_id,
                    "period_days": period_days,
                    "current_price": stats["current_price"],
                    "period_avg_price": stats["period_avg_price"],
                    "price_min": stats["price_min"],
                    "price_max": stats["price_max"],
                    "computed_at": computed_at,
                }
                existing_id = existing_by_key.get((location_id, type_id))
                if existing_id is None:
                    insert_mappings.append(mapping)
                else:
                    update_mappings.append({"id": existing_id, **mapping})

        if update_mappings:
            session.bulk_update_mappings(MarketPricePeriod.__mapper__, update_mappings)
        if insert_mappings:
            session.bulk_insert_mappings(MarketPricePeriod.__mapper__, insert_mappings)
        session.commit()
        return len(location_ids) * len(stats_by_type)

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
