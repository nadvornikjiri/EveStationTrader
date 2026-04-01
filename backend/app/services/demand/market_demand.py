from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.domain.enums import DemandSource, LocationType
from app.models.all_models import AdamMarketOrdersTradeRaw, Item, Location, MarketDemandResolved, StructureDemandPeriod
from app.services.postgres_copy import copy_rows


@dataclass
class MarketDemandResolutionResult:
    created: bool
    row: MarketDemandResolved | None
    points_used: int


class MarketDemandResolutionService:
    def refresh_npc_keys_from_adam(
        self,
        session: Session,
        *,
        demand_keys: list[tuple[int, int]],
        period_days: int,
    ) -> int:
        if not demand_keys:
            return 0

        if session.get_bind().dialect.name != "postgresql":
            refreshed_count = 0
            for location_id, type_id in dict.fromkeys(demand_keys):
                result = self.upsert_for_location(
                    session,
                    location_id=location_id,
                    type_id=type_id,
                    period_days=period_days,
                )
                if result.row is not None:
                    refreshed_count += 1
            return refreshed_count

        normalized_keys = list(dict.fromkeys(demand_keys))
        self._prepare_npc_refresh_key_table(session, demand_keys=normalized_keys)
        window_days = max(period_days - 1, 0)
        session.execute(
            text(
                """
                DELETE FROM market_demand_resolved AS resolved
                USING adam_npc_demand_refresh_keys AS keys
                LEFT JOIN (
                    WITH latest_per_key AS (
                        SELECT
                            keys.location_id,
                            keys.type_id,
                            locations.location_id AS external_location_id,
                            items.type_id AS external_type_id,
                            MAX(raw."scanDate") AS latest_scan_date
                        FROM adam_npc_demand_refresh_keys AS keys
                        JOIN locations ON locations.id = keys.location_id
                        JOIN items ON items.id = keys.type_id
                        LEFT JOIN adam_market_orders_trade_raw AS raw
                          ON raw.location_id = locations.location_id
                         AND raw.type_id = items.type_id
                        GROUP BY keys.location_id, keys.type_id, locations.location_id, items.type_id
                    )
                    SELECT latest_per_key.location_id, latest_per_key.type_id
                    FROM latest_per_key
                    WHERE latest_per_key.latest_scan_date IS NOT NULL
                ) AS aggregated
                  ON aggregated.location_id = keys.location_id
                 AND aggregated.type_id = keys.type_id
                WHERE resolved.location_id = keys.location_id
                  AND resolved.type_id = keys.type_id
                  AND resolved.period_days = :period_days
                  AND aggregated.location_id IS NULL
                """
            ),
            {"period_days": period_days},
        )
        session.execute(
            text(
                """
                INSERT INTO market_demand_resolved (
                    location_id,
                    type_id,
                    period_days,
                    demand_source,
                    buy_from_sell_period,
                    sell_to_buy_period,
                    buy_from_sell_yesterday,
                    sell_to_buy_yesterday,
                    computed_at
                )
                WITH latest_per_key AS (
                    SELECT
                        keys.location_id,
                        keys.type_id,
                        locations.location_id AS external_location_id,
                        items.type_id AS external_type_id,
                        MAX(raw."scanDate") AS latest_scan_date
                    FROM adam_npc_demand_refresh_keys AS keys
                    JOIN locations ON locations.id = keys.location_id
                    JOIN items ON items.id = keys.type_id
                    LEFT JOIN adam_market_orders_trade_raw AS raw
                      ON raw.location_id = locations.location_id
                     AND raw.type_id = items.type_id
                    GROUP BY keys.location_id, keys.type_id, locations.location_id, items.type_id
                ),
                aggregated AS (
                    SELECT
                        latest_per_key.location_id,
                        latest_per_key.type_id,
                        SUM(CASE WHEN raw.is_buy_order = 0 THEN raw.amount ELSE 0 END) AS buy_from_sell_period,
                        SUM(CASE WHEN raw.is_buy_order = 1 THEN raw.amount ELSE 0 END) AS sell_to_buy_period,
                        SUM(
                            CASE
                                WHEN raw.is_buy_order = 0 AND raw."scanDate" = latest_per_key.latest_scan_date
                                THEN raw.amount
                                ELSE 0
                            END
                        ) AS buy_from_sell_yesterday,
                        SUM(
                            CASE
                                WHEN raw.is_buy_order = 1 AND raw."scanDate" = latest_per_key.latest_scan_date
                                THEN raw.amount
                                ELSE 0
                            END
                        ) AS sell_to_buy_yesterday,
                        COUNT(DISTINCT raw."scanDate") AS points_used
                    FROM latest_per_key
                    JOIN adam_market_orders_trade_raw AS raw
                      ON raw.location_id = latest_per_key.external_location_id
                     AND raw.type_id = latest_per_key.external_type_id
                     AND raw."scanDate" >= latest_per_key.latest_scan_date - :window_days
                     AND raw."scanDate" <= latest_per_key.latest_scan_date
                    WHERE latest_per_key.latest_scan_date IS NOT NULL
                    GROUP BY latest_per_key.location_id, latest_per_key.type_id, latest_per_key.latest_scan_date
                )
                SELECT
                    aggregated.location_id,
                    aggregated.type_id,
                    :period_days,
                    :demand_source,
                    aggregated.buy_from_sell_period,
                    aggregated.sell_to_buy_period,
                    aggregated.buy_from_sell_yesterday,
                    aggregated.sell_to_buy_yesterday,
                    :computed_at
                FROM aggregated
                ON CONFLICT (location_id, type_id, period_days) DO UPDATE
                SET demand_source = EXCLUDED.demand_source,
                    buy_from_sell_period = EXCLUDED.buy_from_sell_period,
                    sell_to_buy_period = EXCLUDED.sell_to_buy_period,
                    buy_from_sell_yesterday = EXCLUDED.buy_from_sell_yesterday,
                    sell_to_buy_yesterday = EXCLUDED.sell_to_buy_yesterday,
                    computed_at = EXCLUDED.computed_at
                """
            ),
            {
                "window_days": window_days,
                "period_days": period_days,
                "demand_source": DemandSource.ADAM4EVE.value,
                "computed_at": datetime.now(UTC),
            },
        )
        refreshed_count = int(
            session.scalar(
                text(
                    """
                    WITH latest_per_key AS (
                        SELECT
                            keys.location_id,
                            keys.type_id,
                            MAX(raw."scanDate") AS latest_scan_date
                        FROM adam_npc_demand_refresh_keys AS keys
                        JOIN locations ON locations.id = keys.location_id
                        JOIN items ON items.id = keys.type_id
                        LEFT JOIN adam_market_orders_trade_raw AS raw
                          ON raw.location_id = locations.location_id
                         AND raw.type_id = items.type_id
                        GROUP BY keys.location_id, keys.type_id
                    )
                    SELECT COUNT(*)
                    FROM latest_per_key
                    WHERE latest_scan_date IS NOT NULL
                    """
                )
            )
            or 0
        )
        session.commit()
        return refreshed_count

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
        if structure_period is not None:
            return self._upsert_row(
                session,
                location_id=location_id,
                type_id=type_id,
                period_days=period_days,
                demand_source=DemandSource.LOCAL_STRUCTURE.value,
                buy_from_sell_period=structure_period.buy_from_sell_period,
                sell_to_buy_period=structure_period.sell_to_buy_period,
                buy_from_sell_yesterday=structure_period.buy_from_sell_yesterday,
                sell_to_buy_yesterday=structure_period.sell_to_buy_yesterday,
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
        location = session.get(Location, location_id)
        item = session.get(Item, type_id)
        if location is None or item is None:
            raise ValueError("location_id or type_id was not found")

        latest_scan_date = session.scalar(
            select(AdamMarketOrdersTradeRaw.c.scanDate).where(
                AdamMarketOrdersTradeRaw.c.location_id == location.location_id,
                AdamMarketOrdersTradeRaw.c.type_id == item.type_id,
            ).order_by(AdamMarketOrdersTradeRaw.c.scanDate.desc())
        )
        if latest_scan_date is None:
            return self._delete_existing(session, location_id=location_id, type_id=type_id, period_days=period_days)

        window_start = latest_scan_date - timedelta(days=max(period_days - 1, 0))
        raw_rows = session.execute(
            select(
                AdamMarketOrdersTradeRaw.c.scanDate,
                AdamMarketOrdersTradeRaw.c.is_buy_order,
                AdamMarketOrdersTradeRaw.c.amount,
            ).where(
                AdamMarketOrdersTradeRaw.c.location_id == location.location_id,
                AdamMarketOrdersTradeRaw.c.type_id == item.type_id,
                AdamMarketOrdersTradeRaw.c.scanDate >= window_start,
                AdamMarketOrdersTradeRaw.c.scanDate <= latest_scan_date,
            )
        ).all()
        if not raw_rows:
            return self._delete_existing(session, location_id=location_id, type_id=type_id, period_days=period_days)

        buy_from_sell_period = 0.0
        sell_to_buy_period = 0.0
        buy_from_sell_yesterday = 0.0
        sell_to_buy_yesterday = 0.0
        distinct_dates: set[date] = set()
        for scan_date, is_buy_order, amount in raw_rows:
            distinct_dates.add(scan_date)
            if is_buy_order == 0:
                buy_from_sell_period += amount
                if scan_date == latest_scan_date:
                    buy_from_sell_yesterday += amount
            else:
                sell_to_buy_period += amount
                if scan_date == latest_scan_date:
                    sell_to_buy_yesterday += amount
        return self._upsert_row(
            session,
            location_id=location_id,
            type_id=type_id,
            period_days=period_days,
            demand_source=DemandSource.ADAM4EVE.value,
            buy_from_sell_period=buy_from_sell_period,
            sell_to_buy_period=sell_to_buy_period,
            buy_from_sell_yesterday=buy_from_sell_yesterday,
            sell_to_buy_yesterday=sell_to_buy_yesterday,
            points_used=len(distinct_dates),
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
                buy_from_sell_period=0.0,
                sell_to_buy_period=0.0,
                buy_from_sell_yesterday=0.0,
                sell_to_buy_yesterday=0.0,
                computed_at=datetime.now(UTC),
            )
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return MarketDemandResolutionResult(created=True, row=existing, points_used=0)

        existing.demand_source = DemandSource.REGIONAL_FALLBACK.value
        existing.buy_from_sell_period = 0.0
        existing.sell_to_buy_period = 0.0
        existing.buy_from_sell_yesterday = 0.0
        existing.sell_to_buy_yesterday = 0.0
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
        buy_from_sell_period: float,
        sell_to_buy_period: float,
        buy_from_sell_yesterday: float,
        sell_to_buy_yesterday: float,
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
                buy_from_sell_period=buy_from_sell_period,
                sell_to_buy_period=sell_to_buy_period,
                buy_from_sell_yesterday=buy_from_sell_yesterday,
                sell_to_buy_yesterday=sell_to_buy_yesterday,
                computed_at=datetime.now(UTC),
            )
            session.add(record)
        else:
            record.demand_source = demand_source
            record.buy_from_sell_period = buy_from_sell_period
            record.sell_to_buy_period = sell_to_buy_period
            record.buy_from_sell_yesterday = buy_from_sell_yesterday
            record.sell_to_buy_yesterday = sell_to_buy_yesterday
            record.computed_at = datetime.now(UTC)

        session.commit()
        session.refresh(record)
        return MarketDemandResolutionResult(created=created, row=record, points_used=points_used)

    def _prepare_npc_refresh_key_table(
        self,
        session: Session,
        *,
        demand_keys: list[tuple[int, int]],
    ) -> None:
        session.execute(
            text(
                """
                CREATE TEMP TABLE IF NOT EXISTS adam_npc_demand_refresh_keys (
                    location_id INTEGER NOT NULL,
                    type_id INTEGER NOT NULL
                ) ON COMMIT DROP
                """
            )
        )
        session.execute(text("TRUNCATE TABLE adam_npc_demand_refresh_keys"))
        copy_rows(
            session,
            table_name="adam_npc_demand_refresh_keys",
            columns=("location_id", "type_id"),
            rows=((location_id, type_id) for location_id, type_id in demand_keys),
        )
