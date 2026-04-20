from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from time import perf_counter

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.domain.enums import DemandSource, LocationType
from app.models.all_models import AdamMarketOrdersTradeRaw, EsiHistoryDaily, Item, Location, MarketDemandResolved, NpcStationDemandPeriod, StructureDemandPeriod


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
    valid_days: int
    buy_from_sell_ratio_period: float | None
    buy_from_sell_ratio_yesterday: float | None
    fallback_reason: str


@dataclass
class MarketDemandBatchPreload:
    locations_by_id: dict[int, Location] = field(default_factory=dict)
    items_by_id: dict[int, Item] = field(default_factory=dict)
    esi_history_by_region_type: dict[tuple[int, int], list[EsiHistoryDaily]] = field(default_factory=dict)
    existing_rows_by_key: dict[tuple[int, int, int], MarketDemandResolved] = field(default_factory=dict)
    station_periods_by_key: dict[tuple[int, int, int], NpcStationDemandPeriod] = field(default_factory=dict)


class MarketDemandResolutionService:
    _PAIR_CHUNK_SIZE = 1000

    @classmethod
    def build_batch_preload(
        cls,
        session: Session,
        *,
        demand_keys: list[tuple[int, int]],
        period_days: int,
    ) -> MarketDemandBatchPreload:
        unique_keys = list(dict.fromkeys(demand_keys))
        location_ids = sorted({location_id for location_id, _ in unique_keys})
        type_ids = sorted({type_id for _, type_id in unique_keys})
        locations = (
            session.scalars(select(Location).where(Location.id.in_(location_ids))).all()
            if location_ids
            else []
        )
        items = (
            session.scalars(select(Item).where(Item.id.in_(type_ids))).all()
            if type_ids
            else []
        )
        preload = MarketDemandBatchPreload(
            locations_by_id={location.id: location for location in locations},
            items_by_id={item.id: item for item in items},
        )

        max_history_days = max(period_days, 1)
        history_pairs = {
            (location.region_id, type_id)
            for location_id, type_id in unique_keys
            if (location := preload.locations_by_id.get(location_id)) is not None
        }
        for pair_chunk in cls._chunk_pairs(sorted(history_pairs)):
            history_rows = session.scalars(
                select(EsiHistoryDaily)
                .where(tuple_(EsiHistoryDaily.region_id, EsiHistoryDaily.type_id).in_(pair_chunk))
                .order_by(
                    EsiHistoryDaily.region_id.asc(),
                    EsiHistoryDaily.type_id.asc(),
                    EsiHistoryDaily.date.desc(),
                )
            ).all()
            rows_by_pair: dict[tuple[int, int], list[EsiHistoryDaily]] = defaultdict(list)
            for row in history_rows:
                key = (row.region_id, row.type_id)
                if len(rows_by_pair[key]) < max_history_days:
                    rows_by_pair[key].append(row)
            preload.esi_history_by_region_type.update(rows_by_pair)

        existing_pairs = sorted(unique_keys)
        for pair_chunk in cls._chunk_pairs(existing_pairs):
            existing_rows = session.scalars(
                select(MarketDemandResolved).where(
                    MarketDemandResolved.period_days == period_days,
                    tuple_(MarketDemandResolved.location_id, MarketDemandResolved.type_id).in_(pair_chunk),
                )
            ).all()
            preload.existing_rows_by_key.update(
                {
                    (row.location_id, row.type_id, row.period_days): row
                    for row in existing_rows
                }
            )

        for pair_chunk in cls._chunk_pairs(existing_pairs):
            station_period_rows = session.scalars(
                select(NpcStationDemandPeriod).where(
                    NpcStationDemandPeriod.period_days == period_days,
                    tuple_(NpcStationDemandPeriod.location_id, NpcStationDemandPeriod.type_id).in_(pair_chunk),
                )
            ).all()
            preload.station_periods_by_key.update(
                {
                    (row.location_id, row.type_id, row.period_days): row
                    for row in station_period_rows
                }
            )
        return preload

    @classmethod
    def _chunk_pairs(
        cls,
        pairs: list[tuple[int, int]],
    ) -> list[list[tuple[int, int]]]:
        return [pairs[index : index + cls._PAIR_CHUNK_SIZE] for index in range(0, len(pairs), cls._PAIR_CHUNK_SIZE)]

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
        autocommit: bool = True,
        preload: MarketDemandBatchPreload | None = None,
    ) -> MarketDemandResolutionResult:
        location = preload.locations_by_id.get(location_id) if preload is not None else session.get(Location, location_id)
        if location is None:
            raise ValueError(f"location_id {location_id} was not found")

        if location.location_type == LocationType.NPC_STATION.value:
            return self._upsert_npc_from_adam(
                session,
                location_id=location_id,
                type_id=type_id,
                period_days=period_days,
                adam_covered=adam_covered,
                autocommit=autocommit,
                preload=preload,
            )

        structure_period = session.scalar(
            select(StructureDemandPeriod).where(
                StructureDemandPeriod.structure_id == location.location_id,
                StructureDemandPeriod.type_id == type_id,
                StructureDemandPeriod.period_days == period_days,
            )
        )
        if structure_period is not None and structure_period.buy_from_sell_period > 0:
            return self._upsert_row(
                session,
                location_id=location_id,
                type_id=type_id,
                period_days=period_days,
                demand_source=DemandSource.LOCAL_STRUCTURE.value,
                buy_from_sell_period=structure_period.buy_from_sell_period,
                sell_to_buy_period=structure_period.sell_to_buy_period,
                points_used=1,
                esi_live_valid_days=None,
                esi_live_buy_from_sell_ratio_period=None,
                esi_live_buy_from_sell_ratio_yesterday=None,
                esi_live_fallback_reason=None,
                autocommit=autocommit,
                preload=preload,
            )

        return self._upsert_structure_fallback(
            session,
            location_id=location_id,
            type_id=type_id,
            period_days=period_days,
            autocommit=autocommit,
            preload=preload,
        )

    def _upsert_npc_from_adam(
        self,
        session: Session,
        *,
        location_id: int,
        type_id: int,
        period_days: int,
        adam_covered: bool = True,
        autocommit: bool = True,
        preload: MarketDemandBatchPreload | None = None,
    ) -> MarketDemandResolutionResult:
        timing = DemandResolutionTiming()
        location = preload.locations_by_id.get(location_id) if preload is not None else session.get(Location, location_id)
        item = preload.items_by_id.get(type_id) if preload is not None else session.get(Item, type_id)
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
                points_used=adam_points,
                esi_live_valid_days=None,
                esi_live_buy_from_sell_ratio_period=None,
                esi_live_buy_from_sell_ratio_yesterday=None,
                esi_live_fallback_reason=None,
                autocommit=autocommit,
            )
            timing.upsert_s = perf_counter() - t0
            result.timing = timing
            return result

        # Check npc_station_demand_period as secondary source (before ESI regional history fallback)
        t0 = perf_counter()
        station_period_key = (location_id, type_id, period_days)
        station_period = (
            preload.station_periods_by_key.get(station_period_key)
            if preload is not None
            else session.scalar(
                select(NpcStationDemandPeriod).where(
                    NpcStationDemandPeriod.location_id == location_id,
                    NpcStationDemandPeriod.type_id == type_id,
                    NpcStationDemandPeriod.period_days == period_days,
                )
            )
        )
        if station_period is not None and station_period.buy_from_sell_period > 0:
            result = self._upsert_row(
                session,
                location_id=location_id,
                type_id=type_id,
                period_days=period_days,
                demand_source=DemandSource.NPC_STATION_PERIOD.value,
                buy_from_sell_period=station_period.buy_from_sell_period,
                sell_to_buy_period=station_period.sell_to_buy_period,
                points_used=int(station_period.coverage_pct * period_days),
                esi_live_valid_days=None,
                esi_live_buy_from_sell_ratio_period=None,
                esi_live_buy_from_sell_ratio_yesterday=None,
                esi_live_fallback_reason=None,
                autocommit=autocommit,
                preload=preload,
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
            preload=preload,
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
                points_used=esi_live_estimate.valid_days,
                esi_live_valid_days=esi_live_estimate.valid_days,
                esi_live_buy_from_sell_ratio_period=esi_live_estimate.buy_from_sell_ratio_period,
                esi_live_buy_from_sell_ratio_yesterday=esi_live_estimate.buy_from_sell_ratio_yesterday,
                esi_live_fallback_reason=esi_live_estimate.fallback_reason,
                autocommit=autocommit,
                preload=preload,
            )
            timing.upsert_s = perf_counter() - t0
            result.timing = timing
            return result

        t0 = perf_counter()
        result = self._delete_existing(
            session,
            location_id=location_id,
            type_id=type_id,
            period_days=period_days,
            autocommit=autocommit,
            preload=preload,
        )
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
        autocommit: bool = True,
        preload: MarketDemandBatchPreload | None = None,
    ) -> MarketDemandResolutionResult:
        esi_live_estimate = self._estimate_esi_live_demand(
            session,
            location_id=location_id,
            type_id=type_id,
            period_days=period_days,
            fallback_reason="missing_structure_period",
            preload=preload,
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
                points_used=esi_live_estimate.valid_days,
                esi_live_valid_days=esi_live_estimate.valid_days,
                esi_live_buy_from_sell_ratio_period=esi_live_estimate.buy_from_sell_ratio_period,
                esi_live_buy_from_sell_ratio_yesterday=esi_live_estimate.buy_from_sell_ratio_yesterday,
                esi_live_fallback_reason=esi_live_estimate.fallback_reason,
                autocommit=autocommit,
                preload=preload,
            )

        return self._upsert_row(
            session,
            location_id=location_id,
            type_id=type_id,
            period_days=period_days,
            demand_source=DemandSource.REGIONAL_FALLBACK.value,
            buy_from_sell_period=0.0,
            sell_to_buy_period=0.0,
            points_used=0,
            esi_live_valid_days=0,
            esi_live_buy_from_sell_ratio_period=None,
            esi_live_buy_from_sell_ratio_yesterday=None,
            esi_live_fallback_reason="missing_structure_period_and_esi_history",
            autocommit=autocommit,
            preload=preload,
        )

    def _delete_existing(
        self,
        session: Session,
        *,
        location_id: int,
        type_id: int,
        period_days: int,
        autocommit: bool = True,
        preload: MarketDemandBatchPreload | None = None,
    ) -> MarketDemandResolutionResult:
        existing_key = (location_id, type_id, period_days)
        existing = preload.existing_rows_by_key.get(existing_key) if preload is not None else session.scalar(
            select(MarketDemandResolved).where(
                MarketDemandResolved.location_id == location_id,
                MarketDemandResolved.type_id == type_id,
                MarketDemandResolved.period_days == period_days,
            )
        )
        if existing is not None:
            session.delete(existing)
            if preload is not None:
                preload.existing_rows_by_key.pop(existing_key, None)
            if autocommit:
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
        points_used: int,
        esi_live_valid_days: int | None,
        esi_live_buy_from_sell_ratio_period: float | None,
        esi_live_buy_from_sell_ratio_yesterday: float | None,
        esi_live_fallback_reason: str | None,
        autocommit: bool = True,
        preload: MarketDemandBatchPreload | None = None,
    ) -> MarketDemandResolutionResult:
        record_key = (location_id, type_id, period_days)
        record = preload.existing_rows_by_key.get(record_key) if preload is not None else session.scalar(
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
                esi_live_valid_days=esi_live_valid_days,
                esi_live_buy_from_sell_ratio_period=esi_live_buy_from_sell_ratio_period,
                esi_live_buy_from_sell_ratio_yesterday=esi_live_buy_from_sell_ratio_yesterday,
                esi_live_fallback_reason=esi_live_fallback_reason,
                computed_at=datetime.now(UTC),
            )
            session.add(record)
            if preload is not None:
                preload.existing_rows_by_key[record_key] = record
        else:
            record.demand_source = demand_source
            record.buy_from_sell_period = buy_from_sell_period
            record.sell_to_buy_period = sell_to_buy_period
            record.esi_live_valid_days = esi_live_valid_days
            record.esi_live_buy_from_sell_ratio_period = esi_live_buy_from_sell_ratio_period
            record.esi_live_buy_from_sell_ratio_yesterday = esi_live_buy_from_sell_ratio_yesterday
            record.esi_live_fallback_reason = esi_live_fallback_reason
            record.computed_at = datetime.now(UTC)

        if autocommit:
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
        preload: MarketDemandBatchPreload | None = None,
    ) -> EsiLiveDemandEstimate | None:
        location = preload.locations_by_id.get(location_id) if preload is not None else session.get(Location, location_id)
        if location is None:
            return None

        history_rows = (
            preload.esi_history_by_region_type.get((location.region_id, type_id), [])
            if preload is not None
            else session.scalars(
                select(EsiHistoryDaily)
                .where(
                    EsiHistoryDaily.region_id == location.region_id,
                    EsiHistoryDaily.type_id == type_id,
                )
                .order_by(EsiHistoryDaily.date.desc())
                .limit(max(period_days, 1))
            ).all()
        )
        if not history_rows:
            return None

        latest_history_date = max(row.date for row in history_rows)
        buy_from_sell_period = 0.0
        sell_to_buy_period = 0.0
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
                buy_from_sell_ratio_yesterday = ratio

        if valid_days == 0:
            return None

        return EsiLiveDemandEstimate(
            buy_from_sell_period=buy_from_sell_period,
            sell_to_buy_period=sell_to_buy_period,
            valid_days=valid_days,
            buy_from_sell_ratio_period=(buy_from_sell_period / valid_volume_period) if valid_volume_period > 0 else None,
            buy_from_sell_ratio_yesterday=buy_from_sell_ratio_yesterday,
            fallback_reason=fallback_reason,
        )
