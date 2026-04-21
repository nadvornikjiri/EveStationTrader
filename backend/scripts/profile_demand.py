"""Profile the Adam demand refresh paths: SQL bulk vs per-key Python loop."""
from __future__ import annotations

import argparse
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.all_models import Location
from app.services.demand.market_demand import MarketDemandResolutionService
from app.services.settings_service import SettingsService
from app.services.sync.service import SyncService


def _load_scope(session: Session) -> tuple[list[int], list[int]]:
    sync_service = SyncService()
    settings = SettingsService(session_factory=lambda: session).get_settings_for_session(session)

    configured_target_ids = settings.target_market_location_ids or []
    target_location_ids = list(
        session.scalars(
            select(Location.id).where(Location.location_id.in_(configured_target_ids))
        ).all()
    ) if configured_target_ids else []

    source_region_ids = sync_service._configured_source_region_ids(session)
    target_npc_locations = session.scalars(
        select(Location).where(Location.id.in_(target_location_ids))
    ).all() if target_location_ids else []
    region_ids_set = set(source_region_ids)
    region_ids_set.update(loc.region_id for loc in target_npc_locations if loc.region_id is not None)
    source_region_ids = sorted(region_ids_set)

    return target_location_ids, source_region_ids


def _run_sql_path(
    session: Session,
    *,
    target_location_ids: list[int],
    source_region_ids: list[int],
    period_days: int,
) -> tuple[float, int]:
    service = MarketDemandResolutionService()
    t0 = perf_counter()
    rows_affected = service.refresh_target_markets_from_adam(
        session,
        target_location_ids=target_location_ids,
        source_region_ids=source_region_ids,
        period_days=period_days,
    )
    elapsed = perf_counter() - t0
    return elapsed, rows_affected


def _run_per_key_path(
    session: Session,
    *,
    target_location_ids: list[int],
    source_region_ids: list[int],
    period_days: int,
    key_limit: int,
) -> tuple[float, int]:
    service = MarketDemandResolutionService()
    demand_keys = service._target_market_demand_keys_from_adam(
        session,
        target_location_ids=target_location_ids,
        source_region_ids=source_region_ids,
    )
    limited_keys = demand_keys[:key_limit]
    t0 = perf_counter()
    count = service.refresh_npc_keys_from_adam(
        session,
        demand_keys=limited_keys,
        period_days=period_days,
    )
    elapsed = perf_counter() - t0
    return elapsed, len(limited_keys)


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile Adam demand refresh paths")
    parser.add_argument("--output", default="/tmp/demand_profile_before.txt")
    parser.add_argument("--per-key-limit", type=int, default=500, help="Keys to test for per-key path")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        settings = SettingsService(session_factory=lambda: session).get_settings_for_session(session)
        period_days = settings.default_analysis_period_days

        target_location_ids, source_region_ids = _load_scope(session)
        print(f"target_location_ids={target_location_ids}")
        print(f"source_region_ids count={len(source_region_ids)}")
        print(f"period_days={period_days}")

        # Measure SQL bulk path
        sql_elapsed, sql_rows = _run_sql_path(
            session,
            target_location_ids=target_location_ids,
            source_region_ids=source_region_ids,
            period_days=period_days,
        )
        sql_rows_per_sec = sql_rows / sql_elapsed if sql_elapsed > 0 else 0

        # Measure per-key Python loop path
        per_key_elapsed, per_key_count = _run_per_key_path(
            session,
            target_location_ids=target_location_ids,
            source_region_ids=source_region_ids,
            period_days=period_days,
            key_limit=args.per_key_limit,
        )
        per_key_rate = per_key_count / per_key_elapsed if per_key_elapsed > 0 else 0

        lines = [
            "=== Adam demand refresh profile ===",
            f"target_location_ids: {target_location_ids}",
            f"source_region_count: {len(source_region_ids)}",
            f"period_days: {period_days}",
            "",
            "--- SQL bulk path (refresh_target_markets_from_adam) ---",
            f"elapsed_s: {sql_elapsed:.3f}",
            f"rows_affected: {sql_rows}",
            f"rows_per_sec: {sql_rows_per_sec:.0f}",
            "",
            f"--- Per-key Python loop path (refresh_npc_keys_from_adam, limit={args.per_key_limit}) ---",
            f"elapsed_s: {per_key_elapsed:.3f}",
            f"keys_processed: {per_key_count}",
            f"keys_per_sec: {per_key_rate:.1f}",
            f"ms_per_key: {per_key_elapsed / per_key_count * 1000:.2f}" if per_key_count else "ms_per_key: N/A",
            "",
            "--- Speedup estimate ---",
        ]
        # Estimate: extrapolate per-key rate to full SQL row count
        if per_key_rate > 0 and sql_rows > 0:
            estimated_per_key_full_s = sql_rows / per_key_rate
            speedup = estimated_per_key_full_s / sql_elapsed if sql_elapsed > 0 else float("inf")
            lines.append(f"estimated_per_key_full_s (for {sql_rows} rows): {estimated_per_key_full_s:.1f}")
            lines.append(f"sql_speedup_factor: {speedup:.1f}x")

        output = "\n".join(lines) + "\n"
        print(output)
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Saved to {args.output}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
