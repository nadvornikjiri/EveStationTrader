import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class NpcStationDemandPeriodService:
    """Aggregates NPC station order deltas into demand periods.

    Uses a single bulk SQL query to compute buy_from_sell and sell_to_buy
    totals for all (location, type) pairs that have deltas within the
    configured time window.
    """

    def refresh_for_locations(
        self,
        session: Session,
        *,
        target_location_ids: Sequence[int],
        period_days: int,
    ) -> int:
        if not target_location_ids:
            return 0

        computed_at = datetime.now(UTC)
        window_start = computed_at - timedelta(days=period_days)
        yesterday_start = computed_at - timedelta(days=1)

        location_list = list(target_location_ids)

        # Build location IN clause with positional placeholders
        loc_placeholders = ", ".join(f":loc_{i}" for i in range(len(location_list)))
        params: dict[str, object] = {
            "period_days": period_days,
            "window_start": window_start,
            "yesterday_start": yesterday_start,
            "computed_at": computed_at,
        }
        for i, loc_id in enumerate(location_list):
            params[f"loc_{i}"] = loc_id

        session.execute(
            text(
                f"""
                INSERT INTO npc_station_demand_period (
                    location_id,
                    type_id,
                    period_days,
                    buy_from_sell_period,
                    sell_to_buy_period,
                    buy_from_sell_yesterday,
                    sell_to_buy_yesterday,
                    coverage_pct,
                    computed_at
                )
                SELECT
                    d.location_id,
                    d.type_id,
                    :period_days,
                    COALESCE(SUM(CASE WHEN d.inferred_trade_side = 'buy_from_sell' THEN d.inferred_trade_units ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN d.inferred_trade_side = 'sell_to_buy' THEN d.inferred_trade_units ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN d.inferred_trade_side = 'buy_from_sell' AND d.to_snapshot_time >= :yesterday_start THEN d.inferred_trade_units ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN d.inferred_trade_side = 'sell_to_buy' AND d.to_snapshot_time >= :yesterday_start THEN d.inferred_trade_units ELSE 0 END), 0),
                    LEAST(COUNT(DISTINCT DATE(d.to_snapshot_time))::float / GREATEST(:period_days, 1), 1.0),
                    :computed_at
                FROM npc_station_order_deltas d
                WHERE d.location_id IN ({loc_placeholders})
                  AND d.to_snapshot_time >= :window_start
                  AND d.to_snapshot_time <= :computed_at
                GROUP BY d.location_id, d.type_id
                ON CONFLICT (location_id, type_id, period_days) DO UPDATE SET
                    buy_from_sell_period = EXCLUDED.buy_from_sell_period,
                    sell_to_buy_period = EXCLUDED.sell_to_buy_period,
                    buy_from_sell_yesterday = EXCLUDED.buy_from_sell_yesterday,
                    sell_to_buy_yesterday = EXCLUDED.sell_to_buy_yesterday,
                    coverage_pct = EXCLUDED.coverage_pct,
                    computed_at = EXCLUDED.computed_at
                """
            ),
            params,
        )

        # Count the result by querying
        upserted = int(
            session.scalar(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM npc_station_demand_period
                    WHERE location_id IN ({loc_placeholders})
                      AND period_days = :period_days
                    """
                ),
                params,
            )
            or 0
        )
        logger.info(
            "Refreshed %d NPC station demand period rows for %d locations (period=%d days)",
            upserted,
            len(location_list),
            period_days,
        )
        return upserted
