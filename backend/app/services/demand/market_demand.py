from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import DemandSource, LocationType
from app.models.all_models import AdamMarketOrdersTradeRaw, EsiHistoryDaily, Item, Location, MarketDemandResolved, StructureDemandPeriod


@dataclass
class DemandResolutionTiming:
    """Accumulated wall-clock seconds for each sub-phase of a resolution call."""
    adam_lookup_s: float = field(default=0.0)
    esi_history_s: float = field(default=0.0)
    upsert_s: float = field(default=0.0)

    @property
    def total_s(self) -> float:
        return self.adam_lookup_s + self.esi_history_s + self.upsert_s


@dataclass
class MarketDemandResolutionResult:
    created: bool
    row: MarketDemandResolved | None
    points_used: int
    timing: DemandResolutionTiming = field(default_factory=DemandResolutionTiming)


@dataclass
class EsiLiveDemandEstimate:
    buy_from_sell_period: float
    sell_to_buy_period: float
    buy_from_sell_yesterday: float
    sell_to_buy_yesterday: float
    valid_days: int
    buy_from_sell_ratio_period: float | None
    buy_from_sell_ratio_yesterday: float | None
    fallback_reason: str


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

    def upsert_for_location(
        self,
        session: Session,
        *,
        location_id: int,
        type_id: int,
        period_days: int,
        adam_covered: bool = True,
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
                adam_covered=adam_covered,
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
                esi_live_valid_days=None,
                esi_live_buy_from_sell_ratio_period=None,
                esi_live_buy_from_sell_ratio_yesterday=None,
                esi_live_fallback_reason=None,
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
        adam_covered: bool = True,
    ) -> MarketDemandResolutionResult:
        timing = DemandResolutionTiming()
        location = session.get(Location, location_id)
        item = session.get(Item, type_id)
        if location is None or item is None:
            raise ValueError("location_id or type_id was not found")

        # Gather Adam4EVE demand data
        adam_bfs_yesterday = 0.0
        adam_bfs_period = 0.0
        adam_stb_period = 0.0
        adam_stb_yesterday = 0.0
        adam_points = 0
        if adam_covered:
            t0 = perf_counter()
            latest_scan_date = session.scalar(
                select(AdamMarketOrdersTradeRaw.c.scanDate).where(
                    AdamMarketOrdersTradeRaw.c.location_id == location.location_id,
                    AdamMarketOrdersTradeRaw.c.type_id == item.type_id,
                ).order_by(AdamMarketOrdersTradeRaw.c.scanDate.desc())
            )
            if latest_scan_date is not None:
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
                distinct_dates: set[date] = set()
                for scan_date, is_buy_order, amount in raw_rows:
                    distinct_dates.add(scan_date)
                    if is_buy_order == 0:
                        adam_bfs_period += amount
                        if scan_date == latest_scan_date:
                            adam_bfs_yesterday += amount
                    else:
                        adam_stb_period += amount
                        if scan_date == latest_scan_date:
                            adam_stb_yesterday += amount
                adam_points = len(distinct_dates)
            timing.adam_lookup_s = perf_counter() - t0

        if adam_bfs_yesterday > 0 or adam_bfs_period > 0:
            t0 = perf_counter()
            result = self._upsert_row(
                session,
                location_id=location_id,
                type_id=type_id,
                period_days=period_days,
                demand_source=DemandSource.ADAM4EVE.value,
                buy_from_sell_period=adam_bfs_period,
                sell_to_buy_period=adam_stb_period,
                buy_from_sell_yesterday=adam_bfs_yesterday,
                sell_to_buy_yesterday=adam_stb_yesterday,
                points_used=adam_points,
                esi_live_valid_days=None,
                esi_live_buy_from_sell_ratio_period=None,
                esi_live_buy_from_sell_ratio_yesterday=None,
                esi_live_fallback_reason=None,
            )
            timing.upsert_s = perf_counter() - t0
            result.timing = timing
            return result

        t0 = perf_counter()
        esi_live_estimate = self._estimate_esi_live_demand(
            session,
            location_id=location_id,
            type_id=type_id,
            period_days=period_days,
            fallback_reason="adam_zero_buy_from_sell" if adam_covered else "adam_not_covered",
        )
        timing.esi_history_s = perf_counter() - t0

        if esi_live_estimate is not None:
            t0 = perf_counter()
            result = self._upsert_row(
                session,
                location_id=location_id,
                type_id=type_id,
                period_days=period_days,
                demand_source=DemandSource.ESI_LIVE.value,
                buy_from_sell_period=esi_live_estimate.buy_from_sell_period,
                sell_to_buy_period=esi_live_estimate.sell_to_buy_period,
                buy_from_sell_yesterday=esi_live_estimate.buy_from_sell_yesterday,
                sell_to_buy_yesterday=esi_live_estimate.sell_to_buy_yesterday,
                points_used=esi_live_estimate.valid_days,
                esi_live_valid_days=esi_live_estimate.valid_days,
                esi_live_buy_from_sell_ratio_period=esi_live_estimate.buy_from_sell_ratio_period,
                esi_live_buy_from_sell_ratio_yesterday=esi_live_estimate.buy_from_sell_ratio_yesterday,
                esi_live_fallback_reason=esi_live_estimate.fallback_reason,
            )
            timing.upsert_s = perf_counter() - t0
            result.timing = timing
            return result

        t0 = perf_counter()
        result = self._delete_existing(session, location_id=location_id, type_id=type_id, period_days=period_days)
        timing.upsert_s = perf_counter() - t0
        result.timing = timing
        return result

    def _upsert_structure_fallback(
        self,
        session: Session,
        *,
        location_id: int,
        type_id: int,
        period_days: int,
    ) -> MarketDemandResolutionResult:
        esi_live_estimate = self._estimate_esi_live_demand(
            session,
            location_id=location_id,
            type_id=type_id,
            period_days=period_days,
            fallback_reason="missing_structure_period",
        )
        if esi_live_estimate is not None:
            return self._upsert_row(
                session,
                location_id=location_id,
                type_id=type_id,
                period_days=period_days,
                demand_source=DemandSource.ESI_LIVE.value,
                buy_from_sell_period=esi_live_estimate.buy_from_sell_period,
                sell_to_buy_period=esi_live_estimate.sell_to_buy_period,
                buy_from_sell_yesterday=esi_live_estimate.buy_from_sell_yesterday,
                sell_to_buy_yesterday=esi_live_estimate.sell_to_buy_yesterday,
                points_used=esi_live_estimate.valid_days,
                esi_live_valid_days=esi_live_estimate.valid_days,
                esi_live_buy_from_sell_ratio_period=esi_live_estimate.buy_from_sell_ratio_period,
                esi_live_buy_from_sell_ratio_yesterday=esi_live_estimate.buy_from_sell_ratio_yesterday,
                esi_live_fallback_reason=esi_live_estimate.fallback_reason,
            )

        return self._upsert_row(
            session,
            location_id=location_id,
            type_id=type_id,
            period_days=period_days,
            demand_source=DemandSource.REGIONAL_FALLBACK.value,
            buy_from_sell_period=0.0,
            sell_to_buy_period=0.0,
            buy_from_sell_yesterday=0.0,
            sell_to_buy_yesterday=0.0,
            points_used=0,
            esi_live_valid_days=0,
            esi_live_buy_from_sell_ratio_period=None,
            esi_live_buy_from_sell_ratio_yesterday=None,
            esi_live_fallback_reason="missing_structure_period_and_esi_history",
        )

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
        esi_live_valid_days: int | None,
        esi_live_buy_from_sell_ratio_period: float | None,
        esi_live_buy_from_sell_ratio_yesterday: float | None,
        esi_live_fallback_reason: str | None,
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
                esi_live_valid_days=esi_live_valid_days,
                esi_live_buy_from_sell_ratio_period=esi_live_buy_from_sell_ratio_period,
                esi_live_buy_from_sell_ratio_yesterday=esi_live_buy_from_sell_ratio_yesterday,
                esi_live_fallback_reason=esi_live_fallback_reason,
                computed_at=datetime.now(UTC),
            )
            session.add(record)
        else:
            record.demand_source = demand_source
            record.buy_from_sell_period = buy_from_sell_period
            record.sell_to_buy_period = sell_to_buy_period
            record.buy_from_sell_yesterday = buy_from_sell_yesterday
            record.sell_to_buy_yesterday = sell_to_buy_yesterday
            record.esi_live_valid_days = esi_live_valid_days
            record.esi_live_buy_from_sell_ratio_period = esi_live_buy_from_sell_ratio_period
            record.esi_live_buy_from_sell_ratio_yesterday = esi_live_buy_from_sell_ratio_yesterday
            record.esi_live_fallback_reason = esi_live_fallback_reason
            record.computed_at = datetime.now(UTC)

        session.commit()
        return MarketDemandResolutionResult(created=created, row=record, points_used=points_used)

    @staticmethod
    def _estimate_buy_from_sell_ratio(*, median_price: float, lowest_price: float, highest_price: float) -> float:
        if highest_price <= lowest_price:
            return 0.5
        ratio = (median_price - lowest_price) / (highest_price - lowest_price)
        return min(max(ratio, 0.0), 1.0)

    def _estimate_esi_live_demand(
        self,
        session: Session,
        *,
        location_id: int,
        type_id: int,
        period_days: int,
        fallback_reason: str,
    ) -> EsiLiveDemandEstimate | None:
        location = session.get(Location, location_id)
        if location is None:
            return None

        history_rows = session.scalars(
            select(EsiHistoryDaily)
            .where(
                EsiHistoryDaily.region_id == location.region_id,
                EsiHistoryDaily.type_id == type_id,
            )
            .order_by(EsiHistoryDaily.date.desc())
            .limit(max(period_days, 1))
        ).all()
        if not history_rows:
            return None

        latest_history_date = max(row.date for row in history_rows)
        buy_from_sell_period = 0.0
        sell_to_buy_period = 0.0
        buy_from_sell_yesterday = 0.0
        sell_to_buy_yesterday = 0.0
        valid_days = 0
        valid_volume_period = 0.0
        buy_from_sell_ratio_yesterday: float | None = None

        for row in history_rows:
            if row.volume <= 0:
                continue
            ratio = self._estimate_buy_from_sell_ratio(
                median_price=row.average,
                lowest_price=row.lowest,
                highest_price=row.highest,
            )
            day_buy_from_sell = float(row.volume) * ratio
            day_sell_to_buy = float(row.volume) * (1.0 - ratio)
            buy_from_sell_period += day_buy_from_sell
            sell_to_buy_period += day_sell_to_buy
            valid_volume_period += float(row.volume)
            valid_days += 1
            if row.date == latest_history_date:
                buy_from_sell_yesterday = day_buy_from_sell
                sell_to_buy_yesterday = day_sell_to_buy
                buy_from_sell_ratio_yesterday = ratio

        if valid_days == 0:
            return None

        return EsiLiveDemandEstimate(
            buy_from_sell_period=buy_from_sell_period,
            sell_to_buy_period=sell_to_buy_period,
            buy_from_sell_yesterday=buy_from_sell_yesterday,
            sell_to_buy_yesterday=sell_to_buy_yesterday,
            valid_days=valid_days,
            buy_from_sell_ratio_period=(buy_from_sell_period / valid_volume_period) if valid_volume_period > 0 else None,
            buy_from_sell_ratio_yesterday=buy_from_sell_ratio_yesterday,
            fallback_reason=fallback_reason,
        )
