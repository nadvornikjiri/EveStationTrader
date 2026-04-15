from __future__ import annotations

import argparse
import cProfile
import io
import pstats
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.all_models import AdamMarketOrdersTradeRaw, Item, Location
from app.services.demand.market_demand import MarketDemandResolutionService
from app.services.settings_service import SettingsService
from app.services.sync.service import SyncService


@dataclass
class ProfileSummary:
    total_s: float
    preprocess_s: float
    loop_s: float
    derived_count: int
    adam_lookup_s: float
    esi_history_s: float
    upsert_s: float


def _load_scope(session: Session, *, limit: int) -> tuple[list[tuple[int, int]], set[tuple[int, int]]]:
    sync_service = SyncService()
    demand_keys = sync_service._esi_demand_refresh_keys(session)
    unique_location_ids = {location_id for location_id, _ in demand_keys}
    unique_type_ids = {type_id for _, type_id in demand_keys}
    locations = (
        session.scalars(select(Location).where(Location.id.in_(unique_location_ids))).all()
        if unique_location_ids
        else []
    )
    items = (
        session.scalars(select(Item).where(Item.id.in_(unique_type_ids))).all()
        if unique_type_ids
        else []
    )

    eve_location_id_by_internal = {
        location.id: location.location_id
        for location in locations
    }
    internal_location_id_by_eve = {
        eve_location_id: internal_id for internal_id, eve_location_id in eve_location_id_by_internal.items()
    }
    eve_type_id_by_internal = {
        item.id: item.type_id
        for item in items
    }
    internal_item_id_by_eve = {eve_type_id: internal_id for internal_id, eve_type_id in eve_type_id_by_internal.items()}

    adam_covered_keys: set[tuple[int, int]] = set()
    if eve_location_id_by_internal and eve_type_id_by_internal:
        covered_rows = session.execute(
            select(
                AdamMarketOrdersTradeRaw.c.location_id,
                AdamMarketOrdersTradeRaw.c.type_id,
            )
            .where(
                AdamMarketOrdersTradeRaw.c.location_id.in_(eve_location_id_by_internal.values()),
                AdamMarketOrdersTradeRaw.c.type_id.in_(eve_type_id_by_internal.values()),
            )
            .distinct()
        ).all()
        adam_covered_keys = {
            (internal_location_id, internal_item_id)
            for eve_location_id, eve_type_id in covered_rows
            if (internal_location_id := internal_location_id_by_eve.get(eve_location_id)) is not None
            if (internal_item_id := internal_item_id_by_eve.get(eve_type_id)) is not None
        }

    filtered_keys = [key for key in demand_keys if key not in adam_covered_keys]
    return filtered_keys[:limit], adam_covered_keys


def _run_refresh(session: Session, *, limit: int, commit_interval: int) -> ProfileSummary:
    settings_service = SettingsService(session_factory=lambda: session)
    analysis_period_days = settings_service.get_settings_for_session(session).default_analysis_period_days

    total_started_at = perf_counter()
    preprocess_started_at = perf_counter()
    demand_keys, adam_covered_keys = _load_scope(session, limit=limit)
    demand_service = MarketDemandResolutionService()
    demand_preload = demand_service.build_batch_preload(
        session,
        demand_keys=demand_keys,
        period_days=analysis_period_days,
    )
    preprocess_s = perf_counter() - preprocess_started_at

    derived_count = 0
    total_adam_s = 0.0
    total_esi_history_s = 0.0
    total_upsert_s = 0.0
    loop_started_at = perf_counter()
    for idx, (location_id, type_id) in enumerate(demand_keys, start=1):
        result = demand_service.upsert_for_location(
            session,
            location_id=location_id,
            type_id=type_id,
            period_days=analysis_period_days,
            adam_covered=(location_id, type_id) in adam_covered_keys,
            autocommit=False,
            preload=demand_preload,
        )
        if idx % commit_interval == 0:
            session.commit()
        total_adam_s += result.timing.adam_lookup_s
        total_esi_history_s += result.timing.esi_history_s
        total_upsert_s += result.timing.upsert_s
        if result.row is not None:
            derived_count += 1
    session.commit()
    loop_s = perf_counter() - loop_started_at
    total_s = perf_counter() - total_started_at
    return ProfileSummary(
        total_s=total_s,
        preprocess_s=preprocess_s,
        loop_s=loop_s,
        derived_count=derived_count,
        adam_lookup_s=total_adam_s,
        esi_history_s=total_esi_history_s,
        upsert_s=total_upsert_s,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--commit-interval", type=int, default=50)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--profile-lines", type=int, default=25)
    args = parser.parse_args()

    session = SessionLocal()
    try:
        if args.profile:
            profiler = cProfile.Profile()
            profiler.enable()
            summary = _run_refresh(session, limit=args.limit, commit_interval=args.commit_interval)
            profiler.disable()
            stats_stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stats_stream).sort_stats("cumulative")
            stats.print_stats(args.profile_lines)
            print(stats_stream.getvalue())
        else:
            summary = _run_refresh(session, limit=args.limit, commit_interval=args.commit_interval)
        print(f"keys={args.limit}")
        print(f"total_s={summary.total_s:.3f}")
        print(f"preprocess_s={summary.preprocess_s:.3f}")
        print(f"loop_s={summary.loop_s:.3f}")
        print(f"derived_count={summary.derived_count}")
        print(f"adam_lookup_s={summary.adam_lookup_s:.3f}")
        print(f"esi_history_s={summary.esi_history_s:.3f}")
        print(f"upsert_s={summary.upsert_s:.3f}")
        if args.limit:
            print(f"avg_ms_per_key={summary.loop_s / args.limit * 1000:.1f}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
