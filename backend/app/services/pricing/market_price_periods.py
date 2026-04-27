from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, text, tuple_
from sqlalchemy.orm import Session

from app.models.all_models import AdamMarketPriceHistoryDaily, Location, MarketPricePeriod
from app.services.postgres_copy import copy_rows


@dataclass
class MarketPriceComputationResult:
    created: bool
    row: MarketPricePeriod | None
    history_points_used: int


class MarketPricePeriodService:
    def refresh_touched_periods_from_history(
        self,
        session: Session,
        *,
        location_type_keys: list[tuple[int, int]],
        period_days_list: list[int],
    ) -> int:
        if not location_type_keys or not period_days_list:
            return 0

        normalized_keys = sorted(set(location_type_keys))
        normalized_period_days = sorted(set(period_days_list))
        if session.get_bind().dialect.name == "postgresql":
            return self._refresh_touched_periods_from_history_postgres(
                session,
                location_type_keys=normalized_keys,
                period_days_list=normalized_period_days,
            )
        return self._refresh_touched_periods_from_history_python(
            session,
            location_type_keys=normalized_keys,
            period_days_list=normalized_period_days,
        )

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

        del region_id
        location_type_keys = [
            (location_id, type_id)
            for location_id in sorted(set(location_ids))
            for type_id in sorted(set(type_ids))
        ]
        return self.refresh_touched_periods_from_history(
            session,
            location_type_keys=location_type_keys,
            period_days_list=period_days_list,
        )

    def _refresh_touched_periods_from_history_python(
        self,
        session: Session,
        *,
        location_type_keys: list[tuple[int, int]],
        period_days_list: list[int],
    ) -> int:
        max_period_days = max(period_days_list)
        ranked_history = (
            select(
                AdamMarketPriceHistoryDaily.location_id.label("location_id"),
                AdamMarketPriceHistoryDaily.type_id.label("type_id"),
                AdamMarketPriceHistoryDaily.average.label("average"),
                AdamMarketPriceHistoryDaily.highest.label("highest"),
                AdamMarketPriceHistoryDaily.lowest.label("lowest"),
                func.row_number()
                .over(
                    partition_by=(
                        AdamMarketPriceHistoryDaily.location_id,
                        AdamMarketPriceHistoryDaily.type_id,
                    ),
                    order_by=AdamMarketPriceHistoryDaily.date.desc(),
                )
                .label("row_num"),
            )
            .where(
                tuple_(
                    AdamMarketPriceHistoryDaily.location_id,
                    AdamMarketPriceHistoryDaily.type_id,
                ).in_(location_type_keys),
            )
            .subquery()
        )
        history_rows = session.execute(
            select(
                ranked_history.c.location_id,
                ranked_history.c.type_id,
                ranked_history.c.average,
                ranked_history.c.highest,
                ranked_history.c.lowest,
                ranked_history.c.row_num,
            )
            .where(ranked_history.c.row_num <= max_period_days)
            .order_by(
                ranked_history.c.location_id.asc(),
                ranked_history.c.type_id.asc(),
                ranked_history.c.row_num.asc(),
            )
        ).all()

        history_by_location_and_type: dict[tuple[int, int], list[tuple[float, float, float]]] = {}
        for location_id, type_id, average, highest, lowest, _row_num in history_rows:
            history_by_location_and_type.setdefault((location_id, type_id), []).append((average, highest, lowest))

        stats_by_location_type_and_period: dict[tuple[int, int, int], dict[str, float]] = {}
        for (location_id, type_id), rows in history_by_location_and_type.items():
            for period_days in period_days_list:
                sample = rows[:period_days]
                if not sample:
                    continue
                stats_by_location_type_and_period[(location_id, type_id, period_days)] = {
                    "current_price": sample[0][0],
                    "period_avg_price": sum(row[0] for row in sample) / len(sample),
                    "price_min": min(row[2] for row in sample),
                    "price_max": max(row[1] for row in sample),
                }

        if not stats_by_location_type_and_period:
            session.execute(
                delete(MarketPricePeriod).where(
                    tuple_(
                        MarketPricePeriod.location_id,
                        MarketPricePeriod.type_id,
                    ).in_(location_type_keys),
                    MarketPricePeriod.period_days.in_(period_days_list),
                )
            )
            session.commit()
            return 0

        session.execute(
            delete(MarketPricePeriod).where(
                tuple_(
                    MarketPricePeriod.location_id,
                    MarketPricePeriod.type_id,
                ).in_(location_type_keys),
                MarketPricePeriod.period_days.in_(period_days_list),
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

    def _refresh_touched_periods_from_history_postgres(
        self,
        session: Session,
        *,
        location_type_keys: list[tuple[int, int]],
        period_days_list: list[int],
    ) -> int:
        max_period_days = max(period_days_list)
        self._prepare_refresh_temp_tables(session)
        copy_rows(
            session,
            table_name="market_price_period_refresh_keys",
            columns=("location_id", "type_id"),
            rows=location_type_keys,
        )
        copy_rows(
            session,
            table_name="market_price_period_refresh_periods",
            columns=("period_days",),
            rows=((period_days,) for period_days in period_days_list),
        )
        session.execute(
            text(
                """
                INSERT INTO market_price_period_refresh_results (
                    location_id,
                    type_id,
                    period_days,
                    current_price,
                    period_avg_price,
                    price_min,
                    price_max
                )
                WITH ranked_history AS (
                    SELECT
                        daily.location_id,
                        daily.type_id,
                        daily.average,
                        daily.highest,
                        daily.lowest,
                        ROW_NUMBER() OVER (
                            PARTITION BY daily.location_id, daily.type_id
                            ORDER BY daily.date DESC
                        ) AS row_num
                    FROM adam_market_price_history_daily AS daily
                    JOIN market_price_period_refresh_keys AS refresh_keys
                      ON refresh_keys.location_id = daily.location_id
                     AND refresh_keys.type_id = daily.type_id
                )
                SELECT
                    ranked_history.location_id,
                    ranked_history.type_id,
                    refresh_periods.period_days,
                    MAX(ranked_history.average) FILTER (WHERE ranked_history.row_num = 1) AS current_price,
                    AVG(ranked_history.average) FILTER (
                        WHERE ranked_history.row_num <= refresh_periods.period_days
                    ) AS period_avg_price,
                    MIN(ranked_history.lowest) FILTER (
                        WHERE ranked_history.row_num <= refresh_periods.period_days
                    ) AS price_min,
                    MAX(ranked_history.highest) FILTER (
                        WHERE ranked_history.row_num <= refresh_periods.period_days
                    ) AS price_max
                FROM ranked_history
                CROSS JOIN market_price_period_refresh_periods AS refresh_periods
                WHERE ranked_history.row_num <= :max_period_days
                GROUP BY
                    ranked_history.location_id,
                    ranked_history.type_id,
                    refresh_periods.period_days
                HAVING COUNT(*) FILTER (
                    WHERE ranked_history.row_num <= refresh_periods.period_days
                ) > 0
                """
            ),
            {"max_period_days": max_period_days},
        )
        refreshed_count = int(
            session.execute(text("SELECT COUNT(*) FROM market_price_period_refresh_results")).scalar_one()
        )
        session.execute(
            text(
                """
                DELETE FROM market_price_period AS existing
                USING
                    market_price_period_refresh_keys AS refresh_keys,
                    market_price_period_refresh_periods AS refresh_periods
                WHERE existing.location_id = refresh_keys.location_id
                  AND existing.type_id = refresh_keys.type_id
                  AND existing.period_days = refresh_periods.period_days
                """
            )
        )
        session.execute(
            text(
                """
                INSERT INTO market_price_period (
                    location_id,
                    type_id,
                    period_days,
                    current_price,
                    period_avg_price,
                    price_min,
                    price_max,
                    computed_at
                )
                SELECT
                    refresh_results.location_id,
                    refresh_results.type_id,
                    refresh_results.period_days,
                    refresh_results.current_price,
                    refresh_results.period_avg_price,
                    refresh_results.price_min,
                    refresh_results.price_max,
                    :computed_at
                FROM market_price_period_refresh_results AS refresh_results
                """
            ),
            {"computed_at": datetime.now(UTC)},
        )
        session.commit()
        return refreshed_count

    def _prepare_refresh_temp_tables(self, session: Session) -> None:
        session.execute(
            text(
                """
                CREATE TEMP TABLE IF NOT EXISTS market_price_period_refresh_keys (
                    location_id INTEGER NOT NULL,
                    type_id INTEGER NOT NULL,
                    PRIMARY KEY (location_id, type_id)
                ) ON COMMIT DROP
                """
            )
        )
        session.execute(text("TRUNCATE TABLE market_price_period_refresh_keys"))
        session.execute(
            text(
                """
                CREATE TEMP TABLE IF NOT EXISTS market_price_period_refresh_periods (
                    period_days INTEGER NOT NULL PRIMARY KEY
                ) ON COMMIT DROP
                """
            )
        )
        session.execute(text("TRUNCATE TABLE market_price_period_refresh_periods"))
        session.execute(
            text(
                """
                CREATE TEMP TABLE IF NOT EXISTS market_price_period_refresh_results (
                    location_id INTEGER NOT NULL,
                    type_id INTEGER NOT NULL,
                    period_days INTEGER NOT NULL,
                    current_price DOUBLE PRECISION NULL,
                    period_avg_price DOUBLE PRECISION NULL,
                    price_min DOUBLE PRECISION NULL,
                    price_max DOUBLE PRECISION NULL
                ) ON COMMIT DROP
                """
            )
        )
        session.execute(text("TRUNCATE TABLE market_price_period_refresh_results"))

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
