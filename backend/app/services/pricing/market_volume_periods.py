from datetime import UTC, datetime

from sqlalchemy import delete, func, select, text, tuple_
from sqlalchemy.orm import Session

from app.models.all_models import AdamMarketVolumeHistoryDaily, MarketVolumePeriod
from app.services.postgres_copy import copy_rows


class MarketVolumePeriodService:
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
                AdamMarketVolumeHistoryDaily.location_id.label("location_id"),
                AdamMarketVolumeHistoryDaily.type_id.label("type_id"),
                AdamMarketVolumeHistoryDaily.sell_volume_avg.label("sell_volume_avg"),
                func.row_number()
                .over(
                    partition_by=(
                        AdamMarketVolumeHistoryDaily.location_id,
                        AdamMarketVolumeHistoryDaily.type_id,
                    ),
                    order_by=AdamMarketVolumeHistoryDaily.date.desc(),
                )
                .label("row_num"),
            )
            .where(
                tuple_(
                    AdamMarketVolumeHistoryDaily.location_id,
                    AdamMarketVolumeHistoryDaily.type_id,
                ).in_(location_type_keys),
            )
            .subquery()
        )
        history_rows = session.execute(
            select(
                ranked_history.c.location_id,
                ranked_history.c.type_id,
                ranked_history.c.sell_volume_avg,
                ranked_history.c.row_num,
            )
            .where(ranked_history.c.row_num <= max_period_days)
            .order_by(
                ranked_history.c.location_id.asc(),
                ranked_history.c.type_id.asc(),
                ranked_history.c.row_num.asc(),
            )
        ).all()

        history_by_location_and_type: dict[tuple[int, int], list[int]] = {}
        for location_id, type_id, sell_volume_avg, _row_num in history_rows:
            history_by_location_and_type.setdefault((location_id, type_id), []).append(sell_volume_avg)

        stats_by_location_type_and_period: dict[tuple[int, int, int], dict[str, float | int]] = {}
        for (location_id, type_id), rows in history_by_location_and_type.items():
            for period_days in period_days_list:
                sample = rows[:period_days]
                if not sample:
                    continue
                stats_by_location_type_and_period[(location_id, type_id, period_days)] = {
                    "current_sell_volume": sample[0],
                    "period_avg_sell_volume": sum(sample) / len(sample),
                }

        if not stats_by_location_type_and_period:
            session.execute(
                delete(MarketVolumePeriod).where(
                    tuple_(
                        MarketVolumePeriod.location_id,
                        MarketVolumePeriod.type_id,
                    ).in_(location_type_keys),
                    MarketVolumePeriod.period_days.in_(period_days_list),
                )
            )
            session.commit()
            return 0

        session.execute(
            delete(MarketVolumePeriod).where(
                tuple_(
                    MarketVolumePeriod.location_id,
                    MarketVolumePeriod.type_id,
                ).in_(location_type_keys),
                MarketVolumePeriod.period_days.in_(period_days_list),
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
                    "current_sell_volume": stats["current_sell_volume"],
                    "period_avg_sell_volume": stats["period_avg_sell_volume"],
                    "computed_at": computed_at,
                }
            )
        if insert_mappings:
            session.bulk_insert_mappings(MarketVolumePeriod.__mapper__, insert_mappings)
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
            table_name="market_volume_period_refresh_keys",
            columns=("location_id", "type_id"),
            rows=location_type_keys,
        )
        copy_rows(
            session,
            table_name="market_volume_period_refresh_periods",
            columns=("period_days",),
            rows=((period_days,) for period_days in period_days_list),
        )
        session.execute(
            text(
                """
                INSERT INTO market_volume_period_refresh_results (
                    location_id,
                    type_id,
                    period_days,
                    current_sell_volume,
                    period_avg_sell_volume
                )
                WITH ranked_history AS (
                    SELECT
                        daily.location_id,
                        daily.type_id,
                        daily.sell_volume_avg,
                        ROW_NUMBER() OVER (
                            PARTITION BY daily.location_id, daily.type_id
                            ORDER BY daily.date DESC
                        ) AS row_num
                    FROM adam_market_volume_history_daily AS daily
                    JOIN market_volume_period_refresh_keys AS refresh_keys
                      ON refresh_keys.location_id = daily.location_id
                     AND refresh_keys.type_id = daily.type_id
                )
                SELECT
                    ranked_history.location_id,
                    ranked_history.type_id,
                    refresh_periods.period_days,
                    MAX(ranked_history.sell_volume_avg) FILTER (
                        WHERE ranked_history.row_num = 1
                    ) AS current_sell_volume,
                    AVG(ranked_history.sell_volume_avg) FILTER (
                        WHERE ranked_history.row_num <= refresh_periods.period_days
                    ) AS period_avg_sell_volume
                FROM ranked_history
                CROSS JOIN market_volume_period_refresh_periods AS refresh_periods
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
            session.execute(text("SELECT COUNT(*) FROM market_volume_period_refresh_results")).scalar_one()
        )
        session.execute(
            text(
                """
                DELETE FROM market_volume_period AS existing
                USING
                    market_volume_period_refresh_keys AS refresh_keys,
                    market_volume_period_refresh_periods AS refresh_periods
                WHERE existing.location_id = refresh_keys.location_id
                  AND existing.type_id = refresh_keys.type_id
                  AND existing.period_days = refresh_periods.period_days
                """
            )
        )
        session.execute(
            text(
                """
                INSERT INTO market_volume_period (
                    location_id,
                    type_id,
                    period_days,
                    current_sell_volume,
                    period_avg_sell_volume,
                    computed_at
                )
                SELECT
                    refresh_results.location_id,
                    refresh_results.type_id,
                    refresh_results.period_days,
                    refresh_results.current_sell_volume,
                    refresh_results.period_avg_sell_volume,
                    :computed_at
                FROM market_volume_period_refresh_results AS refresh_results
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
                CREATE TEMP TABLE IF NOT EXISTS market_volume_period_refresh_keys (
                    location_id INTEGER NOT NULL,
                    type_id INTEGER NOT NULL,
                    PRIMARY KEY (location_id, type_id)
                ) ON COMMIT DROP
                """
            )
        )
        session.execute(text("TRUNCATE TABLE market_volume_period_refresh_keys"))
        session.execute(
            text(
                """
                CREATE TEMP TABLE IF NOT EXISTS market_volume_period_refresh_periods (
                    period_days INTEGER NOT NULL PRIMARY KEY
                ) ON COMMIT DROP
                """
            )
        )
        session.execute(text("TRUNCATE TABLE market_volume_period_refresh_periods"))
        session.execute(
            text(
                """
                CREATE TEMP TABLE IF NOT EXISTS market_volume_period_refresh_results (
                    location_id INTEGER NOT NULL,
                    type_id INTEGER NOT NULL,
                    period_days INTEGER NOT NULL,
                    current_sell_volume BIGINT NULL,
                    period_avg_sell_volume DOUBLE PRECISION NULL
                ) ON COMMIT DROP
                """
            )
        )
        session.execute(text("TRUNCATE TABLE market_volume_period_refresh_results"))
