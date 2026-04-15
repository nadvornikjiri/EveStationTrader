# Current task

Gap 1 fix complete. All backlog items done. 8,213 new npc_station_period demand rows, +4,177 opportunity_items.

# End goal with specs

- `market_demand_resolved` gains rows with `demand_source = 'npc_station_period'` for previously-missing items
- The next opportunity rebuild picks them up — verifiable by querying `opportunity_items` count before/after
- All 31 existing tests still pass
- No changes to `generation.py`, no degradation of existing `adam4eve` or `esi_live` rows

## File ownership
- YOU OWN: `backend/app/domain/enums.py`, `backend/app/services/demand/market_demand.py`, `backend/app/services/sync/service.py`
- DO NOT TOUCH: `backend/app/services/opportunities/generation.py`
- Tests live in: `backend/tests/`

# Roadmap (Completed)
- Investigation complete, root cause identified

# Roadmap (Upcoming)
- Implement all code changes
- Run tests
- Trigger demand resolution + opportunity rebuild
- Verify improvement in opportunity count

# Backlog

- [x] Read the 3 target files before editing
- [x] Edit `backend/app/domain/enums.py`: add `NPC_STATION_PERIOD = "npc_station_period"` to `DemandSource` enum
- [x] Edit `backend/app/services/demand/market_demand.py` — 4 sub-changes:
  - Add `NpcStationDemandPeriod` to imports (line 10)
  - Add `station_periods_by_key: dict[tuple[int, int, int], NpcStationDemandPeriod] = field(default_factory=dict)` to `MarketDemandBatchPreload` dataclass
  - In `build_batch_preload()`, after the `existing_rows_by_key` loading block, add a loop that loads `NpcStationDemandPeriod` rows for all `unique_keys` into `preload.station_periods_by_key` using the same `_chunk_pairs` pattern
  - In `_upsert_npc_from_adam()`, insert new block AFTER the adam4eve `if adam_bfs_yesterday > 0 or adam_bfs_period > 0: ... return result` block and BEFORE the `_estimate_esi_live_demand` call: look up station_period from preload or DB, if `buy_from_sell_period > 0` call `_upsert_row` with `demand_source=DemandSource.NPC_STATION_PERIOD.value` and return
- [x] Edit `backend/app/services/sync/service.py` — 2 sub-changes:
  - Add `NpcStationDemandPeriod` to the model imports block (around line 25-56, alphabetically after `MarketPricePeriod`)
  - Rewrite the tail of `_esi_demand_refresh_keys()`: after computing `order_based_pairs`, add a second query fetching `(location_id, type_id)` from `npc_station_demand_period` at target locations with `buy_from_sell_period > 0`, then union both into a single deduped list. The period_days for the second query = `max(settings.default_analysis_period_days, 1)` (settings already loaded at top of method)
- [x] Run tests: `docker exec eve-station-trader-dev-backend-1 python -m pytest tests/ -x -q`
- [x] Record pre-fix baseline: count of `opportunity_items` and `market_demand_resolved` rows
  - Baseline: opportunity_items=922,347 | adam4eve=86,636 | esi_live=42,763 | npc_station_period=0
- [x] Trigger demand resolution: POST to `/api/sync/run/everef_history_sync` (runs `_esi_demand_refresh_keys` → `_upsert_npc_from_adam` → writes new rows)
- [x] Wait for sync to complete, then trigger opportunity rebuild: POST `/api/sync/run/opportunity_rebuild`
- [x] Verify fix: 8,213 new `npc_station_period` rows created; opportunity_items=926,524 (+4,177)

## Key implementation details

### `_upsert_npc_from_adam` injection point (market_demand.py ~line 286)
Insert this block between the adam4eve return and the `t0 = perf_counter()` / `_estimate_esi_live_demand` call:

```python
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
```

### `_esi_demand_refresh_keys` tail rewrite (service.py ~line 2058)
Replace everything from `items_with_orders: set[int] = ...` to the final `return [...]` with:

```python
        # Items with live market orders at target stations AND ESI history
        items_with_orders: set[int] = {type_id for _, type_id in order_pairs}
        items_with_history: set[int] = set(
            session.scalars(
                select(distinct(EsiHistoryDaily.type_id)).where(
                    EsiHistoryDaily.type_id.in_(items_with_orders),
                    EsiHistoryDaily.region_id.in_(desired_internal_region_ids),
                )
            ).all()
        )
        order_based_pairs: list[tuple[int, int]] = [
            (location_id, type_id)
            for location_id, type_id in dict.fromkeys(order_pairs)
            if type_id in items_with_history
        ]

        # Items with npc_station_demand_period at target stations
        # (self-contained demand signal — no ESI history gate needed)
        analysis_period_days = max(settings.default_analysis_period_days, 1)
        period_based_pairs: list[tuple[int, int]] = list(
            session.execute(
                select(
                    distinct(NpcStationDemandPeriod.location_id),
                    NpcStationDemandPeriod.type_id,
                ).where(
                    NpcStationDemandPeriod.location_id.in_(target_location_ids),
                    NpcStationDemandPeriod.period_days == analysis_period_days,
                    NpcStationDemandPeriod.buy_from_sell_period > 0,
                )
            ).all()
        )

        # Union — order-based first (deduped by dict.fromkeys)
        all_pairs: dict[tuple[int, int], None] = dict.fromkeys(order_based_pairs)
        all_pairs.update(dict.fromkeys(period_based_pairs))
        return list(all_pairs.keys())
```

### API endpoints for triggering jobs
- Check sync status: `curl http://localhost:8000/sync/status`
- Trigger job: `curl -X POST http://localhost:8000/sync/trigger -H 'Content-Type: application/json' -d '{"job_type": "everef_history_sync"}'`
- Poll job: `curl http://localhost:8000/sync/jobs/<job_id>`
- DB queries via: `docker exec eve-station-trader-dev-postgres-1 psql -U eve_trader -d eve_trader -c "<SQL>"`

### Verification queries
```sql
-- New demand rows
SELECT demand_source, COUNT(*) FROM market_demand_resolved WHERE period_days=14 GROUP BY demand_source;

-- New opportunity count (before vs after)
SELECT COUNT(*) FROM opportunity_items;

-- Spot check: items that now appear
SELECT i.name, l.name as location, mdr.buy_from_sell_period, mdr.demand_source
FROM market_demand_resolved mdr
JOIN items i ON i.id = mdr.type_id
JOIN locations l ON l.id = mdr.location_id
WHERE mdr.demand_source = 'npc_station_period'
LIMIT 10;
```

## Loop Control
STOP
