# Current task

Run profiling script for AFTER measurements to capture post-cleanup performance.

# End goal with specs

## Context

`refresh_target_markets_from_adam()` in `backend/app/services/demand/market_demand.py` already has a working SQL-based bulk INSERT...ON CONFLICT path (`_TARGET_MARKET_REFRESH_SQL`, lines 77-147). The main sync flow at `service.py:1198` already uses it.

However, `_generate_trade_period()` at `service.py:2611` still calls `_refresh_market_demand_for_keys()` → `refresh_npc_keys_from_adam()` which loops per (location_id, type_id) in Python — the old slow path.

## What to do

### 1. Profile the BEFORE state
Write a small standalone profiling script at `backend/scripts/profile_demand.py` that:
- Connects to the real local DB (use docker compose exec or direct psql connection)
- Calls `refresh_target_markets_from_adam` for all configured target stations + source regions (read from user_settings)
- Times it over a couple hundred iterations (or at least measures the wall-clock time for 1 full pass)
- Records: total time, rows affected, rows/sec
- Save output to `/tmp/demand_profile_before.txt`

Run this BEFORE making changes.

### 2. Switch `_generate_trade_period` to use SQL path
In `service.py` around line 2610-2615, replace:
```python
self._refresh_market_demand_for_keys(
    session,
    demand_keys=[(target_location.id, current_type_id) for current_type_id in type_ids],
    period_days=requested_period_days,
)
```
With a call to `_refresh_market_demand_for_target_markets` using the target location and its source region. You'll need to derive the source_region_ids — read the settings like the main sync does, or get the region from the target location.

### 3. Add stale row cleanup
After the INSERT...ON CONFLICT in `refresh_target_markets_from_adam`, add a DELETE for `market_demand_resolved` rows WHERE:
- `location_id` IN target_location_ids
- `period_days` = period_days  
- `demand_source` = 'adam4eve'
- NOT EXISTS in the current Adam raw data for that station+type

This ensures items that lost Adam coverage get cleaned up.

### 4. Profile the AFTER state
Run the same profiling script after changes. Save to `/tmp/demand_profile_after.txt`.

### 5. Run tests
`docker compose exec backend python -m pytest` — all must pass.

## File ownership
- YOU OWN: `backend/app/services/demand/market_demand.py`, `backend/app/services/sync/service.py`
- YOU CREATE: `backend/scripts/profile_demand.py`

## Constraints
- Do NOT change opportunity generation logic (generation.py) without explicit approval
- Do NOT alter existing DemandSource enum values
- All demand resolution changes must be backward-compatible
- Run tests: `docker compose exec backend python -m pytest`

# Roadmap (Completed)
- SQL-based bulk path (_TARGET_MARKET_REFRESH_SQL) already implemented
- Main sync flow already switched to SQL path

# Roadmap (Upcoming)
- Profile before state, switch remaining caller, add cleanup, profile after

# Backlog
- [x] Write and run profiling script for BEFORE measurements (SQL: 1.8s/21633 rows; per-key: ~1046s; 590x speedup)
- [x] Switch _generate_trade_period to use _refresh_market_demand_for_target_markets
- [x] Add stale row cleanup DELETE after INSERT...ON CONFLICT
- [ ] Run profiling script for AFTER measurements <- current
- [ ] Run full test suite and confirm 0 failures
- [ ] Commit all changes with descriptive message
