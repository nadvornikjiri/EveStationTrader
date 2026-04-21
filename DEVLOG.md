## 2026-04-19

- task id: `SETTINGS-SCOPED-STRUCTURE-ESI-SYNC-2026-04-19`
- title: Restrict Structure ESI Sync To Selected Target Markets
- status: `PASS_WITH_EXISTING_FAILURES`
- summary: added a real authenticated structure-market pull path and wired it into `SyncService` by default, but scoped it strictly to structure targets selected in settings. `structure_snapshot_sync` now derives its workset from `target_market_location_ids`, auto-upserts selected structure targets into `tracked_structures`, and ignores unselected tracked structures. The default snapshot client reuses connected-character tokens, prefers characters already known to have access to the structure, fetches `/markets/structures/{structure_id}/`, and records snapshot times back onto `character_accessible_structures` when pulls succeed.
- validation:
  - `docker compose exec -T backend python -m ruff check app/services/esi/client.py app/services/sync/service.py tests/services/test_sync_service.py --fix`
  - `docker compose exec -T backend python -m mypy app/services/esi/client.py app/services/sync/service.py`
  - `docker compose exec -T backend python - <<'PY' ... SyncService(...).trigger_job(\"structure_snapshot_sync\") ... PY`
  - note: the direct Postgres-backed verification confirmed only the selected structure target was polled and unselected tracked structures were ignored
  - note: targeted integration `pytest` remains blocked inside the backend container by the existing `tests/db_test_utils.py` bootstrap/cwd issue

- task id: `STRUCTURE-ESI-FALLBACK-SCOPE-2026-04-19`
- title: Include Structure Targets In ESI History Fallback Scope
- status: `PASS_WITH_EXISTING_FAILURES`
- summary: fixed a scope bug in `_esi_demand_refresh_keys()` that excluded structure targets from the ESI-history fallback refresh path. Structure targets now participate in the history-based key union, so items with regional ESI history but no local structure snapshot data can still derive `market_demand_resolved` rows and reach opportunity generation. Added regression coverage for a structure-target history-only item case mirroring the missing `Polarized Rocket Launcher` behavior.
- validation:
  - `docker compose exec -T backend python -m ruff check app/services/sync/service.py tests/services/test_sync_service.py --fix`
  - `docker compose exec -T backend python -m mypy app/services/sync/service.py tests/services/test_sync_service.py`
  - `docker compose exec -T backend python - <<'PY' ... SyncService()._esi_demand_refresh_keys(session) ... PY`
  - note: targeted `mypy` still reports pre-existing unrelated failures in `app/services/npc_stations/deltas.py`, `app/services/opportunities/generation.py`, and older sections of `tests/services/test_sync_service.py`
  - note: targeted integration `pytest` is currently blocked inside the backend container because `tests/db_test_utils.py` resolves `REPO_ROOT` incorrectly under the container mount and then fails Alembic/Docker-based test bootstrap

## 2026-04-17

- task id: `STATIC-STRUCTURE-TARGET-SETTINGS-2026-04-17`
- title: Auto-Include Static Catalog Targets In Active Settings
- status: `PASS_WITH_EXISTING_FAILURES`
- summary: fixed the gap between static structure import and the trade target dropdown. The trade UI reads `/api/targets`, which is driven by persisted `target_market_location_ids`, so importing structure `locations` alone was not enough on existing installs. Settings loading now unions the built-in static structure catalog IDs into the configured target list, so curated public structures like the Amamake entries become active trade targets without manual settings edits.
- validation:
  - `cd backend && ./.venv/bin/python - <<'PY' ... SettingsService().get_settings() ... PY`
  - `cd backend && ./.venv/bin/python - <<'PY' ... TradeRepository().list_targets() ... PY`
  - `cd backend && ./.venv/bin/pytest -o addopts='' tests/api/test_endpoints.py::test_get_settings -q`
  - `cd backend && ./.venv/bin/ruff check app/services/settings_service.py tests/api/test_endpoints.py --fix`
  - note: repo-wide `mypy .` still has pre-existing unrelated failures in `app/services/opportunities/generation.py`, `app/services/npc_stations/deltas.py`, multiple `alembic/versions/*` files, `tests/services/test_auth_service.py`, and `tests/services/test_sync_service.py`

- task id: `STATIC-STRUCTURE-CATALOG-2026-04-17`
- title: Seed Static Public Structure Targets
- status: `PASS_WITH_EXISTING_FAILURES`
- summary: added a built-in static public-structure catalog to the foundation import and used it to seed Amamake structure `locations` without waiting for character sync or market-order discovery. Foundation bootstrap now upserts existing structure locations in place, so placeholder names like `Structure <id>` are replaced by the static catalog on rerun instead of being left stale. Added regression coverage for catalog merging and placeholder-structure name backfill.
- validation:
  - `cd backend && ./.venv/bin/pytest -m integration tests/services/test_foundation_import.py -q`
  - `cd backend && ./.venv/bin/pytest -m integration tests/services/test_foundation_data.py -q`
  - `cd backend && ./.venv/bin/ruff check . --fix`
  - `cd backend && ./.venv/bin/pytest`
  - `cd backend && ./.venv/bin/mypy .`
  - note: `mypy .` is still blocked by pre-existing unrelated errors in `app/services/opportunities/generation.py`, `app/services/npc_stations/deltas.py`, multiple `alembic/versions/*` files, `tests/services/test_auth_service.py`, and `tests/services/test_sync_service.py`

## 2026-04-15

- task id: `EVEREF-ESI-DEMAND-PROFILING-2026-04-15`
- title: Reduce EVE Ref ESI Demand Refresh Query Churn
- status: `PASS_WITH_EXISTING_FAILURES`
- summary: added a reproducible benchmark script for the `everef_history_sync` ESI demand refresh loop and then landed two verified optimizations. Commit `bd2b6c8` stopped rebuilding Adam-coverage ID maps via thousands of `session.get()` calls after the bulk preload, which cut the 1000-key benchmark from `16.773s` to `5.478s` by reducing preload time from `13.082s` to `1.765s`. Commit `438fb49` added a batch preload context in `MarketDemandResolutionService` that holds strong references to `Location`/`Item` rows, preloads ESI history by `(region_id, type_id)`, and reuses existing `MarketDemandResolved` rows, which cut the same benchmark again from `5.478s` to `2.417s`; the per-key loop itself dropped from `3.714s` to `0.128s`.
- validation:
  - `cd backend && ./.venv/bin/python scripts/profile_refresh_esi_demand.py --limit 1000 --profile --profile-lines 30`
  - `cd backend && ./.venv/bin/pytest -o addopts='' tests/services/test_sync_service.py::test_everef_history_sync_preload_keeps_esi_demand_values_correct -q`
  - `cd backend && ./.venv/bin/pytest -o addopts='' tests/services/test_market_demand.py::test_upsert_for_location_preload_matches_non_preloaded_result tests/services/test_sync_service.py::test_everef_history_sync_preload_keeps_esi_demand_values_correct -q`
  - `cd backend && ./.venv/bin/ruff check . --fix`
  - `cd backend && ./.venv/bin/mypy .`
  - `cd backend && ./.venv/bin/pytest`
  - note: `mypy .` is still blocked by pre-existing unrelated errors in `app/services/npc_stations/deltas.py`, `alembic/versions/20260409_0013_widen_esi_history_volume.py`, and `alembic/versions/20260409_0012_restore_esi_history_daily.py`

## 2026-04-11

- task id: `ESI-DEMAND-IDENTITY-PRELOAD-2026-04-11`
- title: Pre-load ESI Demand Location And Item Identity Map
- status: `PASS_WITH_EXISTING_FAILURES`
- summary: pre-loaded all `Location` and `Item` rows referenced by `_esi_demand_refresh_keys()` before the ESI demand refresh loop in `everef_history_sync`, so the downstream `session.get()` calls in `MarketDemandResolutionService` are served from SQLAlchemy's identity map instead of issuing per-key lookups. Added a regression test that exercises the EVE Ref history sync path and verifies the preload change still writes the expected `esi_live` demand row and `buy_from_sell_period` value.
- validation:
  - `cd backend && ./.venv/bin/ruff check . --fix`
  - `cd backend && ./.venv/bin/mypy .`
  - `cd backend && ./.venv/bin/pytest`
  - `cd backend && ./.venv/bin/pytest -o addopts='' tests/services/test_sync_service.py::test_everef_history_sync_preload_keeps_esi_demand_values_correct`
  - note: `mypy .` is still blocked by pre-existing errors in `app/services/npc_stations/deltas.py`, `alembic/versions/20260409_0013_widen_esi_history_volume.py`, and `alembic/versions/20260409_0012_restore_esi_history_daily.py`

## 2026-04-11

- task id: `REMOVE-LEGACY-ESI-HISTORY-SYNC-2026-04-11`
- title: Remove Legacy ESI History Sync
- status: `PASS_WITH_EXISTING_FAILURES`
- summary: removed the retired `esi_history_sync` path now that `everef_history_sync` is in place. This deleted the old ESI history ingestion service, removed `fetch_regional_history()` from the ESI client, stripped the sync-service dispatch/clear-data/inline-refresh hooks, dropped `EsiHistorySyncState` from the ORM and exports, added Alembic migration `20260411_0016` to drop `esi_history_sync_state`, replaced the manual sync action with `Sync EVE Ref History Now`, and removed obsolete API/client/service tests for the legacy path.
- validation:
  - `cd backend && ./.venv/bin/ruff check . --fix`
  - `rg -n "esi_history_sync|EsiHistorySyncState|EsiRegionalHistoryIngestionService|fetch_regional_history|_sync_esi_history" backend/app backend/tests frontend/src`
  - `cd backend && ./.venv/bin/mypy app/`
  - `cd backend && ./.venv/bin/pytest tests/`
  - note: `mypy app/` is still blocked by pre-existing errors in `app/services/opportunities/aggregator.py`, `app/services/npc_stations/deltas.py`, `app/services/demand/market_demand.py`, and `app/repositories/trade_repository.py`
  - note: `pytest tests/` is still blocked by pre-existing failures in `tests/services/test_adam4eve_client.py`, `tests/services/test_aggregator.py`, and `tests/workers/test_sync_tasks.py`

## 2026-03-27

- task id: `ADAM4EVE-FILE-IMPORT-LOGGING-2026-03-27`
- title: Log Adam4EVE File Downloads And Cache Hits
- status: `PASS`
- summary: added explicit bulk-import logging so Adam4EVE demand/history file activity now emits one log line per file showing whether the import used a cache hit or performed a fresh download, along with the import kind, remote path, local cache path, and coverage date/byte count. SQL query logging remains in place separately through the database logger so the import's file-fetch phase and subsequent DB work are both visible in Docker logs.

## 2026-03-27

- task id: `DOCKER-REQUEST-SQL-LOGGING-2026-03-27`
- title: Add Backend Request And SQL Logging For Docker
- status: `PASS`
- summary: implemented the backlog logging task so backend Docker logs now include one app-level HTTP request line per REST call plus SQL query logging with statement text, parameters, and duration. FastAPI request logging is installed at app startup, SQLAlchemy engine hooks emit query timing logs, and deterministic backend tests verify both logging paths are wired.

## 2026-03-27

- task id: `ADAM4EVE-HISTORY-BLANK-ROWS-2026-03-27`
- title: Skip Blank Adam4EVE Regional History Price Rows
- status: `PASS`
- summary: investigated why `adam4eve_sync` was not populating `market_price_period` and found the regional-history client can hit live CSV rows with blank sell-price fields. The parser now skips those malformed rows instead of aborting the entire history import, which unblocks reruns after ESI market orders have populated the eligible region/type scopes used for Adam4EVE history selection.

## 2026-03-27

- task id: `ESI-ORDER-DELETE-BATCHING-2026-03-27`
- title: Batch ESI Market Order Deletes For Full-Region Syncs
- status: `PASS`
- summary: fixed the `esi_market_orders_sync` full-region failure where PostgreSQL rejected a giant `order_id IN (...)` delete with more than 65,535 bound parameters. The ingestion path now deletes seen/stale order IDs in bounded batches and still clears the region snapshot before re-copying the downloaded rows, preserving rerun semantics without building oversized delete statements.

## 2026-03-27

- task id: `ADAM4EVE-DATABASE-VISIBILITY-2026-03-27`
- title: Clarify Adam4EVE Location Coverage In Database Browser
- status: `PASS`
- summary: verified the live `adam_npc_demand_daily` table contains many stations, not a single location, and updated the database diagnostics endpoint to enrich Adam4EVE demand rows with resolved station and item metadata. The database page now shows internal FK values alongside EVE station IDs, location names, region/system names, and item names so imported coverage is immediately visible and no longer looks like a one-location sync.

## 2026-03-27

- task id: `SYNC-CLEAR-ACTIONS-2026-03-27`
- title: Add Clear Data Actions To Sync Dashboard
- status: `PASS`
- summary: added a first-row set of clear-data actions above the manual sync buttons on the sync dashboard, with backend `/api/sync/clear/{job_type}` support for each sync family. The clear actions now remove the relevant persisted tables for foundation/SDE, Adam4EVE, NPC orders, structure snapshots, character sync outputs, and opportunities, and the UI surfaces pending/error feedback for those clear requests the same way it does for run/cancel actions.

## 2026-03-27

- task id: `ADAM4EVE-EXPORT-COVERAGE-2026-03-27`
- title: Use Actual Adam4EVE Export Coverage Dates
- status: `PASS`
- summary: fixed Adam4EVE weekly export completion tracking to use the latest `scanDate` present in the CSV instead of assuming the ISO week always covers through Sunday. This resolves the live `2026-13` case where the file only contains data through 2026-03-26 even though week 13 nominally ends on 2026-03-29, which had been leaving regions falsely marked incomplete and repeatedly rechecked with zero new rows.

## 2026-03-27

- task id: `ADAM4EVE-SYNC-REGRESSION-2026-03-27`
- title: Limit Adam4EVE Demand Refresh To Imported Keys
- status: `PASS`
- summary: fixed the Adam4EVE post-download stall by stopping `adam4eve_sync` from brute-forcing demand resolution across every NPC station and item after each import. The sync now refreshes only the `(location_id, type_id, period_days)` keys touched by imported Adam rows, while keeping the cached-file vs successful-import cursor split intact so already imported dates/exports are skipped only after successful ingestion. Added regression coverage for targeted demand refresh and updated the Adam4EVE client/cache path so session-backed syncs still use persisted bulk-file caching while direct client tests stay isolated.

## 2026-03-26

- task id: `T26`
- title: Market Groups Import
- status: `PASS`
- summary: ESI client now resolves real group_name and category_name for items instead of storing raw group_id. Added `_resolve_group()` and `_resolve_category()` methods that fetch `/universe/groups/{id}/` and `/universe/categories/{id}/`, with in-memory caching to avoid duplicate requests. Graceful fallback on resolution failure. Test updated to verify "Mineral" group and "Material" category are resolved for Tritanium.

## 2026-03-26

- task id: `T28`
- title: Initial Sync Job Enqueue on Character Connect
- status: `PASS`
- summary: after a new character is connected via EVE SSO, the auth callback now enqueues a `character_sync` SyncJobRun with status "pending" and triggered_by "sso_connect". Re-authenticating an existing character does not create duplicate jobs (sync state already exists check). Tests verify job creation on first connect and no duplicates on re-auth.

## 2026-03-26

- task id: `T25`
- title: Settings Page Polish
- status: `PASS`
- summary: expanded the settings page from 4 fields to all 9 spec-required settings plus 4 default filter fields. All numeric inputs now use `type="number"` with proper `min`/`max`/`step` constraints. Added controls for: min confidence for local demand, structure poll interval, snapshot retention days, fallback policy (select), shipping cost per m3. Default filters section uses a fieldset with labeled inputs for min item profit, min order margin %, min ROI, and min demand/day.

## 2026-03-26

- task id: `T22`
- title: Full Confidence Gating
- status: `PASS`
- summary: implemented the spec's MVP confidence gate: observation_window >= 72h requirement. Added `observation_factor = min(observation_window_hours / 72, 1.0)` to the confidence formula in `demand_periods.py`, making `confidence_score = coverage_pct * recency_factor * observation_factor`. Structures with < 72h of observation data now produce confidence below the 0.75 threshold, correctly falling back to regional demand. Added test verifying sub-72h observation windows are penalized. Updated existing test data to span 94h (>72h) with corrected expected values.

## 2026-03-26

- task id: `T23`
- title: ESI Rate Limit Sync Status Card
- status: `PASS`
- summary: added ESI rate limit status card to the sync dashboard. The card reads shared `EsiRateLimitState` from `EsiClient.get_rate_limit_state()` and displays error_limit_remain as a progress bar (out of 100), total requests, cached responses, error-limited count, and reset timer. Status shows "degraded" when backoff threshold is hit. Integrates seamlessly with existing StatusCards component.

## 2026-03-26

- task id: `T18`
- title: Characters Page Frontend
- status: `PASS`
- summary: wired CharactersPage and CharacterDetailPage to the backend API. Created `types/characters.ts`, `api/characters.ts`, `hooks/useCharacterData.ts` with React Query hooks for list, detail, connect, sync, patch, and track-structure mutations. CharactersPage shows all 11 spec columns (character name with link, corporation, scopes count, sync status, token refresh, last sync, per-domain sync statuses, accessible structure count). CharacterDetailPage shows identity, sync toggles, accessible structures table with all 9 spec columns plus track action, and skills. Added `apiPatch` to client.ts. Tests verify column rendering, empty state, and connect flow.

## 2026-03-26

- task id: `T17`
- title: Trade Page Missing Columns
- status: `PASS`
- summary: expanded both `SourceSummaryTable` and `ItemOpportunityTable` to display all 22 spec-required columns each. Source summary now shows: Source Units Available, Target Supply Units, Target D.O.S, In Transit, Assets, Active Sell Orders, Source Avg Price, Target Now Price, Target Period Avg Price, Target Period Profit, ROI Period, Item Volume, Shipping Cost, Demand Source. Item table now shows: Sec, Source Units Available, Target Demand/Day, Target Supply Units, Target D.O.S, In Transit, Assets, Active Sell Orders, all price columns, ROI Period, Item Volume, Shipping Cost. Added `table-scroll` wrapper for horizontal scrolling. Test verifies all column headers render.

## 2026-03-26

- task id: `T16`
- title: Trade Page Missing Filters
- status: `PASS`
- summary: added all spec-required filters to the trade page: min profit (ISK), min margin %, min demand/day, max D.O.S, min confidence, source type (NPC/structure/all), min security (highsec/lowsec/nullsec/all), and demand source (adam4eve/local/fallback/blended/all). Filters are client-side against the existing opportunity items query. Updated `TradeControls` with new inputs/selects and `TradePage` with filter state and useMemo filtering logic. Added test covering all new filter behaviors.

## 2026-03-26

- task id: `T15`
- title: ESI Rate Limiting
- status: `PASS`
- summary: added first-class ESI rate limiting to `EsiClient`: tracks `X-ESI-Error-Limit-Remain`/Reset headers on every response, backs off when remain drops below 20, supports ETag/If-None-Match caching, implements exponential backoff on 5xx and 420 responses with configurable retries. Rate limit state is shared across all client instances and exposes a `to_dict()` for the sync status card. All existing ESI fetch methods now route through `_request_with_rate_limit()`.

## 2026-03-26

- task id: `T14`
- title: Wire Live Order Book Into Item Detail Panel
- status: `PASS`
- summary: replaced empty placeholder order lists in `get_item_detail()` with real queries against `esi_market_orders`. Target sell orders sorted ascending by price with cumulative volume, source sell orders ascending, source buy orders descending. Added `_query_orders` helper to TradeRepository. New test covers full order book population.

## 2026-03-26

- task id: `T13`
- title: Wire Live Order Data Into Opportunity Generation
- status: `PASS`
- summary: replaced hardcoded zero placeholders for `source_units_available` and `target_supply_units` with aggregated sell-side volume from `esi_market_orders`. This makes `purchase_units`, `target_dos`, and all dependent summary fields reflect real market liquidity. Added tests for both populated-order and zero-order edge cases.

## 2026-03-22

- task id: `T05F`
- title: Computed Source Endpoint Resolution
- status: `PASS`
- summary: rewired the source endpoint to resolve only persisted computed source markets for the selected target/period and added repository/API coverage for both populated and empty scopes.

## 2026-03-22

- task id: `T05E`
- title: Remove Placeholder Opportunity List Fallbacks
- status: `PASS`
- summary: removed placeholder trade-list rows now that the computed opportunity pipeline exists, and added deterministic backend/frontend empty-state coverage for targets with no computed opportunities.

## 2026-03-22

- task id: `T11`
- title: Structure Snapshots And Demand Inference closeout
- status: `PASS`
- summary: reconciled the parent structure-demand packet now that snapshot persistence, delta aggregation, confidence-gated local demand resolution, and sync orchestration are all implemented and tested.

## 2026-03-22

- task id: `T10`
- title: Live Ingestion And Opportunity Computation closeout
- status: `PASS`
- summary: reconciled the parent live-ingestion packet now that the public Adam4EVE/ESI clients, persisted compute pipelines, and sync-driven opportunity rebuild flow are all complete and tested.

## 2026-03-22

- task id: `T07`
- title: Characters, Auth, And Multi-User Support closeout
- status: `PASS`
- summary: reconciled the parent auth/characters packet now that persisted character flows, linking behavior, connect/login entrypoints, and mocked structure discovery sync are all implemented and tested.

## 2026-03-22

- task id: `T06`
- title: Sync Operations Dashboard closeout
- status: `PASS`
- summary: reconciled the parent sync-dashboard packet now that manual jobs, persisted history, fallback diagnostics, and worker heartbeat reporting are grounded in real stored state.

## 2026-03-22

- task id: `T04`
- title: Foundation Data Bootstrap closeout
- status: `PASS`
- summary: reconciled the parent foundation-bootstrap packet now that the seeded persistence path, operational sync entrypoint, idempotence coverage, and source abstractions are all complete.

## 2026-03-22

- task id: `T09`
- title: Testing Baseline quality-gate completion
- status: `PASS`
- summary: made the backend `uv sync` workflow install the repo quality gates by default and aligned the task/docs so the baseline test packet is operationally complete.

## 2026-03-21

- task id: `T11D`
- title: Structure Snapshot Sync Orchestration
- status: `PASS`
- summary: added a structure snapshot sync job that reuses the existing snapshot, delta, and demand-period services and stays deterministic on reruns.

## 2026-03-21

- task id: `T10I`
- title: Live Adam4EVE NPC Demand Client
- status: `PASS`
- summary: replaced the mocked Adam4EVE NPC-demand client with a public export fetcher and added deterministic client tests for request shape, aggregation, and malformed CSV handling.

## 2026-03-21

- task id: `T10H`
- title: Live ESI Regional History Client
- status: `PASS`
- summary: replaced the mocked regional-history fetcher with a public ESI client and added deterministic client tests for request, empty, and malformed payload handling.

## 2026-03-21

- task id: `T10G`
- title: Scheduler-Driven Opportunity Rebuild
- status: `PASS`
- summary: replaced the worker rebuild placeholder with the real persisted rebuild path and added focused worker tests for delegation and scheduler registration.

## 2026-03-21

- task id: `T04B`
- title: File-Backed Foundation Snapshot Source
- status: `PASS`
- summary: added a validated file-backed foundation seed source plus snapshot fixture coverage, while keeping the curated in-code provider as the default bootstrap path.

## 2026-03-21

- task id: `T06D`
- title: Persisted Worker Health Card
- status: `PASS`
- summary: replaced the synthetic worker card with a persisted heartbeat-backed card and covered fresh, stale, and missing-heartbeat cases in backend tests.

## 2026-03-21

- task id: `T06C`
- title: Persisted Fallback Diagnostics
- status: `PASS`
- summary: replaced synthetic fallback diagnostics with persisted tracked-structure and structure-demand rows, while keeping empty and NPC-excluded cases deterministic.

## 2026-03-21

- task id: `T07G`
- title: Character Sync Route Triggers Structure Discovery
- status: `PASS`
- summary: wired the character sync route into the mocked discovery path, updated sync-state timestamps/status, and validated the route with deterministic backend tests.

## 2026-03-21

- task id: `T07F`
- title: Persist Accessible Structure Discovery From Character Sync Inputs
- status: `PASS`
- summary: added a character-service discovery upsert that deduplicates resolved structures, preserves existing tracking flags, and refreshes accessible-structure metadata in place.

## 2026-03-21

- task id: `T07E`
- title: Character Connect Entry Point
- status: `PASS`
- summary: routed `/api/characters/connect` through the shared EVE SSO login payload helper and added API tests that keep it aligned with `/api/auth/login`.

## 2026-03-21

- task id: `T07D`
- title: Link Additional EVE SSO Characters To Existing User
- status: `PASS`
- summary: linked second-character SSO callbacks to the existing user under the current single-user MVP assumption, while preserving repeat-callback update behavior and duplicate prevention.

## 2026-03-21

- task id: `T07C`
- title: Persisted Character Structure Tracking Flag
- status: `PASS`
- summary: persisted `tracking_enabled=True` for accessible structures, added idempotent re-track behavior, and covered missing-character and missing-access cases in backend tests.

## 2026-03-21

- task id: `T07B`
- title: Persisted Character Sync Toggle Updates
- status: `PASS`
- summary: persisted `sync_enabled` updates on `esi_characters`, added no-op and missing-character handling, and covered the patch/read-after-write path with backend tests.

## 2026-03-21

- task id: `T07A`
- title: Persisted Character Reads
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 5, 11, 12B, 14
- acceptance criteria covered:
  - `CharacterService.list_characters()` now reads persisted `esi_characters` rows and joins sync-state data
  - accessible structure counts now come from persisted `character_accessible_structures`
  - `CharacterService.get_character(character_id)` now returns persisted detail and structures for the requested public EVE character id
  - missing characters now fail deterministically with a not-found path instead of returning demo data
  - deterministic backend tests cover list, detail, structure mapping, and missing-character behavior
- files changed:
  - `backend/app/services/characters/service.py`
  - `backend/app/api/routes/characters.py`
  - `backend/tests/services/test_character_service.py`
  - `backend/tests/api/test_endpoints.py`
  - `TASKS.md`
- short implementation summary: Replaced the demo-backed character read path with persisted character, sync-state, and accessible-structure queries so the characters API now reflects stored auth data.
- important decisions:
  - character list/detail IDs are exposed as public EVE `character_id` values rather than internal database row ids
  - missing-character reads raise a deterministic 404 path through the API layer
  - sync toggles are still projected from the shared `sync_enabled` flag until per-domain preference persistence exists
- open follow-ups:
  - persist per-domain sync toggle settings instead of mirroring a single `sync_enabled` flag
  - populate character skills from real sync data rather than an empty placeholder list
  - add structure discovery and tracking flows that write `character_accessible_structures` end to end

## 2026-03-21

- task id: `T05D`
- title: Trade Page Item Detail Selection
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 1, 14, 15, 17.2
- acceptance criteria covered:
  - the trade page now selects a deterministic default item from the filtered item-result set
  - selecting a different item row requeries item detail for the active target, source, type, and period scope
  - the execution-context panel now renders API-backed order rows and key metrics for the selected item
  - item selection resets safely when control changes remove the currently selected row
  - frontend tests cover default detail loading, row-driven detail changes, and selection reset behavior
- files changed:
  - `frontend/src/api/trade.ts`
  - `frontend/src/hooks/useTradeData.ts`
  - `frontend/src/types/trade.ts`
  - `frontend/src/components/trade/ItemOpportunityTable.tsx`
  - `frontend/src/components/trade/ItemDetailPanel.tsx`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
  - `frontend/src/styles/global.css`
  - `TASKS.md`
- short implementation summary: Connected the trade-page item table to the existing item-detail API so the execution-context panel now follows the selected opportunity instead of remaining static scaffold text.
- important decisions:
  - the selected item defaults to the first row in the current filtered-and-sorted item list
  - selection resets automatically whenever filters or source/target changes remove the currently selected row
  - the detail panel intentionally renders the backend-provided placeholder order stacks without changing the backend contract
- open follow-ups:
  - add keyboard and screen-reader friendly row-selection controls beyond pointer-based row clicks
  - replace placeholder order rows with live order-book-derived detail when ingestion exists
  - add item-detail loading and empty-state polish beyond the current lightweight panel states

## 2026-03-21

- task id: `T05C`
- title: Trade Page Controls And Client-Side Filtering
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 1, 14, 15, 17.2
- acceptance criteria covered:
  - target-market and analysis-period controls now drive the source-summary and item queries
  - item search applies a case-insensitive substring filter before rendering item rows
  - min ROI and warning-threshold controls filter weaker rows deterministically from loaded query results
  - sortable item-table columns now change rendered row order deterministically
  - frontend tests cover default filtering, control-driven requeries, source reset behavior, and sortable row rendering
- files changed:
  - `frontend/package.json`
  - `frontend/package-lock.json`
  - `frontend/src/api/trade.ts`
  - `frontend/src/hooks/useTradeData.ts`
  - `frontend/src/components/trade/TradeControls.tsx`
  - `frontend/src/components/trade/ItemOpportunityTable.tsx`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
  - `frontend/src/styles/global.css`
  - `frontend/src/vite-env.d.ts`
  - `backend/app/services/auth/service.py`
  - `TASKS.md`
- short implementation summary: Wired the trade-page controls into the active query state and added deterministic client-side item filtering and sorting so the main trade workflow is more interactive without changing the backend contract.
- important decisions:
  - `period_days` is now part of the frontend trade-query contract for source summaries and item rows
  - warning-threshold filtering currently uses `risk_pct` as a client-side max-risk gate rather than recomputing backend warning flags
  - source selection resets automatically when a target or period change removes the previously selected source from the result set
- open follow-ups:
  - move the remaining trade filters to typed backend query parameters when the API surface is expanded
  - wire item-row selection into the detail panel so the lower-right pane reflects the chosen opportunity
  - add source-level filtering for security, demand source, and source type

# DEVLOG.md

Imported baseline entries for work completed before `AGENTS.md` adoption. These entries reflect the current repository state and validation evidence, not historical certainty about when the original implementation happened.

## 2026-03-20

- task id: `T11C`
- title: Structure-Local Demand Resolution
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 3, 8, 10, 13, 17.3
- acceptance criteria covered:
  - structure targets now resolve local demand from persisted `structure_demand_period` rows when confidence is sufficient
  - insufficient-confidence structure targets still persist `regional_fallback`
  - NPC demand resolution remains unchanged
  - deterministic tests cover sufficient-confidence local demand, insufficient-confidence fallback, and NPC no-regression behavior
- files changed:
  - `backend/app/services/demand/market_demand.py`
  - `backend/tests/services/test_market_demand.py`
  - `TASKS.md`
- short implementation summary: Extended market demand resolution so structure locations can now consume persisted local demand periods instead of always falling back.
- important decisions:
  - structure-local demand is currently gated by explicit `coverage_pct >= 0.75` and `confidence_score >= 0.75`
  - NPC resolution behavior was left untouched
  - structure fallback remains the temporary zero-demand regional placeholder until real CCP fallback demand is wired in
- open follow-ups:
  - replace the temporary fallback placeholder with real CCP-derived fallback demand
  - drive structure demand updates from periodic snapshot jobs
  - use the resolved local demand rows in broader opportunity rebuild coverage

## 2026-03-20

- task id: `T11B`
- title: Structure Demand Period Aggregation
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 8, 13, 17.3
- acceptance criteria covered:
  - a service now reads persisted `structure_order_deltas` and upserts `structure_demand_period` rows
  - `demand_min`, `demand_max`, and `demand_chosen` are computed deterministically from inferred trade units
  - `coverage_pct` and `confidence_score` are persisted using a deterministic MVP rule
  - reruns update the same `(structure_id, type_id, period_days)` row instead of duplicating it
  - deterministic tests cover aggregation and rerun behavior
- files changed:
  - `backend/app/services/structures/demand_periods.py`
  - `backend/tests/services/test_structure_demand_periods.py`
  - `TASKS.md`
- short implementation summary: Added the aggregation layer that turns persisted structure order deltas into `structure_demand_period` rows for later local-demand resolution.
- important decisions:
  - MVP demand aggregation uses deterministic averages over the selected period window
  - coverage and confidence are intentionally simple heuristics for now
  - reruns update the existing structure/type/period row instead of appending duplicates
- open follow-ups:
  - feed structure demand periods into `market_demand_resolved`
  - tighten confidence gating to match the longer-window product rules
  - drive these aggregations from structure snapshot sync jobs

## 2026-03-20

- task id: `T11A`
- title: Structure Snapshot Persistence And Deltas
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 8, 13, 17.3
- acceptance criteria covered:
  - a structure snapshot batch with orders can now be persisted
  - two snapshots for the same structure can be diffed into persisted `structure_order_deltas`
  - inferred trade side and units follow the existing basic buy/sell reduction rules
  - deterministic tests cover snapshot persistence and delta computation
  - no live HTTP integration was introduced in this slice
- files changed:
  - `backend/app/services/structures/snapshots.py`
  - `backend/tests/services/test_structure_snapshots.py`
  - `TASKS.md`
- short implementation summary: Added the first real persistence layer for structure market snapshots and the delta records needed to support later local demand inference.
- important decisions:
  - matching-order reductions reuse the existing inference helper
  - disappeared orders are recorded conservatively with `disappeared=True` and no inferred trade side/units
  - timestamps are normalized to UTC-aware values at the service boundary
- open follow-ups:
  - aggregate deltas into `structure_demand_period`
  - add structure snapshot sync orchestration
  - integrate structure-local demand into market demand resolution

## 2026-03-20

- task id: `T06B`
- title: History-Backed Sync Status Cards
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 12A, 14, 17.4
- acceptance criteria covered:
  - sync status cards now derive `last_successful_sync` and `recent_error_count` from persisted `sync_job_runs` for implemented job types
  - cards remain stable when no history exists
  - deterministic backend tests cover history-backed and no-history cases
  - scope stayed backend-only
- files changed:
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_sync_service.py`
  - `TASKS.md`
- short implementation summary: Replaced hardcoded sync status timestamps with job-history-backed values for the implemented manual sync paths, while keeping idle defaults for untouched scopes.
- important decisions:
  - history-backed timestamps are normalized to UTC-aware values at the service boundary
  - the worker card remains a safe default placeholder for now
  - error counts currently reflect persisted failed job rows for the implemented sync types
- open follow-ups:
  - derive worker health and scheduler timing from real runtime state
  - replace synthetic fallback diagnostics
  - add ESI rate-limit status reporting

## 2026-03-20

- task id: `T05B`
- title: Precise Item Detail Resolution
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 1C, 14, 17.2
- acceptance criteria covered:
  - `get_item_detail()` now resolves the requested public EVE `type_id` from persisted opportunity rows when available
  - fallback detail remains consistent for the requested public `type_id`
  - deterministic tests cover both computed and fallback item-detail paths
  - no unrelated frontend changes were needed
- files changed:
  - `backend/app/repositories/trade_repository.py`
  - `backend/tests/services/test_trade_repository.py`
  - `TASKS.md`
- short implementation summary: Fixed item-detail lookup so the selected item is resolved correctly from computed opportunity rows and public item IDs are preserved consistently in the response.
- important decisions:
  - public API `type_id` values are translated through `Item.type_id` when resolving persisted opportunity rows
  - fallback detail now builds placeholder metrics for the requested item instead of reusing the first placeholder row
  - computed order metrics and placeholder order panels are kept internally consistent even though order books are still mocked
- open follow-ups:
  - replace placeholder order-book panels with real persisted order context
  - surface computed detail behavior through richer trade-page interactions

## 2026-03-20

- task id: `T10F`
- title: Sync-Driven Opportunity Rebuild
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 12A, 14, 17.2, 17.4
- acceptance criteria covered:
  - manual `opportunity_rebuild` now runs the persisted opportunity-generation path over computed price and demand rows
  - rebuild jobs persist meaningful `sync_job_runs` metadata including `records_processed` and message text
  - deterministic backend tests cover the manual rebuild path creating opportunity rows and a sync job record
  - the rebuild path operates on computed tables rather than placeholder API rows
- files changed:
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_sync_service.py`
  - `TASKS.md`
- short implementation summary: Wired the sync layer’s `opportunity_rebuild` action into the real persisted generation pipeline, so manual rebuilds now populate opportunity tables and leave an auditable job record.
- important decisions:
  - rebuild scope selection currently keys off persisted `market_demand_resolved` rows and matching source `market_price_period` rows
  - the sync job stores the number of generated item rows and the number of target scopes processed in its message metadata
  - no placeholder API data is used in the rebuild flow
- open follow-ups:
  - broaden rebuild orchestration to cover scheduler/background runs
  - improve scope selection and rebuild diagnostics
  - replace zero-default liquidity inputs with real order-derived values

## 2026-03-20

- task id: `T10E`
- title: Persisted Opportunity Generation
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 1, 10, 13, 17.2
- acceptance criteria covered:
  - a backend service now generates `opportunity_items` from precomputed price and demand inputs
  - reruns replace prior rows for the same target/source/type/period scope
  - `opportunity_source_summaries` are aggregated and persisted from generated item rows
  - deterministic tests cover item generation, summary aggregation, and rerun behavior
  - the generation path reads only from precomputed tables, not placeholder API responses
- files changed:
  - `backend/app/services/opportunities/generation.py`
  - `backend/tests/services/test_opportunity_generation.py`
  - `TASKS.md`
- short implementation summary: Added the first real persisted opportunity-generation pipeline, turning computed market price and demand rows into `opportunity_items` and `opportunity_source_summaries`.
- important decisions:
  - reruns delete and replace rows for the same target/source/type/period scope to keep persistence deterministic
  - generation reuses the existing formula helpers and summary aggregator instead of duplicating business logic
  - source liquidity and target supply remain zero-default placeholders until live order ingestion exists
- open follow-ups:
  - wire the generation path into the sync/job layer as a real rebuild step
  - replace zero-default liquidity inputs with real market-order derived values
  - extend the trade API and UI so they rely on rebuilt opportunity tables by default

## 2026-03-20

- task id: `T06A`
- title: Persisted Sync Job History
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 12A, 13, 14, 17.4
- acceptance criteria covered:
  - manual sync execution now persists `sync_job_runs` rows
  - successful synchronous jobs are marked complete with `finished_at` and `duration_ms`
  - sync job history is listed from persisted rows newest first
  - deterministic tests cover job creation and listing for a real manual job path
- files changed:
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_sync_service.py`
  - `TASKS.md`
- short implementation summary: Replaced synthetic sync job history with persisted `sync_job_runs` rows for the implemented manual sync paths, and added service-level coverage for job creation and listing behavior.
- important decisions:
  - the current manual sync paths execute synchronously and are recorded as `success` immediately on completion
  - ordering is newest first by `started_at` and `id` to keep ties deterministic
  - job persistence was added without changing the existing sync status-card placeholders yet
- open follow-ups:
  - record scheduler-driven/background runs through the same persistence path
  - expose real worker health and ESI rate-limit telemetry on `/sync`
  - replace the remaining synthetic sync status and fallback diagnostics

## 2026-03-20

- task id: `T05A`
- title: Trade Repository Reads Computed Opportunity Tables
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 1, 10, 14, 17.2
- acceptance criteria covered:
  - source summaries prefer persisted `opportunity_source_summaries` rows when present
  - item rows prefer persisted `opportunity_items` rows when present
  - safe placeholder fallback remains when computed rows are absent
  - refresh timestamps are derived from computed rows and normalized to UTC-aware values
  - deterministic tests cover computed-read behavior, fallback behavior, and refresh timestamp handling
- files changed:
  - `backend/app/repositories/trade_repository.py`
  - `backend/tests/services/test_trade_repository.py`
  - `TASKS.md`
- short implementation summary: Taught the trade repository to read computed opportunity tables when available without regressing the runnable placeholder flow, and normalized refresh timestamps at the repository boundary.
- important decisions:
  - placeholder fallback remains in place until opportunity generation is complete
  - refresh timestamps are normalized to UTC-aware datetimes so API behavior stays storage-backend independent
  - computed metrics are used now, but item-detail order books remain placeholder-backed for the moment
- open follow-ups:
  - generate real `opportunity_items` and `opportunity_source_summaries` rows
  - replace placeholder order-book detail data
  - implement trade-page filter, sort, and search behavior against computed data

## 2026-03-20

- task id: `T10D`
- title: Persisted Market Demand Resolution
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 3, 8, 10, 13, 17.2
- acceptance criteria covered:
  - `market_demand_resolved` rows are persisted for NPC targets from stored Adam4EVE daily demand
  - short history windows resolve deterministically from the available data
  - stale NPC resolved rows are removed when no raw demand history exists
  - structure targets are explicitly marked as `regional_fallback` until the local structure pipeline exists
  - deterministic tests cover NPC resolution, short-history behavior, stale-row cleanup, and structure fallback behavior
- files changed:
  - `backend/app/services/demand/market_demand.py`
  - `backend/tests/services/test_market_demand.py`
  - `TASKS.md`
- short implementation summary: Added a persisted market-demand resolution service that turns stored Adam4EVE daily demand into query-ready `market_demand_resolved` rows for NPC targets.
- important decisions:
  - NPC demand is averaged across the available requested period instead of requiring a full window
  - missing NPC history deletes stale computed rows for the same key
  - structure targets intentionally resolve to `regional_fallback` with zero demand until the structure-local and CCP fallback pipelines exist
- open follow-ups:
  - replace the temporary structure fallback placeholder with real CCP regional fallback demand
  - wire resolved demand rows into opportunity generation
  - add a scheduled/manual sync path that recomputes demand rows in bulk

## 2026-03-20

- task id: `T10C`
- title: Adam4EVE NPC Demand Ingestion
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 3, 6, 10, 17.2
- acceptance criteria covered:
  - Adam4EVE NPC demand batches persist into `adam_npc_demand_daily`
  - upsert behavior is idempotent on the internal daily NPC demand key
  - persisted rows preserve demand-day values and source metadata
  - `adam4eve_sync` invokes the ingestion path for NPC locations
  - deterministic tests prove mapping, update behavior, and sync-path persistence
- files changed:
  - `backend/app/services/adam4eve/ingestion.py`
  - `backend/app/services/adam4eve/client.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_adam4eve_ingestion.py`
  - `TASKS.md`
- short implementation summary: Added persisted Adam4EVE NPC demand ingestion, wired it through the sync service, and validated the stored rows with deterministic tests.
- important decisions:
  - ingestion resolves external `location_id` and `type_id` values into the repo's internal foreign-key ids before persisting
  - duplicate daily demand rows update the existing record instead of creating a second row
  - the sync entrypoint continues using a mock Adam4EVE client so the pipeline remains runnable before live HTTP integration
- open follow-ups:
  - replace the mock Adam4EVE client with live API-backed fetch logic
  - compute and persist resolved demand rows for NPC and structure targets
  - feed persisted demand into opportunity generation

## 2026-03-20

- task id: `T10B`
- title: Persisted ESI Regional History Ingestion
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 6, 10, 13, 17.2
- acceptance criteria covered:
  - regional history batches persist into `esi_history_daily`
  - upsert behavior is idempotent on the internal unique history key
  - persisted rows contain the pricing fields required by `T10A`
  - `esi_history_sync` invokes the ingestion path for a region batch
  - deterministic tests prove mapping, update behavior, and a round-trip into `market_price_period`
- files changed:
  - `backend/app/services/esi/history_ingestion.py`
  - `backend/app/services/esi/client.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
  - `TASKS.md`
- short implementation summary: Added a persisted regional history ingestion service, wired it through the sync service, and validated that ingested rows feed the existing market price period computation.
- important decisions:
  - ingestion resolves external `region_id` and `type_id` values into the repo's internal foreign-key ids before persisting
  - duplicate history rows update the existing record instead of creating a second row
  - the sync entrypoint uses the mock ESI client for now so the data path is runnable before live CCP HTTP integration lands
- open follow-ups:
  - replace the mock ESI history client with real CCP-backed fetch logic
  - extend the sync/job layer to persist `sync_job_runs`
  - feed ingested history and computed price periods into opportunity generation

## 2026-03-20

- task id: `T10A`
- title: Market Price Period Computation
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 9, 10, 13, 17.2
- acceptance criteria covered:
  - service reads persisted `esi_history_daily` rows and upserts `market_price_period`
  - `risk_pct` uses the shared spec formula
  - `warning_flag` follows threshold behavior
  - empty and insufficient history cases are deterministic
  - deterministic service tests exist and passed
- files changed:
  - `backend/app/services/pricing/market_price_periods.py`
  - `backend/tests/services/test_market_price_periods.py`
- short implementation summary: Added the first real derived-data slice for T10 by computing query-ready market price period rows from stored regional history.
- important decisions:
  - `current_price` is derived from the latest available history average in this slice
  - empty-history recomputation removes an existing stale computed row for the same key
- open follow-ups:
  - wire real Adam4EVE and ESI ingestion into persisted raw tables
  - feed `market_price_period` into opportunity generation

## 2026-03-20

- task id: `T01`
- title: Workflow Adoption Artifacts
- status: `COMPLETED`
- spec refs: baseline audit instructions, `DESIGN_PROMPT.md`
- acceptance criteria covered:
  - `AGENTS.md` created with workflow, role, DoD, and quality gate guidance
  - `TASKS.md` created with reconstructed task packets and conservative statuses
  - `DEVLOG.md` initialized with imported baseline entries
- files changed:
  - `AGENTS.md`
  - `TASKS.md`
  - `DEVLOG.md`
- short implementation summary: Adopted the new Planner/Developer/Tester/Reviewer workflow and established the repository tracking artifacts.
- important decisions:
  - no `DEFECTS.md` created because no confirmed defects were established during the baseline pass
  - no `CLARIFICATIONS.md` created because no ambiguity required adjudication
- open follow-ups:
  - keep future work scoped to one task packet at a time
  - add `DEFECTS.md` only when a defect is confirmed by validation or review

## 2026-03-20

- task id: `T02`
- title: Core Scaffold And Runtime
- status: `IMPORTED_VERIFIED`
- spec refs: `DESIGN_PROMPT.md` sections 14, 15, 17, 19
- acceptance criteria covered:
  - backend app, frontend app, worker, and Docker scaffold exist
  - API routes are mounted
  - database wiring and Alembic scaffolding exist
- files changed:
  - `backend/app/main.py`
  - `backend/app/db/session.py`
  - `frontend/src/app/App.tsx`
  - `frontend/src/routes/AppRoutes.tsx`
  - `docker-compose.yml`
- short implementation summary: Established the modular-monolith scaffold across backend, frontend, worker, and Docker runtime.
- important decisions:
  - APScheduler-based worker used for MVP
  - Docker-first local development retained
- open follow-ups:
  - replace placeholder-backed routes with real computed data paths

- task id: `T03`
- title: Core Trading Formulas
- status: `IMPORTED_VERIFIED`
- spec refs: `DESIGN_PROMPT.md` sections 9, 10, 16.1
- acceptance criteria covered:
  - risk, warning, profit, ROI, DOS, and purchase unit formulas implemented
  - formula unit tests exist and pass
- files changed:
  - `backend/app/domain/rules.py`
  - `backend/tests/domain/test_rules.py`
- short implementation summary: Added explicit formula helpers in the domain layer and covered them with unit tests.
- important decisions:
  - zero/tiny denominator cases return safe defaults instead of raising
- open follow-ups:
  - extend coverage for additional business edge cases as opportunity logic becomes real

- task id: `T04`
- title: Foundation Data Bootstrap
- status: `IMPORTED_PARTIAL`
- spec refs: `DESIGN_PROMPT.md` sections 4, 6, 13, 17.1
- acceptance criteria covered:
  - baseline regions, systems, stations, locations, tracked structures, and default settings are seeded
  - bootstrap path is idempotent
- files changed:
  - `backend/app/services/sync/foundation_data.py`
  - `backend/app/db/session.py`
  - `backend/tests/services/test_foundation_data.py`
- short implementation summary: Added a small persisted seed/bootstrap path to make the app runnable with reference data.
- important decisions:
  - used curated seed data instead of live SDE import for the baseline scaffold
- open follow-ups:
  - implement real SDE import and market group refresh

- task id: `T04A`
- title: Foundation Data Source Abstraction
- status: `DONE`
- spec refs: `TASKS.md` task packet `T04A`
- acceptance criteria covered:
  - foundation bootstrap reads seed data through a provider abstraction
  - default curated source preserves the existing persisted bootstrap shape
  - bootstrap remains idempotent
  - a small mock source proves the abstraction boundary
- files changed:
  - `backend/app/services/sync/foundation_data.py`
  - `backend/app/repositories/seed_data.py`
  - `backend/tests/services/test_foundation_data.py`
- short implementation summary: Swapped the bootstrap over to a seed-source interface and added tests for the default and mock sources.

- task id: `T05`
- title: Trade Analysis API And Data Flow
- status: `IMPORTED_PARTIAL`
- spec refs: `DESIGN_PROMPT.md` sections 1, 2, 10, 14
- acceptance criteria covered:
  - targets, sources, source summaries, items, and item detail endpoints exist
  - trade page consumes the API and renders the hierarchy
- files changed:
  - `backend/app/repositories/trade_repository.py`
  - `backend/app/api/routes/targets.py`
  - `backend/app/api/routes/opportunities.py`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/hooks/useTradeData.ts`
- short implementation summary: Built the trade API surface and UI flow using typed schemas and placeholder-backed opportunity data.
- important decisions:
  - only targets/sources were moved to persisted seed-backed lookup
  - opportunity rows remain demo-backed until ingestion/compute work lands
- open follow-ups:
  - replace demo rows with query-ready computed opportunity tables
  - implement the full control/filter/sort/search behavior

- task id: `T06`
- title: Sync Operations Dashboard
- status: `IMPORTED_PARTIAL`
- spec refs: `DESIGN_PROMPT.md` sections 12A, 14, 17.4
- acceptance criteria covered:
  - sync page renders status cards, manual actions, job history, and fallback diagnostics
  - manual foundation seed action is wired through the sync API
- files changed:
  - `backend/app/services/sync/service.py`
  - `backend/app/api/routes/sync.py`
  - `frontend/src/pages/SyncPage.tsx`
  - `frontend/src/components/sync/`
- short implementation summary: Upgraded `/sync` from a shell to an API-backed dashboard with operational actions and diagnostics.
- important decisions:
  - synthetic status/history retained temporarily for unimplemented jobs
- open follow-ups:
  - persist `sync_job_runs`
  - expose real worker health and ESI rate-limit telemetry

- task id: `T07`
- title: Characters, Auth, And Multi-User Support
- status: `IMPORTED_PARTIAL`
- spec refs: `DESIGN_PROMPT.md` sections 5, 11, 12B, 14
- acceptance criteria covered:
  - auth and character route shapes exist
  - user/character/token/sync-state tables exist in the model layer
- files changed:
  - `backend/app/api/routes/auth.py`
  - `backend/app/api/routes/characters.py`
  - `backend/app/services/characters/service.py`
  - `backend/app/models/all_models.py`
- short implementation summary: Added route and model scaffolding for EVE SSO, characters, accessible structures, and sync state.
- important decisions:
  - auth flow remains mock-friendly until real SSO/token persistence is implemented
- open follow-ups:
  - implement real callback/token exchange/user linking
  - add accessible structure discovery from assets/orders

- task id: `T08`
- title: Frontend Shells And Routing
- status: `IMPORTED_VERIFIED`
- spec refs: `DESIGN_PROMPT.md` sections 1, 12, 15, 19
- acceptance criteria covered:
  - primary routes exist for `/trade`, `/sync`, `/characters`, and `/settings`
  - page shells are styled and test-covered
- files changed:
  - `frontend/src/routes/AppRoutes.tsx`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/pages/SyncPage.tsx`
  - `frontend/src/pages/CharactersPage.tsx`
  - `frontend/src/pages/SettingsPage.tsx`
- short implementation summary: Established the main frontend route structure and base page shells.
- important decisions:
  - custom CSS shell used instead of a component library
- open follow-ups:
  - deepen characters/settings workflows beyond shell rendering

- task id: `T09`
- title: Testing Baseline
- status: `IMPORTED_PARTIAL`
- spec refs: `DESIGN_PROMPT.md` section 16
- acceptance criteria covered:
  - backend tests exist for formulas, selected services, and key API routes
  - frontend shell tests exist and pass
- files changed:
  - `backend/tests/`
  - `frontend/src/pages/TradePage.test.tsx`
  - `frontend/src/pages/SyncPage.test.tsx`
  - `frontend/src/routes/AppRoutes.test.tsx`
- short implementation summary: Added baseline backend and frontend tests and validated them during the audit.
- important decisions:
  - Docker is used as the practical frontend test runner in this environment
- open follow-ups:
  - add ingestion tests, auth/setup tests, and deeper UI behavior tests
  - install/configure `ruff` and `mypy` if they are intended quality gates

- task id: `BUGFIX-TRADE-CONTROLS-2026-03-23`
- title: Trade Page Control Layout And Dropdown Contrast
- status: `PASS`
- spec refs: user-reported trade page UI defect
- acceptance criteria covered:
  - target market and analysis period controls no longer collapse into overlapping columns on the trade page
  - dropdown option text uses a darker, readable color for unselected entries
- files changed:
  - `frontend/src/components/trade/TradeControls.tsx`
  - `frontend/src/styles/global.css`
- short implementation summary: Scoped a wider responsive grid to the trade controls and set explicit option colors for the select menu.
- important decisions:
  - kept the layout change trade-page-specific to avoid widening controls globally on settings and other panels
- validation:
  - `npm.cmd test -- --run TradePage`
  - `npm.cmd run build`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`

- task id: `BUGFIX-STRUCTURE-SYNC-2026-03-23`
- title: Character-Tracked Structures Feed Snapshot Sync
- status: `PASS`
- spec refs: user-reported structure snapshot sync defect
- acceptance criteria covered:
  - enabling or rediscovering a tracked character structure creates or updates the backend rows used by snapshot sync
  - structure snapshot sync processes character-tracked structures instead of reporting zero work
- files changed:
  - `backend/app/services/characters/service.py`
  - `backend/tests/services/test_character_service.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Mirrored tracked character structures into `locations` and `tracked_structures`, then added regression tests proving snapshot sync sees those rows.
- important decisions:
  - kept the fix in `CharacterService` so the sync job can continue reading a single authoritative tracked-structure table
  - silently skips mirroring when a discovered structure cannot be matched to a known system/region
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`

- task id: `BUGFIX-TRADE-DERIVATION-2026-03-23`
- title: Remove Demo Trade Rows And Rebuild Derived Opportunities From Syncs
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 1, 6, 10, 18
- acceptance criteria covered:
  - trade endpoints no longer fabricate placeholder source/item rows when derived tables are empty
  - item detail no longer invents demo order-book rows
  - raw sync jobs refresh derived price/demand rows and rebuild opportunities so trade results recalculate from synced data
- files changed:
  - `backend/app/repositories/trade_repository.py`
  - `backend/app/api/routes/opportunities.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/api/test_endpoints.py`
  - `backend/tests/services/test_adam4eve_ingestion.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
  - `backend/tests/services/test_sync_service.py`
  - `backend/tests/services/test_trade_repository.py`
- short implementation summary: Removed fallback/demo trade responses, made sync jobs refresh derived market tables plus opportunities, and added regression tests for the raw-sync-to-trade pipeline.
- important decisions:
  - trade endpoints now return empty results instead of masking missing derivations with fake data
  - item detail returns real computed metrics with empty order sections until real order-book ingestion is implemented
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`

- task id: `T12A-2026-03-26`
- title: Bulk Market Price Rebuild And Persistent Bulk Import Cache
- status: `PARTIAL`
- spec refs: `TASKS.md` `T12A`, user follow-up on persistent bulk import progress and local file reuse
- acceptance criteria covered:
  - market price stats for `3/7/14/30` day periods are now computed from one regional history read and written in bulk
  - sync state now records generic bulk import progress by scope instead of only relying on source-specific tables
  - dated Adam/ESI-style bulk files are cached locally and reused on reruns instead of being downloaded again
- files changed:
  - `backend/app/core/config.py`
  - `backend/app/models/all_models.py`
  - `backend/app/services/adam4eve/client.py`
  - `backend/app/services/pricing/market_price_periods.py`
  - `backend/app/services/sync/bulk_imports.py`
  - `backend/app/services/sync/service.py`
  - `backend/alembic/versions/20260326_0006_bulk_import_tracking.py`
  - `backend/tests/services/test_bulk_imports.py`
  - `backend/tests/services/test_market_price_periods.py`
  - `backend/tests/services/test_sync_service.py`
  - `backend/tests/services/test_adam4eve_ingestion.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
  - `TASKS.md`
- short implementation summary: Added a shared bulk-import cursor/file cache layer for dated Adam/ESI exports and replaced the market-price rebuild path with a multi-period regional bulk write that populates `3/7/14/30` day rows in one pass.
- important decisions:
  - kept the existing source-specific sync-state tables for compatibility while mirroring progress into the new generic bulk-import cursor table
  - limited the forever-cache behavior to dated export files; the CCP foundation `latest` zip was left uncached because its URL is not versioned
- validation:
  - `C:\Users\ASUS\AppData\Local\Python\bin\python.exe -m compileall backend\app`
  - in-memory SQLite smoke script covering `BulkImportService`, generic cursor progression, multi-period market price rebuild, and the Adam export completion gate
  - `C:\Users\ASUS\AppData\Local\Python\bin\python.exe -m pytest ...` attempted but blocked during import because local application-control policy blocks `psycopg-binary` and the pure-Python fallback cannot find `libpq`

- task id: `ADAM4EVE-DEMAND-INCREMENTAL-2026-03-25`
- title: Skip Adam4EVE Demand Downloads For Already-Synced Region Weeks
- status: `PASS`
- spec refs: user-requested incremental Adam4EVE workflow
- acceptance criteria covered:
  - Adam4EVE demand ingest is append-only and no longer probes or rewrites existing `(location, item, date)` rows
  - sync state tracks Adam4EVE NPC demand coverage per region
  - `adam4eve_sync` resolves the latest Adam4EVE export metadata first and skips regions already synced for that export week without downloading the weekly CSV
  - existing persisted demand history can bootstrap the new skip logic from max stored region date
  - tests cover export metadata resolution, append-only demand ingest, sync-state persistence, and no-download skip behavior
- files changed:
  - `backend/alembic/versions/20260325_0005_adam_npc_demand_sync_state.py`
  - `backend/app/models/all_models.py`
  - `backend/app/services/adam4eve/client.py`
  - `backend/app/services/adam4eve/ingestion.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_adam4eve_client.py`
  - `backend/tests/services/test_adam4eve_ingestion.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Added per-region Adam4EVE demand sync state keyed to the latest weekly export, switched demand ingest to append-only writes, and taught `adam4eve_sync` to skip already-synced regions before fetching the weekly demand dump.
- important decisions:
  - the pre-download skip check uses Adam4EVE weekly export metadata from the index pages, not the CSV body itself
  - regions with historical demand rows but no explicit sync-state row bootstrap into the new skip path from their max persisted demand date
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`

- task id: `ESI-HISTORY-ORDER-SCOPE-2026-03-25`
- title: Restrict ESI History Pull To Active Regional Orders
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 5, 6
- acceptance criteria covered:
  - ESI history sync only requests items that currently have active market orders in the region
  - demand-only items do not expand the history download scope
  - raw trade sync coverage stays aligned with the new order-backed history rule
- files changed:
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Locked the history-sync scope to active regional orders with a regression test that proves demand rows alone do not trigger ESI history fetches.
- important decisions:
  - kept the narrowed `_history_sync_items()` behavior already present in the working tree and added coverage rather than broadening the sync back out
  - updated the raw trade sync test seed to include a real active order so it still exercises the intended order-backed path
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests/services/test_sync_service.py backend/tests/services/test_esi_history_ingestion.py`

- task id: `ESI-HISTORY-APPEND-ONLY-2026-03-25`
- title: Make ESI History Ingest Trust Region Sync Watermark
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 5, 6
- acceptance criteria covered:
  - ESI history ingest no longer performs per-row database existence checks before writing
  - region sync watermark remains the mechanism that limits downloaded history to unseen dates
  - ingestion tests cover append-only history rows instead of row-level idempotent skipping
- files changed:
  - `backend/app/services/esi/history_ingestion.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
- short implementation summary: Removed the large tuple-key existence probe from ESI history ingestion and switched the service to append incoming delta rows directly, relying on per-region sync state to avoid re-downloading already synced dates.
- important decisions:
  - preserved the append-only contract in both the Postgres COPY path and the ORM fallback
  - updated coverage to validate new-date appends rather than duplicate-row skipping
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests/services/test_esi_history_ingestion.py backend/tests/services/test_sync_service.py`

- task id: `ADAM4EVE-REGIONAL-HISTORY-2026-03-25`
- title: Replace ESI History Source With Adam4EVE Regional Price Dumps
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 5, 6
- acceptance criteria covered:
  - historical price rows are sourced from Adam4EVE regional price dumps instead of CCP ESI market history
  - `adam4eve_sync` imports both NPC demand and regional historical sell-price data before derived rebuilds
  - region sync watermark limits Adam4EVE history downloads to unseen dates and can bootstrap from existing persisted history
- files changed:
  - `backend/app/services/adam4eve/client.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_adam4eve_client.py`
  - `backend/tests/services/test_adam4eve_ingestion.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Added Adam4EVE per-region daily price-history fetching from the static dump, mapped sell-side regional prices into the existing daily history table, merged that import into `adam4eve_sync`, and pointed the legacy `esi_history_sync` job at the same Adam4EVE-backed regional-history flow.
- important decisions:
  - mapped `sell_price_avg/high/low` into the existing `esi_history_daily` average/highest/lowest fields because downstream pricing compares against target sell pricing
  - preserved the legacy history job as a compatibility alias while moving the actual source off ESI
  - seeded the history watermark from already persisted daily rows when no explicit sync-state row exists to avoid full-region re-downloads
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`

- task id: `REMOVE-ESI-HISTORY-JOB-2026-03-25`
- title: Remove Legacy ESI History Sync Job Surface
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 5, 6
- acceptance criteria covered:
  - legacy `esi_history_sync` job is no longer exposed in backend sync execution paths or status cards
  - frontend manual sync actions no longer offer a separate ESI history button
  - dead ESI market-history client code and compatibility-only tests are removed
- files changed:
  - `backend/app/domain/enums.py`
  - `backend/app/services/esi/client.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_esi_client.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
  - `backend/tests/services/test_sync_service.py`
  - `frontend/src/components/sync/ManualSyncActions.tsx`
- short implementation summary: Removed the obsolete `esi_history_sync` job and all remaining code paths that implied CCP ESI was still a historical-price source, leaving Adam4EVE as the only historical-price import flow.
- important decisions:
  - kept the existing `esi_history_daily` storage table and sync-state table names for now because they are internal storage details still used by the Adam4EVE-backed history pipeline
  - removed only the legacy job surface and dead ESI client history fetch logic, not the reusable ingestion/storage layer
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `npm.cmd test -- --run`
  - `npm.cmd run build`

- task id: `TRADE-SINGLE-PERIOD-2026-03-25`
- title: Collapse Fixed Multi-Period Price Snapshots To One Selected Period
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 2, 9, 10, 12C
- acceptance criteria covered:
  - trade analysis period is now a numeric up/down input with a default of 14 days
  - sync jobs compute demand and price-period derivatives only for the configured single analysis period instead of fixed `3/7/14/30` snapshots
  - trade reads can prepare the requested period on demand so changing the selected number still yields data
  - design prompt no longer requires fixed supported snapshot periods
- files changed:
  - `DESIGN_PROMPT.md`
  - `backend/app/repositories/trade_repository.py`
  - `backend/app/services/settings_service.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_adam4eve_ingestion.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
  - `backend/tests/services/test_sync_service.py`
  - `backend/tests/services/test_trade_repository.py`
  - `frontend/src/components/trade/TradeControls.tsx`
  - `frontend/src/pages/SettingsPage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
- short implementation summary: Replaced the hardcoded multi-period snapshot loop with a single selected analysis period, computed during sync for the configured default and prepared on demand for trade page requests.
- important decisions:
  - kept the selected period as a numeric input so the UI is no longer limited to a fixed enum
  - avoided deleting or recomputing already-present derived rows during trade reads unless the requested period rows were missing
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `npm.cmd test -- --run`
  - `npm.cmd run build`

- task id: `TRADE-RISK-REMOVAL-2026-03-25`
- title: Remove Calculated Risk And Warning Outputs
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 2, 5, 9, 10, 12C, 13, 16
- acceptance criteria covered:
  - calculated risk and warning fields are removed from backend models, schemas, repositories, and generation logic
  - trade/settings frontend no longer exposes risk or warning controls or fields
  - database migration removes obsolete risk/warning columns from derived tables
  - design prompt no longer specifies calculated risk or warning behavior
- files changed:
  - `DESIGN_PROMPT.md`
  - `backend/alembic/versions/20260325_0004_remove_risk_fields.py`
  - `backend/app/api/schemas/settings.py`
  - `backend/app/api/schemas/trade.py`
  - `backend/app/domain/constants.py`
  - `backend/app/domain/rules.py`
  - `backend/app/models/all_models.py`
  - `backend/app/repositories/seed_data.py`
  - `backend/app/repositories/trade_repository.py`
  - `backend/app/services/opportunities/aggregator.py`
  - `backend/app/services/opportunities/generation.py`
  - `backend/app/services/pricing/market_price_periods.py`
  - `backend/app/services/settings_service.py`
  - `backend/tests/api/test_endpoints.py`
  - `backend/tests/domain/test_rules.py`
  - `backend/tests/fixtures/foundation_snapshot.json`
  - `backend/tests/services/test_aggregator.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
  - `backend/tests/services/test_foundation_data.py`
  - `backend/tests/services/test_market_price_periods.py`
  - `backend/tests/services/test_opportunity_generation.py`
  - `backend/tests/services/test_sync_service.py`
  - `backend/tests/services/test_trade_repository.py`
  - `frontend/src/api/settings.ts`
  - `frontend/src/api/trade.ts`
  - `frontend/src/components/trade/ItemDetailPanel.tsx`
  - `frontend/src/components/trade/TradeControls.tsx`
  - `frontend/src/pages/SettingsPage.test.tsx`
  - `frontend/src/pages/SettingsPage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/types/trade.ts`
- short implementation summary: Removed the risk and warning concept from the trade flow entirely, including derived persistence, APIs, UI controls, tests, and the written product spec, while keeping a small legacy settings cleanup for older saved JSON.
- important decisions:
  - retained legacy stripping of `warning_threshold_pct` and `warning_enabled` in settings loading so old persisted settings remain readable
  - treated the risk fields as derived-only state and removed them from the database via a forward migration
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `npm.cmd test -- --run`
  - `npm.cmd run build`

- task id: `ESI-COPY-RAW-2026-03-24`
- title: Bulk Load Raw ESI Imports With PostgreSQL COPY
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 5, 6, 12A
- acceptance criteria covered:
  - raw ESI history rows are bulk loaded directly into `esi_history_daily` without extra staging tables
  - raw Adam4EVE NPC demand rows are bulk loaded directly into `adam_npc_demand_daily` without extra staging tables
  - raw ESI regional order snapshots are bulk loaded directly into `esi_market_orders` without extra staging tables
  - existing sync counters and order snapshot semantics remain covered by tests
- files changed:
  - `backend/app/services/postgres_copy.py`
  - `backend/app/services/esi/history_ingestion.py`
  - `backend/app/services/adam4eve/ingestion.py`
  - `backend/app/services/esi/orders_ingestion.py`
  - `backend/main.py`
  - `backend/tests/services/test_esi_orders_ingestion.py`
- short implementation summary: Replaced row-by-row ORM inserts in the three raw ingestion services with PostgreSQL `COPY` into the destination raw tables, while preserving created/updated/deleted reporting and NPC-station resolution behavior.
- important decisions:
  - kept the existing ORM path as a fallback for non-Postgres dialects
  - history and Adam demand continue to replace incoming unique rows rather than deleting broader slices
  - regional orders keep full-region snapshot semantics by deleting the prior region snapshot before copying the refreshed rows
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend -q`

- task id: `ESI-HISTORY-INCREMENTAL-2026-03-25`
- title: Incremental ESI History Raw Sync
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 5, 6, 12A
- acceptance criteria covered:
  - raw `esi_history_daily` ingestion no longer rewrites immutable historical rows that are already present
  - ESI history sync tracks a per-region watermark and last-check timestamp in persisted state
  - same-day reruns skip regions already checked today instead of redownloading the full history payload again
  - client-side history filtering only passes through rows newer than the region watermark
- files changed:
  - `backend/app/models/all_models.py`
  - `backend/alembic/versions/20260325_0003_esi_history_sync_state.py`
  - `backend/app/services/esi/client.py`
  - `backend/app/services/esi/history_ingestion.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_esi_client.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Added `esi_history_sync_state` as a per-region high-water mark, switched history ingestion to append only missing days, and taught `esi_history_sync` to skip regions already checked on the current UTC day while requesting only rows newer than the stored watermark.
- important decisions:
  - CCP's `/markets/{region_id}/history/` endpoint has no server-side `since` parameter, so true delta download by date is not possible; the implementation avoids repeat same-day calls and filters the returned payload client-side for new rows only
  - immutable historical rows are treated as append-only, so existing `esi_history_daily` rows are preserved and no longer counted as updates
  - the Alembic migration is defensive because the test harness can materialize metadata before startup migrations run
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend -q`

- task id: `PG-TEST-001`
- title: Postgres Test Harness Migration
- status: `PASS`
- spec refs: `AGENTS.md`, `DESIGN_PROMPT.md` section 17 phase 1 PostgreSQL schema/testing requirements
- acceptance criteria covered:
  - backend tests run against a dedicated PostgreSQL test database instead of SQLite
  - harness resets preserve per-test isolation without dropping the database under active connections
  - API tests avoid repeated app lifespan startup cost while still restoring baseline foundation data per test
  - Postgres test setup failures still surface clear actionable startup guidance
- files changed:
  - `backend/tests/conftest.py`
  - `backend/tests/db_test_utils.py`
- short implementation summary: Migrated the backend test harness fully to Postgres, replaced destructive database recreation with cheaper schema/table resets, reused test infrastructure safely, and cut repeated API client startup cost so the full backend suite now completes quickly on Postgres.
- important decisions:
  - kept the fix strictly inside the test harness so application runtime behavior did not change
  - used reviewer adjudication to keep unrelated failing tests out of scope for this packet
- validation:
  - full backend `pytest` now completes quickly on Postgres during harness validation
  - remaining failing tests were adjudicated as separate defects outside `PG-TEST-001`

- task id: `PG-RUNTIME-002`
- title: Remove SQLite Runtime Branches
- status: `PASS`
- spec refs: `AGENTS.md`, `DESIGN_PROMPT.md` PostgreSQL runtime requirements
- acceptance criteria covered:
  - runtime database setup no longer carries active SQLite-specific branches
  - sync and database diagnostics runtime paths no longer include SQLite lock-tolerance behavior
  - Postgres-only runtime behavior is reflected in the owned sync-service tests
- files changed:
  - `backend/app/db/session.py`
  - `backend/app/services/sync/service.py`
  - `backend/app/api/routes/database.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Removed SQLite-specific engine/session setup and deleted the runtime lock-tolerance fallbacks that previously swallowed SQLite lock errors, leaving the touched runtime paths Postgres-only.
- important decisions:
  - kept the packet scoped to runtime code and its directly affected tests only
  - let database failures surface normally in the touched Postgres runtime paths instead of masking them with SQLite-era retry/default behavior
- validation:
  - targeted runtime/test updates completed for the owned files
  - remaining suite failures were adjudicated as separate Postgres-backed defects outside `PG-RUNTIME-002`

- task id: `PG-MIGRATION-003`
- title: Alembic-Only Postgres Schema Bootstrap
- status: `PASS`
- spec refs: `AGENTS.md`, `DESIGN_PROMPT.md` PostgreSQL schema and Alembic migration requirements
- acceptance criteria covered:
  - a blank Postgres database reaches application startup through Alembic migrations
  - schema creation is owned by Alembic revisions
  - startup no longer mutates schema outside the Alembic path
  - initial schema boots to a healthy initialized state on a new database
- files changed:
  - no code changes required for this packet
- short implementation summary: Verified that the current startup path runs Alembic migrations first, then seeds foundation data, which proves a blank Postgres database can boot through migrations alone and reach a healthy initialized state.
- important decisions:
  - kept the packet as a verification-only pass because the current code already satisfied the migration/bootstrap acceptance criteria
  - left unrelated Postgres-backed test failures out of scope once they were adjudicated separately
- validation:
  - inspected the runtime migration entry point and Alembic environment/revisions for schema ownership
  - remaining suite failures were separate Postgres-backed defects outside `PG-MIGRATION-003`

- task id: `PG-CLEANUP-004`
- title: Remove SQLite Artifacts From Active Repo Surface
- status: `PASS`
- spec refs: `AGENTS.md`, `DESIGN_PROMPT.md` PostgreSQL database requirement
- acceptance criteria covered:
  - tracked SQLite artifact files `test.db` and `backend/test.db` were removed from the repo
  - ignore rules now prevent regenerated local SQLite database artifacts from being re-added
  - active runtime and test guidance remains Postgres-only
- files changed:
  - `.gitignore`
  - `test.db`
  - `backend/test.db`
- short implementation summary: Removed the tracked SQLite database artifacts from the active repo surface and added ignore rules to keep local SQLite `.db` files from being committed again, while leaving the supported runtime and test guidance Postgres-only.
- important decisions:
  - kept the cleanup packet tightly scoped to repo-surface artifacts and ignore rules
  - left unrelated local database files and unrelated dirty worktree changes untouched
- validation:
  - tester PASSed the packet-specific cleanup acceptance criteria
  - unrelated backend `pytest` failures remain outside `PG-CLEANUP-004` scope

- task id: `POSTGRES-DEFAULT-ALEMBIC-BOOT-2026-03-23`
- title: Restore Postgres Default Runtime And Alembic-Driven Startup
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` tech stack and architecture sections
- acceptance criteria covered:
  - backend runtime defaults to local PostgreSQL instead of SQLite when `DATABASE_URL` is not explicitly set
  - app startup runs Alembic migrations rather than `create_all()` plus runtime schema patching
  - sync job progress columns exist as a real Alembic migration for existing databases
  - backend docs now reflect the Postgres default runtime URL
- files changed:
  - `backend/alembic/versions/20260323_0002_sync_job_progress_columns.py`
  - `backend/app/core/config.py`
  - `backend/app/db/session.py`
  - `README.md`
- short implementation summary: Switched the default runtime database URL back to local PostgreSQL, replaced startup schema mutation with Alembic `upgrade head`, and moved the sync progress columns into an idempotent migration so already-patched local databases still upgrade cleanly.
- important decisions:
  - kept SQLite-specific connection pragmas for the test and explicit-SQLite path, but stopped making SQLite the default production/dev runtime
  - used Alembic’s Python API during startup so the backend and Docker flows share the same migration path
  - made the progress-column migration idempotent to tolerate older local/test SQLite databases that had already received those columns from the previous runtime patch logic
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\\.venv\\Scripts\\python.exe' -m mypy backend`
  - `& '.\backend\\.venv\\Scripts\\python.exe' -m ruff check backend --fix`
  - `npm.cmd test -- --run SyncPage`
  - `npm.cmd test -- --run DatabasePage AppRoutes`
  - `npm.cmd run build`

- task id: `SQLITE-DIAGNOSTICS-STABILITY-2026-03-23`
- title: Stabilize Sync History And Database Diagnostics Under SQLite Load
- status: `PASS`
- spec refs: user-requested sync diagnostics usability
- acceptance criteria covered:
  - sync dashboard no longer drops job history immediately after a run because of transient SQLite lock windows
  - database table inspection keeps prior data during refetches and shows a readable busy-state error instead of looking blank
  - backend SQLite sessions use a longer busy timeout and WAL mode to reduce local lock contention during sync jobs
  - backend and frontend tests cover the updated lock-tolerant behavior and diagnostics rendering
- files changed:
  - `backend/app/api/routes/database.py`
  - `backend/app/db/session.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/api/test_endpoints.py`
  - `frontend/src/hooks/useDatabaseData.ts`
  - `frontend/src/hooks/useSyncData.ts`
  - `frontend/src/pages/DatabasePage.test.tsx`
  - `frontend/src/pages/DatabasePage.tsx`
- short implementation summary: Reduced SQLite lock churn with better engine pragmas, retried read-heavy diagnostics endpoints longer before declaring the database busy, preserved prior React Query data during refetches, and made the Database page render explicit busy-state errors.
- important decisions:
  - kept SQLite lock handling non-fatal for diagnostics reads, but stopped silently replacing visible data with empty results during brief refetch lock windows
  - retained `PRAGMA foreign_keys = ON` and fixed the affected API tests to clean up character-linked rows correctly instead of loosening integrity checks
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `npm.cmd test -- --run DatabasePage`
  - `npm.cmd run build`

- task id: `SYNC-PROGRESS-BARS-2026-03-23`
- title: Add Running Job Progress Bars To Sync Dashboard
- status: `PASS`
- spec refs: user-requested sync diagnostics usability
- acceptance criteria covered:
  - running sync jobs expose progress fields through the backend API and sync status cards
  - long-running ESI history and market-order jobs report a download phase and then a processed `x / total` view over downloaded records
  - sync dashboard renders visible progress bars for running jobs and refreshes often enough to observe progress
  - existing local databases gain the new sync progress columns automatically on startup without requiring a manual reset
- files changed:
  - `backend/app/api/schemas/sync.py`
  - `backend/app/db/session.py`
  - `backend/app/models/all_models.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/api/test_endpoints.py`
  - `backend/tests/services/test_sync_service.py`
  - `frontend/src/components/sync/JobHistoryTable.tsx`
  - `frontend/src/components/sync/StatusCards.tsx`
  - `frontend/src/hooks/useSyncData.ts`
  - `frontend/src/pages/SyncPage.test.tsx`
  - `frontend/src/styles/global.css`
  - `frontend/src/types/sync.ts`
- short implementation summary: Added generic sync-job progress fields, updated the ESI jobs to checkpoint download and processing progress into `sync_job_runs`, surfaced that state through the API, and rendered live progress bars on the dashboard cards and job history table.
- important decisions:
  - ESI jobs now show region-based progress while downloading and switch to downloaded-record progress once all remote data is in memory
  - startup performs a lightweight runtime schema patch for the new `sync_job_runs` columns so current local databases start reporting progress without a manual migration step
  - sync dashboard polling was shortened from 60 seconds to 5 seconds so visible progress updates are timely
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `npm.cmd test -- --run SyncPage`
  - `npm.cmd run build`

- task id: `NPC-ORDER-LOCATION-SKIP-2026-03-23`
- title: Skip Structure Location IDs During NPC Order Sync
- status: `PASS`
- spec refs: user-reported ingestion bug
- acceptance criteria covered:
  - NPC order sync no longer calls the station endpoint for structure-style location IDs from regional order snapshots
  - non-NPC order locations are skipped cleanly instead of failing the whole sync job
  - sync job messaging reports how many orders were skipped because the location was not an NPC station
- files changed:
  - `backend/app/services/esi/orders_ingestion.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Added a non-NPC location skip path to regional order ingestion, including a structure-ID guard and graceful handling for 400/404 station lookups, then surfaced the skip count in the sync job summary.
- important decisions:
  - orders with structure-style location IDs still count as downloaded records for progress, but they are excluded from persisted NPC order rows
  - existing non-station `locations` rows are also ignored if an order references them during NPC order sync
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`

- task id: `ORDER-INGESTION-SCOPE-2026-03-23`
- title: Remove Item Fallback Fetches And Expand ESI Scope
- status: `PASS`
- spec refs: user-requested ingestion corrections
- acceptance criteria covered:
  - `Sync NPC Orders` no longer fetches missing item types one by one during order ingestion
  - missing order `type_id` values are skipped instead of hydrated, so order sync depends on foundation data being present
  - CCP SDE foundation import excludes blueprint-category items entirely
  - ESI market orders and ESI history syncs operate across all imported regions instead of only the curated subset
- files changed:
  - `backend/app/services/esi/orders_ingestion.py`
  - `backend/app/services/sync/foundation_import.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_foundation_import.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Removed the per-type order-ingestion fallback, filtered blueprint types out of the bulk SDE import, and changed the ESI region selection logic from curated target regions to the full imported region set.
- important decisions:
  - order sync now treats missing items as a foundation-data gap and skips those orders rather than hiding the problem by downloading metadata ad hoc
  - skipped orders still count as downloaded records for sync progress, while the final message calls out how many were skipped because foundation data was missing
  - history sync now derives its item scope from all order-backed items across imported regions, with NPC-station demand rows as fallback context
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `npm.cmd test -- --run SyncPage`
  - `npm.cmd run build`

- task id: `SYNC-DASHBOARD-LOCK-TOLERANCE-2026-03-23`
- title: Make Sync Status And Job Reads Tolerant Of SQLite Locks
- status: `PASS`
- spec refs: user-requested sync diagnostics stability
- acceptance criteria covered:
  - `/api/sync/status` no longer returns `500` just because SQLite is temporarily locked during a live sync
  - `/api/sync/jobs` similarly degrades instead of crashing under transient SQLite lock pressure
  - backend tests cover locked status reads and locked job-history reads directly
- files changed:
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Wrapped sync status and job-history loading in best-effort SQLite lock tolerance so dashboard polling stays responsive while heavy sync jobs are writing.
- important decisions:
  - returned idle/default status cards when status reads are locked, and an empty list when job-history reads are locked
  - kept lock tolerance limited to transient SQLite lock errors so unexpected database failures still surface
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`

- task id: `STALE-CLEANUP-LOCK-TOLERANCE-2026-03-23`
- title: Ignore SQLite Locks During Stale Cancellation Cleanup
- status: `PASS`
- spec refs: user-requested sync operability and diagnostics
- acceptance criteria covered:
  - stale-cancellation reconciliation no longer crashes requests when the `sync_job_runs` lookup hits a transient SQLite lock
  - sync status, sync job history, and sync triggers continue normally when stale-job cleanup cannot read due to a temporary lock
  - backend tests cover the locked stale-cleanup query path directly
- files changed:
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Made stale `cancelling` job cleanup opportunistic by skipping reconciliation when SQLite is temporarily locked instead of treating that status query as fatal.
- important decisions:
  - kept stale cleanup best-effort only, because abandoned-row cleanup is lower priority than keeping the sync APIs responsive
  - limited the tolerance to transient SQLite lock errors so unexpected database errors still surface
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`

- task id: `STALE-CANCELLING-JOBS-2026-03-23`
- title: Auto-Finalize Abandoned Cancelling Sync Jobs
- status: `PASS`
- spec refs: user-requested sync operability and diagnostics
- acceptance criteria covered:
  - stale sync jobs stuck in `cancelling` are automatically finalized as `cancelled`
  - stale-cancellation cleanup runs before sync status and job-history reads, so abandoned rows stop lingering in the dashboard
  - long-running `running` jobs are not auto-finalized by this cleanup path
  - backend tests cover stale `cancelling` reconciliation directly
- files changed:
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Added a stale-cancellation reconciler that finalizes abandoned `cancelling` sync jobs before status and job-history reads so dead rows don’t persist forever.
- important decisions:
  - limited automatic cleanup to `cancelling` rows only, leaving legitimately long `running` imports untouched
  - used a short grace period before reconciliation so active cooperative cancellations still have time to finish normally
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`

- task id: `FALLBACK-STATUS-LOCK-TOLERANCE-2026-03-23`
- title: Tolerate SQLite Locks In Fallback Diagnostics Reads
- status: `PASS`
- spec refs: user-requested sync diagnostics stability
- acceptance criteria covered:
  - `/api/sync/fallback-status` no longer returns `500` just because SQLite is briefly locked during a long-running sync
  - fallback diagnostics degrade to an empty list when the locked read cannot be retried successfully
  - backend tests cover the locked-read fallback path directly
- files changed:
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Wrapped the fallback-diagnostics read path in transient SQLite lock tolerance so dashboard polling does not crash while another sync job is writing.
- important decisions:
  - limited the lock tolerance to read-only diagnostics loading and returned an empty list on repeated locked reads instead of surfacing a 500
  - kept non-lock operational errors surfacing normally so genuine bugs are still visible
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`

- task id: `SQLITE-LOCK-TOLERANCE-2026-03-23`
- title: Ignore Transient SQLite Locks In Cancellation Probe
- status: `PASS`
- spec refs: user-requested sync operability and diagnostics
- acceptance criteria covered:
  - long-running sync jobs no longer fail just because the cancellation status probe hits a transient SQLite `database is locked` error
  - cancellation checks continue to honor actual `cancelling` and `cancelled` states when the status row is readable
  - backend tests cover the locked-probe case directly
- files changed:
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Made the sync cancellation probe tolerant of transient SQLite lock errors by treating a locked status read as a retry-later condition instead of aborting the whole job.
- important decisions:
  - limited the tolerance to the status-probe read path only, so real database errors still surface normally
  - kept the existing cancellation flow intact; this change only prevents a locked probe from crashing active sync work
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`

- task id: `CCP-SDE-URL-FIX-2026-03-23`
- title: Use CCP Official Latest JSONL Archive URL
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 5, 12A
- acceptance criteria covered:
  - foundation import no longer requests the unsupported `enhanced-jsonl` archive URL that returned `403 Forbidden`
  - importer uses CCP’s documented latest JSONL shorthand archive URL directly
  - backend tests cover successful plain JSONL loading and surfaced download failures from the latest archive URL
- files changed:
  - `backend/app/core/config.py`
  - `backend/app/services/sync/foundation_import.py`
  - `backend/tests/services/test_foundation_import.py`
- short implementation summary: Removed the unsupported enhanced-archive fetch path and switched the importer to CCP’s official `eve-online-static-data-latest-jsonl.zip` endpoint, which is the publicly documented bulk JSONL source.
- important decisions:
  - preferred the official latest shorthand URL over build-numbered enhanced archive guessing to avoid archive-availability races and access errors
  - kept station-name fallback behavior for plain JSONL imports where NPC station names are not present in the archive payload
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`

- task id: `SYNC-FAILURE-VISIBILITY-2026-03-23`
- title: Surface Immediate Sync Button Failures In UI And Tests
- status: `PASS`
- spec refs: user-requested diagnostics and sync operability
- acceptance criteria covered:
  - the Sync page shows an immediate visible error when a manual sync button returns a failed job payload
  - frontend tests fail if a button-triggered sync job returns `status="failed"` and the page hides the failure
  - backend API tests cover failed sync-run responses carrying `error_details`
  - existing sync cancellation coverage remains green after the new failure-visibility checks
- files changed:
  - `backend/tests/api/test_endpoints.py`
  - `backend/tests/services/test_sync_service.py`
  - `frontend/src/pages/SyncPage.tsx`
  - `frontend/src/pages/SyncPage.test.tsx`
  - `frontend/src/styles/global.css`
- short implementation summary: Added a visible error alert for immediately failed sync jobs, then extended the API and page tests to require that failure state to be exposed instead of being silently buried in job history.
- important decisions:
  - kept the sync-run API returning the failed job payload as `200 OK`, but made the frontend treat `status="failed"` as an immediate alert condition
  - strengthened the long-running cancellation test fixture so the broader backend suite stays reliable while covering the new sync-failure cases
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `npm.cmd test -- --run SyncPage`
  - `npm.cmd run build`

- task id: `CCP-SDE-IMPORT-2026-03-23`
- title: Replace Fuzzwork Foundation Import With CCP JSONL SDE
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 5, 12A
- acceptance criteria covered:
  - foundation import now uses CCP’s official static-data feed instead of the Fuzzwork SQLite mirror
  - importer loads regions, systems, stations, and marketable item types from the bulk JSONL archive
  - importer prefers the enhanced JSONL archive for station names and falls back to the plain JSONL archive if needed
  - backend tests cover build metadata parsing, JSONL archive loading, and fallback behavior
- files changed:
  - `backend/app/core/config.py`
  - `backend/app/services/sync/foundation_import.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_foundation_import.py`
- short implementation summary: Replaced the Fuzzwork-based foundation importer with a CCP SDE JSONL importer that discovers the latest build, downloads the official bulk archive, and loads the app’s foundation tables from JSONL records.
- important decisions:
  - preferred the enhanced JSONL variant so station names remain available in bulk imports
  - kept the plain JSONL archive as a fallback path so foundation import still works if the enhanced build asset is unavailable
  - added a small SQLite-lock retry around sync cancellation commits to keep the existing cancellation flow stable under the updated test matrix
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`

- task id: `ESI-ORDERS-SCOPE-2026-03-23`
- title: Bound ESI Market Orders Sync To Curated Target Regions
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 5, 6, 12A
- acceptance criteria covered:
  - `Sync NPC Orders Now` no longer attempts to crawl every imported region after full SDE foundation import
  - orders sync is limited to the curated target-market regions used by the app
  - stale order cleanup still works within the scoped region set
  - backend tests cover scoped region fetching and scoped stale-order deletion
- files changed:
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Restricted the NPC market-order job to the curated target-market regions instead of every imported region, and added regression coverage for both region scoping and scoped rerun cleanup.
- important decisions:
  - kept the orders job aligned with the current app trading surface rather than the full imported universe
  - reused the same curated-region scope as the fixed history job so the manual sync buttons operate over the same market footprint
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`

- task id: `ESI-HISTORY-SCOPE-2026-03-23`
- title: Bound ESI History Sync To Real Market Scope
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 5, 6, 12A
- acceptance criteria covered:
  - `Sync ESI History Now` no longer fails when the full SDE item catalog includes types with no regional market history
  - history sync scope is bounded to curated target-market regions plus market-relevant items instead of all imported universe items
  - foundation import excludes non-marketable published items from the item catalog bootstrap
  - backend tests cover 404 history responses, market-group filtering, and scoped history sync behavior
- files changed:
  - `backend/app/services/esi/client.py`
  - `backend/app/services/sync/foundation_import.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_esi_client.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
  - `backend/tests/services/test_foundation_import.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Stopped the history sync from treating the full imported universe as immediately history-syncable by filtering the foundation item import to market-group types, skipping per-type ESI 404 history responses, and limiting the sync job to curated target regions with order-backed or demand-backed items.
- important decisions:
  - kept the manual history job aligned to the current app trading scope rather than attempting an impractical universe-wide `region x type` crawl
  - used raw NPC orders as the primary market-item scope and resolved demand rows as a fallback so the job still works in normal sync flows
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`

- task id: `INGESTION-FOUNDATION-ORDERS-2026-03-23`
- title: Bulk SDE Foundation Import And NPC Order Ingestion
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 6, 12A, 13, 17.1, 17.2
- acceptance criteria covered:
  - a real foundation import job now persists non-demo regions, systems, stations, and items from a bulk Fuzzwork SDE SQLite dump
  - a raw NPC market order table and ingestion path now persist active regional ESI orders
  - NPC order sync backfills missing station and item reference rows as live orders are discovered
  - stale regional orders are removed on rerun so the raw order table reflects current active ESI state
  - sync dashboard actions now expose explicit SDE import and NPC order sync jobs
- files changed:
  - `backend/app/models/all_models.py`
  - `backend/app/repositories/seed_data.py`
  - `backend/app/core/config.py`
  - `backend/app/services/esi/client.py`
  - `backend/app/services/esi/orders_ingestion.py`
  - `backend/app/services/sync/foundation_import.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_esi_client.py`
  - `backend/tests/services/test_foundation_import.py`
  - `backend/tests/services/test_sync_service.py`
  - `frontend/src/components/sync/ManualSyncActions.tsx`
- short implementation summary: Added a bulk SDE-backed foundation import path plus a first real raw NPC order ingestion pipeline, both wired into explicit sync jobs and validated with backend/client tests.
- important decisions:
  - startup bootstrap still uses the safe curated seed set, while the bulk SDE import is exposed as an explicit sync job to avoid a heavy first-run network dependency
  - foundation import now uses the Fuzzwork bulk SQLite dump for static data instead of one-by-one ESI universe hydration
  - raw NPC orders are stored as the current active state per region, with stale orders deleted when absent from the latest ESI pull
- open follow-ups:
  - derive current source/target prices and liquidity directly from `esi_market_orders` instead of relying on regional history placeholders
  - wire raw order books into the trade item detail panel and opportunity generation metrics
  - add UI visibility for order-sync job status and raw order counts beyond the manual action trigger
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `npm.cmd run build`
  - `npm.cmd test -- --run SyncPage`

- task id: `SYNC-CANCELLATION-2026-03-23`
- title: Cooperative Sync Job Cancellation
- status: `PASS`
- spec refs: user-requested sync operability improvement
- acceptance criteria covered:
  - sync jobs now persist active `running` state instead of appearing only as pending placeholders
  - the backend exposes a cancel endpoint for in-flight jobs
  - long-running sync jobs cooperatively observe cancellation requests and finish as `cancelled`
  - sync dashboard job history now exposes cancel controls for active jobs
  - process shutdown signals such as `Ctrl+C` now set the same cancellation path for cooperative job exit
- files changed:
  - `backend/app/api/routes/sync.py`
  - `backend/app/services/esi/orders_ingestion.py`
  - `backend/app/services/sync/foundation_data.py`
  - `backend/app/services/sync/foundation_import.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/api/test_endpoints.py`
  - `backend/tests/services/test_sync_service.py`
  - `frontend/src/api/sync.ts`
  - `frontend/src/components/sync/JobHistoryTable.tsx`
  - `frontend/src/hooks/useSyncData.ts`
  - `frontend/src/pages/SyncPage.tsx`
  - `frontend/src/pages/SyncPage.test.tsx`
- short implementation summary: Added cooperative cancellation to the sync pipeline, exposed it through the API and dashboard, and wired process interrupt handling into the same job-cancellation flow.
- important decisions:
  - cancellation is cooperative rather than destructive, so already-committed partial ingestion work is preserved
  - long foundation imports now checkpoint commits periodically so local SQLite users can successfully issue a cancel request during large runs
  - active jobs are surfaced as `running` or `cancelling`, and finish as `cancelled` when the cancellation checks observe the request
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `npm.cmd run build`
  - `npm.cmd test -- --run SyncPage`

- task id: `DATABASE-BROWSER-2026-03-23`
- title: Database Table Browser Page
- status: `PASS`
- spec refs: user-requested diagnostics UI
- acceptance criteria covered:
  - a new `Database` menu entry routes to a browser-style table inspection page
  - the page lists database tables and lets the user pick any table to inspect
  - selected tables render all columns in a standard sortable tabular view
  - backend API endpoints expose table names, row counts, and row data for browser inspection
  - backend and frontend tests cover the API, route wiring, and page rendering
- files changed:
  - `backend/app/api/routes/__init__.py`
  - `backend/app/api/routes/database.py`
  - `backend/app/api/schemas/database.py`
  - `backend/tests/api/test_endpoints.py`
  - `frontend/src/api/database.ts`
  - `frontend/src/components/common/AppShell.tsx`
  - `frontend/src/hooks/useDatabaseData.ts`
  - `frontend/src/pages/DatabasePage.tsx`
  - `frontend/src/pages/DatabasePage.test.tsx`
  - `frontend/src/routes/AppRoutes.tsx`
  - `frontend/src/routes/AppRoutes.test.tsx`
  - `frontend/src/styles/global.css`
  - `frontend/src/types/database.ts`
- short implementation summary: Added a diagnostics-focused database browser that reflects the live SQLAlchemy tables through a small API and renders them in a standard sortable table UI.
- important decisions:
  - table rows are capped to a safe browser payload size and ordered by primary key descending when available
  - client-side sorting keeps the backend API simple while still making ad hoc inspection usable
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
  - `npm.cmd test -- --run DatabasePage`
  - `npm.cmd test -- --run AppRoutes`
  - `npm.cmd run build`

- task id: `SYNC-FULL-SCOPE-2026-03-23`
- title: Expand Manual Sync Jobs To Full Dataset Scope
- status: `PASS`
- spec refs: `DESIGN_PROMPT.md` sections 5, 6, 12A
- acceptance criteria covered:
  - Adam4EVE sync runs across all seeded NPC locations and items instead of a tiny sample
  - ESI history sync runs across all seeded regions and items instead of a tiny sample
  - Sync All Characters now executes a real backend character sync over all enabled characters
  - sync status cards include structure snapshot and character sync job families
- files changed:
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Removed hardcoded sync caps, added a real `character_sync` job path, and broadened job accounting/status coverage to full current dataset scope.
- important decisions:
  - scoped “everything” to all currently seeded or connected rows in the local database, not arbitrary out-of-band universe data
- validation:
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy backend`
  - `& '.\backend\.venv\Scripts\python.exe' -m ruff check backend --fix`
- task id: `DOCKER-LIVE-REQUEST-SQL-STDOUT-2026-03-27`
- title: Make Backend Docker Logs Show Live Requests And SQL
- status: `PASS`
- spec refs: user-requested Docker Desktop backend observability
- acceptance criteria covered:
  - backend container logs show one line per live HTTP request while using the Dockerized dev stack
  - backend container logs show SQL emitted by API-triggered database activity, not only startup probes
  - logging configuration preserves Uvicorn access logger visibility after app logging setup runs
- files changed:
  - `docker-compose.yml`
  - `backend/app/core/logging.py`
  - `backend/app/db/session.py`
  - `backend/tests/test_logging.py`
- short implementation summary: Explicitly enabled Uvicorn access logging in Docker, restored `uvicorn.access` logger configuration after app logging initialization, and wrote request/SQL lines directly to container stdout so Docker Desktop shows them reliably during live backend activity.
- important decisions:
  - favored container-stdout visibility over relying purely on logger propagation, because Docker Desktop was not reliably surfacing normal request traffic from the existing logging stack
  - kept the structured app loggers in place alongside stdout emission so tests and non-Docker observability paths still work
- validation:
  - live Docker verification with `docker compose up -d --build backend`
  - live request check with `curl.exe -s http://localhost:8000/health`
  - live DB-backed check with `curl.exe -s http://localhost:8000/api/database/tables`
  - `docker logs eve-station-trader-dev-backend-1 --since 20s`
  - `& '.\backend\.venv\Scripts\ruff.exe' check . --fix`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy .`
  - `& '.\backend\.venv\Scripts\python.exe' -m pytest`
- task id: `DIRECT-DEMAND-WITHOUT-CONFIDENCE-2026-03-28`
- title: Remove Demand Confidence Scoring From Resolved Demand
- status: `PASS`
- spec refs: user-requested demand simplification for Adam4EVE/static demand and resolved-demand outputs
- acceptance criteria covered:
  - resolved demand now treats Adam4EVE demand as a direct value instead of attaching a confidence score
  - local structure demand now resolves from direct `buy_from_sell` units over the requested period when a structure period exists
  - trade and fallback API/UI payloads no longer expose demand confidence fields or filters
  - settings no longer expose the removed local-demand confidence threshold
- files changed:
  - `backend/app/models/all_models.py`
  - `backend/app/services/structures/demand_periods.py`
  - `backend/app/services/demand/market_demand.py`
  - `backend/app/services/demand/resolver.py`
  - `backend/app/api/schemas/trade.py`
  - `backend/app/api/schemas/sync.py`
  - `backend/app/api/schemas/settings.py`
  - `backend/app/repositories/trade_repository.py`
  - `backend/app/services/opportunities/aggregator.py`
  - `backend/app/services/opportunities/generation.py`
  - `backend/app/services/settings_service.py`
  - `backend/app/repositories/seed_data.py`
  - `backend/alembic/versions/20260328_0007_remove_demand_confidence.py`
  - `frontend/src/api/settings.ts`
  - `frontend/src/api/trade.ts`
  - `frontend/src/types/sync.ts`
  - `frontend/src/types/trade.ts`
  - `frontend/src/components/sync/FallbackDiagnosticsTable.tsx`
  - `frontend/src/components/trade/ItemOpportunityTable.tsx`
  - `frontend/src/components/trade/SourceSummaryTable.tsx`
  - `frontend/src/components/trade/TradeControls.tsx`
  - `frontend/src/pages/SettingsPage.tsx`
  - `frontend/src/pages/TradePage.tsx`
  - demand/trade/settings test files covering the updated contract
- short implementation summary: Removed demand confidence columns from resolved-demand and opportunity persistence, changed structure demand periods to count only `buy_from_sell` units per period, resolved local structure demand whenever a period row exists, and removed the corresponding trade filters, diagnostics fields, and settings knob.
- important decisions:
  - kept fallback behavior as an explicit `regional_fallback` row when no local structure period exists, instead of using coverage/confidence thresholds
  - left unrelated character and tracked-structure confidence fields untouched because they describe structure discovery quality rather than market demand
- validation:
  - `& '.\backend\.venv\Scripts\ruff.exe' check . --fix`
  - `& '.\backend\.venv\Scripts\python.exe' -m mypy .`
  - `npm test`
  - `npm run build`
  - backend `pytest` remains blocked in this session because the required Postgres test database on `localhost:5432` was unavailable and `docker compose up -d postgres` failed against the local Docker engine

## RAW-ADAM-STAGING-AND-RESOLVED-METRICS-2026-03-28

- files changed:
  - `backend/app/models/all_models.py`
  - `backend/app/models/__init__.py`
  - `backend/app/services/postgres_copy.py`
  - `backend/app/services/adam4eve/client.py`
  - `backend/app/services/adam4eve/ingestion.py`
  - `backend/app/services/demand/market_demand.py`
  - `backend/app/services/structures/demand_periods.py`
  - `backend/app/services/opportunities/generation.py`
  - `backend/app/services/sync/service.py`
  - `backend/app/api/routes/database.py`
  - `backend/alembic/versions/20260328_0008_raw_adam_market_orders_staging.py`
  - backend Adam/demand/sync/database test files updated to the new raw staging contract
- short implementation summary: Replaced the transformed Adam daily-import table with a raw `adam_market_orders_trade_raw` staging table that matches the Adam4EVE CSV columns and is loaded directly through PostgreSQL `COPY`. Demand resolution now runs as a second step in code and persists explicit buy-from-sell and sell-to-buy totals for the selected period plus the latest-day values in `market_demand_resolved`.
- important decisions:
  - kept trade-page daily demand semantics by mapping `target_demand_day` to `market_demand_resolved.buy_from_sell_yesterday`
  - updated structure-derived demand to emit the same four resolved metrics so NPC and structure targets share one resolved-demand shape
  - assumed the latest Adam4EVE market-orders export contains the raw history window we need, so each sync refresh replaces the staging table with the newest export before rebuilding resolved rows
- validation:
  - `backend\.venv\Scripts\ruff.exe check backend/app backend/tests --fix`
  - `backend\.venv\Scripts\python.exe -m mypy backend/app backend/tests`
  - `backend\.venv\Scripts\python.exe -m pytest backend/tests -q`
  - backend `pytest` remains blocked in this session because the required Postgres test database on `localhost:5432` was unavailable

## QUIETER-BACKEND-LOGGING-2026-03-28

- files changed:
  - `backend/app/core/logging.py`
  - `backend/app/db/session.py`
  - `backend/app/services/settings_service.py`
- short implementation summary: Removed the direct stdout prints from request and SQL logging, kept normal backend request/import/application logs at `INFO` by default, and moved SQL statement logging to `DEBUG` so it only appears when debug mode is enabled.
- important decisions:
  - left application/request logs on `INFO` even in normal mode
  - kept SQL timing/parameter logging instrumentation in place, but emitted it only through the debug logger instead of unconditional prints
  - aligned runtime settings toggles so `debug_enabled` promotes SQL logging alongside the rest of the backend debug behavior
- validation:
  - `backend\.venv\Scripts\ruff.exe check backend/app backend/tests --fix`
  - `backend\.venv\Scripts\python.exe -m mypy backend/app backend/tests`

## SDE-ONLY-FOUNDATION-2026-03-28

- files changed:
  - `backend/app/db/session.py`
  - `backend/app/repositories/seed_data.py`
  - `backend/app/repositories/trade_repository.py`
  - `backend/app/services/sync/foundation_data.py`
  - `backend/app/services/sync/foundation_import.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/conftest.py`
  - `backend/tests/api/test_endpoints.py`
  - `backend/tests/services/test_foundation_data.py`
  - `backend/tests/services/test_sync_service.py`
  - `frontend/src/components/sync/ManualSyncActions.tsx`
  - `frontend/src/pages/SyncPage.test.tsx`
- short implementation summary: Removed the built-in curated foundation seed path so startup and manual sync no longer populate universe data from hardcoded rows. Universe reference data now comes only from the SDE import flow, and trade targets are listed from imported NPC stations instead of a curated station allowlist.
- important decisions:
  - stopped auto-bootstrapping foundation rows during backend startup; migrations and settings initialization still run
  - removed the `foundation_seed_sync` action from backend and frontend rather than keeping a dead alias
  - kept the generic foundation seed-source interfaces for SDE import plumbing and tests, but removed the curated default source and constants
- validation:
  - `backend\.venv\Scripts\ruff.exe check backend/app backend/tests --fix`
  - `backend\.venv\Scripts\python.exe -m mypy backend/app backend/tests`
  - `npm test -- --run`
  - `npm run build`
  - `backend\.venv\Scripts\python.exe -m pytest`
  - backend `pytest` remains blocked in this session because the required Postgres test database on `localhost:5432` was unavailable during collection

## ADAM-STATION-HISTORY-STAGING-2026-03-28

- files changed:
  - `backend/app/services/adam4eve/client.py`
  - `backend/app/services/adam4eve/history_ingestion.py`
  - `backend/app/services/postgres_copy.py`
  - `backend/app/services/pricing/market_price_periods.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_adam4eve_client.py`
  - `backend/tests/services/test_adam4eve_ingestion.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Switched Adam station history sync to a staging-first SQL import flow. Matching weekly Adam CSVs are now cached, copied whole into SQL staging, filtered and cast inside SQL, and then transformed into the internal Adam history tables. The sync also now tolerates `price_date`, ignores repeated header rows embedded inside Adam files, and caps the rolling history window to 14 days.
- important decisions:
  - kept CCP ESI limited to SDE and live order data; historical price input now stays on the Adam4EVE path
  - filtered weekly station history exports before download/import using export covered dates so the sync no longer walks the full 2022+ backlog on every run
  - changed market price period region refresh from update-in-place with huge `OR` deletes to scoped delete-and-reinsert so large region refreshes do not hit PostgreSQL parameter limits
- validation:
  - `backend\.venv\Scripts\ruff.exe check backend --fix`
  - `backend\.venv\Scripts\python.exe -m mypy backend`
  - `backend\.venv\Scripts\python.exe -m pytest backend/tests/services/test_adam4eve_client.py backend/tests/services/test_adam4eve_ingestion.py backend/tests/services/test_esi_history_ingestion.py backend/tests/services/test_market_price_periods.py backend/tests/services/test_sync_service.py`
  - `backend\.venv\Scripts\python.exe -m pytest backend`
  - full backend `pytest` still has 2 unrelated pre-existing failures in `backend/tests/services/test_structure_demand_periods.py` and `backend/tests/test_logging.py`
  - live benchmark of `SyncService().trigger_job("adam4eve_sync")`: success in about `120.9s` with `118741` history rows created and `28712` price periods computed

## ADAM-DEMAND-BULK-REFRESH-2026-03-29

- files changed:
  - `backend/app/services/demand/market_demand.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_market_demand.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Replaced the per-key Adam NPC demand refresh loop with a bulk PostgreSQL refresh. Demand keys are now staged into a temp table, latest scan dates and rolling-window aggregates are computed in SQL with grouped joins, stale resolved rows are deleted in one statement, and refreshed demand rows are bulk upserted instead of doing thousands of Python-driven round trips.
  Added a regression test that writes a tiny Adam CSV fixture, computes the expected 14-day demand metrics manually from that fixture, stages it through the real Adam raw import path, and asserts the bulk SQL output matches exactly.
- important decisions:
  - kept the non-PostgreSQL fallback on the old per-key path so tests and alternate environments still work without COPY/temp-table support
  - counted refreshed Adam demand keys inside the same transaction as the temp-key table so the bulk path stays compatible with `ON COMMIT DROP`
  - left structure demand resolution behavior unchanged; only the Adam NPC refresh path was collapsed into set-based SQL
- validation:
  - `backend\.venv\Scripts\python.exe -m ruff check app/services/demand app/services/sync tests/services/test_market_demand.py tests/services/test_sync_service.py`
  - `backend\.venv\Scripts\python.exe -m mypy app/services/demand/market_demand.py app/services/sync/service.py tests/services/test_market_demand.py tests/services/test_sync_service.py`
  - `backend\.venv\Scripts\python.exe -m pytest tests/services/test_market_demand.py tests/services/test_sync_service.py`
  - `backend\.venv\Scripts\python.exe -m pytest tests/services/test_market_demand.py`
  - `backend\.venv\Scripts\python.exe -m ruff check . --fix`
  - `backend\.venv\Scripts\python.exe -m mypy .`
  - `backend\.venv\Scripts\python.exe -m pytest`
  - full backend `pytest` ended at `156 passed, 3 failed`; the remaining failures were `backend/tests/services/test_adam4eve_ingestion.py`, `backend/tests/services/test_structure_demand_periods.py`, and `backend/tests/test_logging.py`
  - live cold benchmark after clearing Adam sync data: `SyncService().trigger_job("adam4eve_sync")` completed in about `43.5s`, with `_refresh_market_demand_for_keys` down to about `0.178s` and `MarketDemandResolutionService.refresh_npc_keys_from_adam` down to about `0.176s`

## ADAM-HISTORY-FILTER-STAGE-2026-03-29

- files changed:
  - `backend/app/services/adam4eve/history_ingestion.py`
  - `backend/tests/services/test_adam4eve_ingestion.py`
  - `backend/tests/services/test_market_demand.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Optimized Adam station-history file ingestion by materializing the typed, region/location/type/date-filtered subset into a dedicated temp table once per file and then reusing that temp table for row counting, overlap deletes, raw inserts, and daily-history inserts. This removes repeated rescans of the large weekly stage file for the same filtered result set.
- important decisions:
  - kept the “copy full CSV into staging first” requirement intact; the optimization happens only after the 1:1 COPY into the raw file-stage table
  - preserved the existing raw-history and daily-history outputs so downstream price-period generation stays unchanged
  - left the hub-file path alone structurally even though it often produces zero kept rows, because the hot win was eliminating repeated rescans of the much larger filtered rest export
- validation:
  - `backend\.venv\Scripts\python.exe -m ruff check app/services/adam4eve/history_ingestion.py tests/services/test_adam4eve_ingestion.py tests/services/test_sync_service.py`
  - `backend\.venv\Scripts\python.exe -m mypy app/services/adam4eve/history_ingestion.py tests/services/test_adam4eve_ingestion.py tests/services/test_sync_service.py`
  - `backend\.venv\Scripts\python.exe -m pytest tests/services/test_adam4eve_ingestion.py tests/services/test_sync_service.py`
  - live cold benchmark after clearing Adam sync data:
    - before this change: full `adam4eve_sync` about `37.2s`, `_sync_adam_regional_price_history` about `28.2s`, `ingest_region_history_file` about `24.8s`
    - after this change: full `adam4eve_sync` about `26.7s`, `_sync_adam_regional_price_history` about `17.8s`, `ingest_region_history_file` about `14.5s`

## ADAM-HISTORY-GLOBAL-CURSOR-2026-03-29

- files changed:
  - `backend/app/services/adam4eve/history_ingestion.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_adam4eve_ingestion.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Removed the Python-side region loop from Adam station-history sync. The history path now uses one global date cursor, builds one SQL workset from live `esi_market_orders` keys, stages each Adam file once, joins staged rows to that workset in SQL, and refreshes market price periods in one pass across the affected locations and items.
- important decisions:
  - changed history watermarking from per-region cursor keys to a single global cursor keyed by `scope_key=\"global\"`
  - preserved the location-to-region hierarchy in SQL by carrying both internal and external ids inside the workset temp table instead of driving region partitioning in Python
  - added a composite primary key on the temp workset join columns after the first implementation regressed the filtered-stage materialization time
- validation:
  - `backend\.venv\Scripts\python.exe -m ruff check app/services/adam4eve/history_ingestion.py app/services/sync/service.py tests/services/test_sync_service.py tests/services/test_adam4eve_ingestion.py`
  - `backend\.venv\Scripts\python.exe -m mypy app/services/adam4eve/history_ingestion.py app/services/sync/service.py tests/services/test_sync_service.py tests/services/test_adam4eve_ingestion.py`
  - `backend\.venv\Scripts\python.exe -m pytest tests/services/test_sync_service.py tests/services/test_adam4eve_ingestion.py`
  - live cold benchmark after clearing Adam sync data:
    - first global-cursor pass regressed badly because filtered-stage materialization became under-indexed
    - after adding the composite workset key: full `adam4eve_sync` about `28.9s`, `_sync_adam_regional_price_history` about `19.7s`, `ingest_region_history_file` about `16.1s`, and filtered-stage materialization about `8.1s`

## ESI-ORDER-BATCH-SQL-2026-03-29

- files changed:
  - `backend/app/services/esi/orders_ingestion.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_esi_orders_ingestion.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Reworked ESI market-order ingestion into a staging-first SQL batch path. The sync still fetches CCP ESI per region because the API requires that, but all downloaded batches are now handed to one combined ingestion pass, staged into SQL once, filtered and counted in SQL, and inserted into `esi_market_orders` via a final set-based insert instead of a Python per-order normalization loop.
- important decisions:
  - removed the NPC-only gate so already-known player-owned structure locations are now included in ESI order sync results
  - changed the skip reason from “not an NPC station” to “location could not be resolved,” which now only covers unknown locations that the local database cannot map
  - kept station discovery limited to unresolved NPC station ids; unknown structure ids still cannot be discovered from the ESI regional orders endpoint alone
- validation:
  - `backend\.venv\Scripts\python.exe -m ruff check app/services/esi/orders_ingestion.py app/services/sync/service.py tests/services/test_esi_orders_ingestion.py tests/services/test_sync_service.py`
  - `backend\.venv\Scripts\python.exe -m mypy app/services/esi/orders_ingestion.py app/services/sync/service.py tests/services/test_esi_orders_ingestion.py tests/services/test_sync_service.py`
  - `backend\.venv\Scripts\python.exe -m pytest tests/services/test_esi_orders_ingestion.py tests/services/test_sync_service.py`
  - exact `Sync NPC Orders Now` button-path benchmark after clearing ESI orders:
    - enqueue response about `18.9 ms`
    - background completion about `4.7s`
    - recorded job duration about `4.6s`
    - previous button-path baseline before the batch SQL refactor was about `46.5s`

## TRADE-TARGET-RESOLVED-STATION-NAME-2026-03-29

- files changed:
  - `backend/app/repositories/trade_repository.py`
  - `backend/tests/services/test_trade_repository.py`
- short implementation summary: Updated the trade repository to display the first non-placeholder market name between `Station.name` and `Location.name` so the trade target and source labels no longer fall back to `Station 600...` style ids when a resolved station name exists.
- important decisions:
  - kept the fix in the backend repository layer so both the target market dropdown and source market summaries inherit the same resolved naming behavior
  - treated names beginning with `Station ` as placeholders and preferred the alternate station/location name when available
- validation:
  - `backend\.venv\Scripts\ruff.exe check app/repositories/trade_repository.py tests/services/test_trade_repository.py`
  - `backend\.venv\Scripts\python.exe -m mypy app/repositories/trade_repository.py tests/services/test_trade_repository.py`
  - `backend\.venv\Scripts\python.exe -m pytest tests/services/test_trade_repository.py -q`

## FOUNDATION-STATION-NAME-REPAIR-2026-03-29

- files changed:
  - `backend/app/services/sync/foundation_data.py`
  - `backend/app/services/sync/foundation_import.py`
  - `backend/tests/services/test_foundation_data.py`
  - `backend/tests/services/test_foundation_import.py`
- short implementation summary: Changed foundation seeding so resolved station/location names can repair placeholder `Station 600...` names, while placeholder seed data can no longer overwrite already-resolved names. This protects live ESI-resolved station names from later CCP bulk imports that still omit station labels.
- important decisions:
  - allowed non-placeholder seed names to update existing `stations` and `locations`
  - blocked placeholder incoming names from replacing an existing resolved station/location name
  - applied the rule in both the ORM bootstrap path and the PostgreSQL COPY import path
- validation:
  - `backend\.venv\Scripts\ruff.exe check app/services/sync/foundation_data.py app/services/sync/foundation_import.py tests/services/test_foundation_data.py tests/services/test_foundation_import.py`
  - `backend\.venv\Scripts\python.exe -m mypy app/services/sync/foundation_data.py app/services/sync/foundation_import.py tests/services/test_foundation_data.py tests/services/test_foundation_import.py`
  - `backend\.venv\Scripts\python.exe -m pytest tests/services/test_foundation_data.py tests/services/test_foundation_import.py -q`
  - live repair run:
    - reran `foundation_import_sync`
    - backfilled `5154` placeholder NPC station names from ESI station metadata into both `stations` and `locations`

## ESI-MARKET-ORDERS-DUPLICATE-STAGE-DEDUPE-2026-03-30

- files changed:
  - `backend/app/services/esi/orders_ingestion.py`
  - `backend/tests/services/test_esi_orders_ingestion.py`
- short implementation summary: Hardened the PostgreSQL ESI market-order staging path to deduplicate repeated `order_id` rows before inserting the refreshed region snapshot into `esi_market_orders`, preventing the large March 29 import from failing on the unique `order_id` constraint.
- important decisions:
  - traced the live PostgreSQL failure in `sync_job_runs` id `115` to `duplicate key value violates unique constraint "esi_market_orders_order_id_key"` during the final insert from `esi_market_orders_valid_stage`
  - kept the fix inside the PostgreSQL batch-ingestion path so the import remains a full snapshot replacement while tolerating repeated ESI rows for the same order
  - used deterministic `DISTINCT ON (stage.order_id)` ordering so the latest staged copy of a duplicated order wins
- validation:
  - `backend\.venv\Scripts\ruff.exe check . --fix`
  - `backend\.venv\Scripts\python.exe -m pytest tests/services/test_esi_orders_ingestion.py -q`
  - repo-wide checks attempted:
    - `backend\.venv\Scripts\python.exe -m mypy .`
    - `backend\.venv\Scripts\python.exe -m pytest`
  - repo-wide checks currently still fail for unrelated pre-existing issues in:
    - `backend/tests/services/test_esi_history_ingestion.py`
    - `backend/tests/services/test_structure_demand_periods.py`
    - `backend/tests/test_logging.py`
    - `backend/tests/api/test_endpoints.py`

## FOUNDATION-SDE-FULL-TYPE-IMPORT-2026-03-30

- files changed:
  - `backend/app/services/sync/foundation_import.py`
  - `backend/tests/services/test_foundation_import.py`
- short implementation summary: Removed the SDE item pruning rules so foundation import now keeps all `types.jsonl` rows instead of dropping entries without `marketGroupID`, blueprint entries, or rows flagged unpublished.
- important decisions:
  - left the bulk source unchanged and widened only the importer behavior
  - kept group/category metadata when present, including blueprint categorization, instead of using those fields as exclusion rules
- validation:
  - `backend\.venv\Scripts\ruff.exe check app/services/sync/foundation_import.py tests/services/test_foundation_import.py`
  - `backend\.venv\Scripts\python.exe -m pytest tests/services/test_foundation_import.py -q`
  - `backend\.venv\Scripts\python.exe -m mypy app/services/sync/foundation_import.py tests/services/test_foundation_import.py`

## ESI-MARKET-ORDERS-LOCATION-RESOLUTION-2026-03-30

- files changed:
  - `backend/app/services/esi/orders_ingestion.py`
  - `backend/tests/services/test_esi_orders_ingestion.py`
- short implementation summary: Fixed ESI order location resolution so cross-region market orders can reuse an existing location by `location_id` alone, and public structure-like ids now get a placeholder `structure` location row instead of being dropped immediately.
- important decisions:
  - removed the stage-time `region_id` requirement from the `locations` join because ESI market-region ids do not always match the location’s home region
  - created placeholder structure locations from the order payload’s `system_id` for trillion-range public structure ids when no location row exists yet
  - kept unresolved rows unresolved when even the referenced solar system is unknown, rather than inventing partial location metadata
- validation:
  - `backend\.venv\Scripts\ruff.exe check app/services/esi/orders_ingestion.py tests/services/test_esi_orders_ingestion.py`
  - `backend\.venv\Scripts\python.exe -m pytest tests/services/test_esi_orders_ingestion.py -q`
  - `backend\.venv\Scripts\python.exe -m mypy app/services/esi/orders_ingestion.py tests/services/test_esi_orders_ingestion.py`

## TRADE-TARGET-HUBS-AND-UNIVERSE-WIDE-SOURCING-2026-03-30

- files changed:
  - `backend/app/api/routes/targets.py`
  - `backend/app/api/schemas/settings.py`
  - `backend/app/repositories/trade_repository.py`
  - `backend/app/services/opportunities/generation.py`
  - `backend/app/services/settings_service.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/api/test_endpoints.py`
  - `backend/tests/services/test_opportunity_generation.py`
  - `backend/tests/services/test_trade_repository.py`
  - `frontend/src/api/settings.ts`
  - `frontend/src/api/trade.ts`
  - `frontend/src/components/trade/ItemOpportunityTable.tsx`
  - `frontend/src/hooks/useTradeData.ts`
  - `frontend/src/pages/SettingsPage.test.tsx`
  - `frontend/src/pages/SettingsPage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
  - `frontend/src/pages/TradePage.tsx`
- short implementation summary: Reworked trade opportunity generation so the selected target hub is the single destination market, profitable source stations are considered universe-wide, and `target_now_profit` now compares live minimum sell at the source station versus live minimum sell at the selected target hub. Added configurable target hubs on Settings and limited the trade target selector to that configured list.
- important decisions:
  - kept the trade-page target selector single-select and moved the multi-select hub curation into Settings
  - changed target option discovery to use all known `npc_station` and `structure` locations, while the main `/targets` list is filtered by saved settings order
  - refreshed target price history only for the chosen destination location, since source-side now-profit calculations no longer depend on historical source averages
  - changed default ordering for source summaries and item drilldown rows to descending `target_now_profit`
- validation:
  - `backend\.venv\Scripts\ruff.exe check backend/app/services/sync/service.py backend/app/services/opportunities/generation.py backend/app/services/settings_service.py backend/app/repositories/trade_repository.py backend/tests/services/test_opportunity_generation.py backend/tests/services/test_trade_repository.py backend/tests/api/test_endpoints.py`
  - `backend\.venv\Scripts\python.exe -m mypy backend/app/services/sync/service.py backend/app/services/opportunities/generation.py backend/app/repositories/trade_repository.py backend/app/services/settings_service.py backend/tests/services/test_opportunity_generation.py backend/tests/services/test_trade_repository.py backend/tests/api/test_endpoints.py`
  - `backend\.venv\Scripts\python.exe -m pytest backend/tests/services/test_trade_repository.py backend/tests/api/test_endpoints.py -k "get_targets or get_target_options or get_settings or put_settings_persists_debug_flag"`
  - `npm test -- src/pages/TradePage.test.tsx src/pages/SettingsPage.test.tsx`
  - `npm run build`
  - attempted broader backend pytest for touched slices:
    - `backend\.venv\Scripts\python.exe -m pytest backend/tests/services/test_opportunity_generation.py backend/tests/services/test_trade_repository.py backend/tests/api/test_endpoints.py`
  - broader backend pytest currently still hits a pre-existing API fixture/session teardown issue around `backend/tests/api/test_endpoints.py::test_get_auth_me`

## TRADE-REFRESH-AND-MISSING-TARGET-PRICE-FALLBACK-2026-03-30

- files changed:
  - `backend/app/api/routes/opportunities.py`
  - `backend/app/repositories/trade_repository.py`
  - `backend/app/services/opportunities/generation.py`
  - `backend/tests/api/test_endpoints.py`
  - `backend/tests/services/test_opportunity_generation.py`
  - `frontend/src/api/trade.ts`
  - `frontend/src/pages/TradePage.test.tsx`
  - `frontend/src/pages/TradePage.tsx`
- short implementation summary: Fixed the empty trade page for major hub targets by allowing opportunity generation to fall back to the live target sell price when Adam station period history is missing, and made the Trade page `Refresh` button trigger a real backend rebuild for the currently selected target before refetching the tables.
- important decisions:
  - kept `target_now_profit` as the primary metric and reused the live target sell price as the temporary period-price fallback so rows are still generated when history has not been imported for that hub yet
  - added a dedicated `POST /api/opportunities/refresh` endpoint instead of overloading the existing read endpoints with forced rebuild behavior
  - kept the existing on-demand rebuild-on-miss behavior for first loads, and used the explicit refresh action for manual recomputation
- validation:
  - `backend\.venv\Scripts\ruff.exe check backend/app/services/opportunities/generation.py backend/app/repositories/trade_repository.py backend/app/api/routes/opportunities.py backend/tests/services/test_opportunity_generation.py backend/tests/api/test_endpoints.py`
  - `backend\.venv\Scripts\python.exe -m mypy backend/app/services/opportunities/generation.py backend/app/repositories/trade_repository.py backend/app/api/routes/opportunities.py backend/tests/services/test_opportunity_generation.py backend/tests/api/test_endpoints.py`
  - `backend\.venv\Scripts\python.exe -m pytest backend/tests/services/test_opportunity_generation.py backend/tests/api/test_endpoints.py -k "opportunity or refresh_trade"`
  - `npm test -- src/pages/TradePage.test.tsx`
  - `npm run build`
  - broader backend validation:
    - `backend\.venv\Scripts\ruff.exe check backend`
    - `backend\.venv\Scripts\python.exe -m mypy backend/app backend/tests`
    - `backend\.venv\Scripts\python.exe -m pytest backend`
    - repo-wide `ruff` passed
    - repo-wide `mypy` still fails in pre-existing `backend/tests/services/test_esi_history_ingestion.py`
    - repo-wide `pytest` still has pre-existing failures in `backend/tests/services/test_esi_history_ingestion.py`, `backend/tests/services/test_structure_demand_periods.py`, `backend/tests/services/test_sync_service.py`, `backend/tests/test_logging.py`, and one API fixture/setup error in `backend/tests/api/test_endpoints.py::test_get_auth_login_returns_actionable_redirect_payload`
  - live verification:
    - `POST http://localhost:8000/api/opportunities/refresh?target_location_id=60003760&period_days=14`
    - `GET http://localhost:8000/api/opportunities/source-summaries?target_location_id=60003760&period_days=14` now returns `4978` source groups
    - `GET http://localhost:8000/api/opportunities/items?target_location_id=60003760&source_location_id=60008494&period_days=14` now returns `8726` item rows

## TRADE-PAGE-LOADING-STATES-2026-03-30

- files changed:
  - `frontend/src/components/trade/SourceSummaryTable.tsx`
  - `frontend/src/components/trade/ItemOpportunityTable.tsx`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
- short implementation summary: Replaced the misleading trade-page empty state shown during long first-load queries with explicit loading copy in the source-summary and item-opportunity tables, so the UI no longer says `0 tracked` or `No computed...` while opportunities are still loading or being computed.
- important decisions:
  - only show the loading rows when the query is still running and there is not yet any data to render
  - keep existing rows visible during background refetches instead of replacing them with a loading placeholder
  - leave the backend-driven on-demand opportunity build behavior intact and make the frontend reflect that long-running work honestly
- validation:
  - `npm test -- src/pages/TradePage.test.tsx`
  - `npm run build`
  - live API check for the screenshot target:
    - `GET http://localhost:8000/api/opportunities/source-summaries?target_location_id=60008494&period_days=14` returns `4748` source groups in about `0.74s`

## TRADE-GROUPED-INLINE-DRILLDOWN-2026-03-30

- files changed:
  - `frontend/src/components/trade/SourceSummaryTable.tsx`
  - `frontend/src/components/trade/TradeControls.tsx`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
  - `frontend/src/styles/global.css`
- short implementation summary: Reworked the trade page into a single grouped opportunities table where source-market rows expand inline to show that station's item opportunities for the selected target market, and every visible column in that grouped table is now sortable.
- important decisions:
  - kept only one expanded source market open at a time and reused the existing per-source item query for the inline drilldown
  - used a shared sort model for both source summary rows and expanded item rows so the same header controls work across the grouped view
  - kept the execution-context detail panel and wired it to item clicks inside the expanded group rows
- validation:
  - `npm test -- src/pages/TradePage.test.tsx`
  - `npm run build`

## TRADE-GROUP-TOTAL-SORT-AND-FAST-EXPANSION-2026-03-30

- files changed:
  - `backend/app/services/opportunities/aggregator.py`
  - `backend/tests/services/test_aggregator.py`
  - `backend/tests/services/test_opportunity_generation.py`
  - `frontend/src/components/trade/SourceSummaryTable.tsx`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
  - `frontend/src/styles/global.css`
- short implementation summary: Fixed grouped trade ordering so source-market rows now sort by total station profit for the selected target instead of a weighted per-item margin, and reduced expand-time UI work by rendering large inline item groups in batches with a `Show more` control.
- important decisions:
  - kept the existing summary schema field names to avoid a wider API/storage churn, but changed the stored summary profit values to represent group totals based on each item's `purchase_units`
  - preserved full inline drilldown behavior while capping the initial expanded render to `200` rows so large stations no longer mount thousands of DOM rows at once
  - reset the expanded render window on target, period, source, and sort changes so the grouped table stays predictable after control changes
- validation:
  - `backend\.venv\Scripts\python.exe -m ruff check backend/app/services/opportunities/aggregator.py backend/tests/services/test_aggregator.py backend/tests/services/test_opportunity_generation.py`
  - `backend\.venv\Scripts\python.exe -m mypy backend/app/services/opportunities/aggregator.py backend/tests/services/test_aggregator.py backend/tests/services/test_opportunity_generation.py`
  - `backend\.venv\Scripts\python.exe -m pytest backend/tests/services/test_aggregator.py backend/tests/services/test_opportunity_generation.py -q`
  - `backend\.venv\Scripts\python.exe -m ruff check backend --fix`
  - `backend\.venv\Scripts\python.exe -m mypy backend/app backend/tests`
  - `backend\.venv\Scripts\python.exe -m pytest backend -q`
  - `npm test -- src/pages/TradePage.test.tsx`
  - `npm run build`
  - live verification:
    - restarted `eve-station-trader-dev-backend-1`, `eve-station-trader-dev-frontend-1`, and `eve-station-trader-dev-worker-1`
    - `POST http://localhost:8000/api/opportunities/refresh?target_location_id=60008494&period_days=14` completed successfully at `2026-03-30T17:03:06.458247Z`
    - `GET http://localhost:8000/api/opportunities/source-summaries?target_location_id=60008494&period_days=14` returns `4748` Amarr source groups and now shows large total-profit summary values such as `69940660.0`
  - broader backend checks still have pre-existing unrelated failures in:
    - `backend/tests/services/test_esi_history_ingestion.py`
    - `backend/tests/services/test_structure_demand_periods.py`
    - `backend/tests/services/test_sync_service.py`
    - `backend/tests/test_logging.py`

## TRADE-EFFECTIVE-SOURCE-PRICE-AND-GROUP-PAGINATION-2026-03-30

- files changed:
  - `backend/app/domain/rules.py`
  - `backend/app/services/opportunities/generation.py`
  - `backend/app/api/schemas/settings.py`
  - `backend/app/services/settings_service.py`
  - `backend/tests/domain/test_rules.py`
  - `backend/tests/services/test_opportunity_generation.py`
  - `backend/tests/api/test_endpoints.py`
  - `frontend/src/api/settings.ts`
  - `frontend/src/components/trade/SourceSummaryTable.tsx`
  - `frontend/src/pages/SettingsPage.tsx`
  - `frontend/src/pages/SettingsPage.test.tsx`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
  - `frontend/src/styles/global.css`
- short implementation summary: Corrected trade opportunity pricing so `target_now_profit` is now `target now sell price - effective source acquisition price`, `target_period_profit` is `target period average price - effective source acquisition price`, and the source price now becomes a weighted execution price whenever the cheapest source sell order cannot fill the station's purchase quantity. Added proper grouped-source pagination on the trade page with a settings-backed default of `20` groups per page.
- important decisions:
  - removed sales-tax and broker-fee adjustments from the trade profit formulas to match the requested station-to-station spread view
  - changed source-side price discovery from `MIN(source sell price)` to an execution-weighted price over the actual `purchase_units` quantity, using a SQL windowed workset instead of a per-order Python loop
  - aligned `capital_required` with the actual purchasable quantity by multiplying the effective source acquisition price by `purchase_units`
  - kept grouped pagination on the frontend and persisted only the page-size default in settings, so sorting and expansion still operate on the live grouped result set while rendering only one page of groups at a time
- validation:
  - `backend\.venv\Scripts\python.exe -m ruff check backend/app/domain/rules.py backend/app/services/opportunities/generation.py backend/app/api/schemas/settings.py backend/app/services/settings_service.py backend/tests/domain/test_rules.py backend/tests/services/test_opportunity_generation.py backend/tests/api/test_endpoints.py`
  - `backend\.venv\Scripts\python.exe -m mypy backend/app/domain/rules.py backend/app/services/opportunities/generation.py backend/app/api/schemas/settings.py backend/app/services/settings_service.py backend/tests/domain/test_rules.py backend/tests/services/test_opportunity_generation.py backend/tests/api/test_endpoints.py`
  - `backend\.venv\Scripts\python.exe -m pytest backend/tests/domain/test_rules.py backend/tests/services/test_opportunity_generation.py backend/tests/api/test_endpoints.py -k "settings or opportunity or rules" -q`
  - `backend\.venv\Scripts\python.exe -m ruff check backend --fix`
  - `backend\.venv\Scripts\python.exe -m mypy backend/app backend/tests`
  - `backend\.venv\Scripts\python.exe -m pytest backend -q`
  - `npm test -- src/pages/TradePage.test.tsx src/pages/SettingsPage.test.tsx`
  - `npm run build`
  - live verification:
    - restarted `eve-station-trader-dev-backend-1`, `eve-station-trader-dev-frontend-1`, and `eve-station-trader-dev-worker-1`
    - `POST http://localhost:8000/api/opportunities/refresh?target_location_id=60008494&period_days=14` completed successfully at `2026-03-30T19:11:51.259966Z`
    - `GET http://localhost:8000/api/opportunities/source-summaries?target_location_id=60008494&period_days=14` now returns `4609` Amarr source groups and a top total-profit summary value of `53607200907.82`
  - broader backend checks still have pre-existing unrelated issues:
    - repo-wide `mypy` still fails in `backend/tests/services/test_esi_history_ingestion.py`
    - repo-wide `pytest backend -q` did not complete within the 120-second command timeout after this change

## TRADE-TARGET-PRICE-VERIFICATION-2026-03-31

- files changed:
  - `backend/tests/services/test_market_price_periods.py`
  - `backend/tests/services/test_opportunity_generation.py`
  - `frontend/src/components/trade/SourceSummaryTable.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
  - `frontend/src/styles/global.css`
- short implementation summary: Verified and locked down the trade pricing semantics so item-level `target_period_avg_price` comes from the target station's selected-period Adam4EVE history average, while item-level `target_station_sell_price` comes from the lowest live sell order in the target station. Clarified the grouped trade table copy so weighted grouped prices are no longer presented like literal station prices.
- important decisions:
  - kept the item-level pricing logic unchanged because it already matched the requested behavior
  - added a 14-day history test to prove the period average uses the latest 14 station history rows and excludes older data
  - added an opportunity-generation test to prove the target now price uses the lowest live target sell order even when the historical current/average prices differ
  - left grouped summary math intact and clarified it in the UI instead of changing it to a different aggregation
- validation:
  - `backend\\.venv\\Scripts\\python.exe -m pytest tests/services/test_market_price_periods.py tests/services/test_opportunity_generation.py`
  - `backend\\.venv\\Scripts\\python.exe -m ruff check tests/services/test_market_price_periods.py tests/services/test_opportunity_generation.py`
  - `backend\\.venv\\Scripts\\python.exe -m mypy tests/services/test_market_price_periods.py tests/services/test_opportunity_generation.py`
  - `backend\\.venv\\Scripts\\python.exe -m ruff check .`
  - `npm test -- --run src/pages/TradePage.test.tsx`
  - broader repo checks still have pre-existing unrelated failures:
    - backend `mypy .` fails in `backend/tests/services/test_esi_history_ingestion.py` because the test still calls `ingest_region_history_file` with outdated keyword arguments
    - backend `pytest` has existing unrelated failures in API/sync/logging tests
    - frontend `npm test` has an existing unrelated `src/routes/AppRoutes.test.tsx` mock failure for `useTargetOptions`

## TRADE-PAGE-FILTER-AND-PERIOD-CONTROLS-2026-03-31

- files changed:
  - `frontend/src/components/trade/TradeControls.tsx`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
- short implementation summary: Removed the duplicate `Min ROI` and page-level `Analysis Period` controls from the trade page. The trade page now always uses the analysis period from settings, and `Min Margin %` filters expanded items from the raw target/source price ratio so `20` means the target now price must be at least `1.20x` the source price.
- important decisions:
  - kept the change scoped to the trade page instead of also removing the ROI field from settings
  - changed the margin filter to compare `target_station_sell_price / source_station_sell_price` directly so it matches the visible price columns instead of depending on the profit field
  - left grouped source rows unfiltered and kept the existing behavior where filters apply to expanded item rows
- validation:
  - `npm test -- --run src/pages/TradePage.test.tsx`
  - `npm run build`
  - broader frontend `npm test` still has a pre-existing unrelated failure in `src/routes/AppRoutes.test.tsx` because that test's trade-data mock does not provide `useTargetOptions`

## TRADE-HISTORY-SAME-DAY-REFRESH-2026-03-31

- files changed:
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_sync_service.py`
- short implementation summary: Fixed Adam4EVE station-history refresh so the sync no longer skips same-day history imports when the current ESI workset is still missing 14-day target price periods. This prevents opportunity generation from falling back to `target_station_sell_price` for `target_period_avg_price` just because target station history had not been derived yet.
- important decisions:
  - kept the daily cursor optimization, but only skip the history refresh when the current workset already has the requested price periods
  - used a single SQL existence check against the live ESI workset plus `MarketPricePeriod` rather than expanding the Python workset into a huge in-memory comparison
  - repaired live trade data for the main target hubs by refreshing their derived price periods and rebuilding 14-day opportunities after the missing daily history rows were imported
- validation:
  - `backend\\.venv\\Scripts\\python.exe -m pytest tests/services/test_sync_service.py -k "history_sync_same_day_refreshes_missing_price_periods or history_sync_since_date_caps_to_rolling_14_day_window"`
  - `backend\\.venv\\Scripts\\python.exe -m ruff check app/services/sync/service.py tests/services/test_sync_service.py`
  - `backend\\.venv\\Scripts\\python.exe -m mypy app/services/sync/service.py tests/services/test_sync_service.py`
  - live verification:
    - confirmed `AdamMarketPriceHistoryDaily` now contains target-station history for `60003760`, `60008494`, `60011866`, `60005686`, and `60004588`
    - refreshed derived price periods and rebuilt 14-day trade opportunities for those target hubs
    - spot-checked Jita item rows now showing distinct values, for example:
      - `Nuclear S`: now `11.95`, 14d avg `12.1963`
      - `Gallente Shuttle`: now `16380.0`, 14d avg `16929.7833`
      - `Station Vault Container`: now `325900.0`, 14d avg `325938.0`
      - `True Sansha Warp Scrambler`: now `125000000.0`, 14d avg `122058583.3333`

## TRADE-FILTER-THRESHOLDS-AND-STEPPERS-2026-03-31

- files changed:
  - `frontend/src/components/trade/TradeControls.tsx`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
- short implementation summary: Tightened the trade-page filter behavior so `Min Profit` filters on `target now profit`, `Min Margin %` uses the target/source now-price ratio with a strict threshold, and the numeric trade filters now expose native increment steppers. The trade page keeps analysis period out of the UI and follows settings.
- important decisions:
  - kept `Min ROI` removed and left `Analysis Period` off the trade page
  - made `Min Profit` and `Min Margin %` strict greater-than thresholds to match the requested behavior
  - used native `type="number"` inputs with `step="5"` for margin and `step="0.1"` for demand/day and D.O.S.
- validation:
  - `npm test -- --run src/pages/TradePage.test.tsx`
  - `npm run build`

## TRADE-FILTER-ROI-NOW-AND-REFRESH-SCOPE-2026-03-31

- files changed:
  - `frontend/src/components/trade/TradeControls.tsx`
  - `frontend/src/pages/TradePage.tsx`
  - `backend/app/repositories/trade_repository.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_trade_repository.py`
- short implementation summary: Corrected `Min Margin %` to filter against `ROI Now` instead of the target/source price ratio, and narrowed manual trade refresh to prefer rebuilding the already-tracked opportunity scope before falling back to a full derived-input refresh.
- important decisions:
  - interpreted `Min Margin 20%` as `ROI Now > 120%`, per the requested behavior
  - left `Min Profit` on `target_now_profit > threshold`
  - kept the full prepare path as a fallback when target demand or target price-period inputs are missing
- validation:
  - `npm test -- --run src/pages/TradePage.test.tsx`
  - `npm run build`
  - `backend\\.venv\\Scripts\\python.exe -m ruff check app/repositories/trade_repository.py app/services/sync/service.py tests/services/test_trade_repository.py`
  - `backend\\.venv\\Scripts\\python.exe -m mypy app/repositories/trade_repository.py app/services/sync/service.py tests/services/test_trade_repository.py`
  - note: a direct live target-wide refresh for Jita is still taking several minutes on the current dataset, so the refresh path likely needs a larger follow-up optimization or a UI change to refresh a narrower scope

## TRADE-GROUP-FILTERED-TOTALS-2026-03-31

- files changed:
  - `backend/app/api/routes/opportunities.py`
  - `backend/app/api/schemas/trade.py`
  - `backend/app/repositories/trade_repository.py`
  - `frontend/src/api/trade.ts`
  - `frontend/src/hooks/useTradeData.ts`
  - `frontend/src/types/trade.ts`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
- short implementation summary: Reworked grouped trade filtering so the page filters against a target-wide item dataset, drops any source group with no matching item rows, and recomputes grouped totals from only the matching filtered items instead of retaining unfiltered summary totals.
- important decisions:
  - added a dedicated `/api/opportunities/target-items` endpoint so grouped filtering can run against all target items without repeatedly fetching one source at a time
  - rebuilt grouped summary totals client-side from the filtered item subset to keep group values aligned with expanded rows
  - kept the existing grouped-row sort and pagination behavior, only changing the data feeding those rows
- validation:
  - `npm test -- --run src/pages/TradePage.test.tsx`
  - `npm run build`
  - `backend\\.venv\\Scripts\\python.exe -m ruff check app/api/routes/opportunities.py app/api/schemas/trade.py app/repositories/trade_repository.py tests/api/test_endpoints.py tests/services/test_trade_repository.py`
  - `backend\\.venv\\Scripts\\python.exe -m mypy app/api/routes/opportunities.py app/api/schemas/trade.py app/repositories/trade_repository.py`
  - note: `backend\\.venv\\Scripts\\python.exe -m pytest tests/api/test_endpoints.py -k target_items` timed out in this environment before completion
  - follow-up: fixed a source ID mismatch in `/api/opportunities/target-items` so grouped summaries and filtered item rows now join on the same internal location ID instead of dropping every group

## TRADE-ROI-NOW-DEFAULT-HYDRATION-2026-03-31

- files changed:
  - `frontend/src/components/trade/TradeControls.tsx`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/pages/SettingsPage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
- short implementation summary: Renamed the trade-page threshold control to `Min ROI Now %`, changed it to compare directly against the raw item `roi_now` value so `20` means `ROI Now > 20%`, and hydrated the visible trade filters from saved settings defaults on first load.
- important decisions:
  - kept the grouped table filter semantics item-row based, with group visibility and totals derived from the matching item subset
  - left server-side filtering untouched for now; the page still fetches the target-wide item dataset and filters it client-side
  - aligned the Settings page default trade filter UI to the same percent-based `ROI Now` semantics
- validation:
  - `npm test -- --run src/pages/TradePage.test.tsx src/pages/SettingsPage.test.tsx`
  - `npm run build`

## TRADE-SERVER-SIDE-FILTERING-2026-03-31

- files changed:
  - `backend/app/api/routes/opportunities.py`
  - `backend/app/repositories/trade_repository.py`
  - `backend/app/services/settings_service.py`
  - `backend/tests/api/test_endpoints.py`
  - `frontend/src/api/trade.ts`
  - `frontend/src/hooks/useTradeData.ts`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/pages/SettingsPage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
- short implementation summary: Moved visible trade filters onto the grouped summary and expanded item requests so the page no longer fetches the full target-wide item set on initial load. The first trade query now waits for settings-backed defaults, and the built-in defaults apply both `Min Profit` and `ROI Now` thresholds by default.
- important decisions:
  - interpreted `20` as `ROI Now > 20%`
  - set the built-in default `roi_now` threshold to `0.20` so a default setup applies both the profit and ROI filters immediately
  - kept backend detail loading unchanged; only grouped summaries and expanded item rows moved to server-side filtering
- validation:
  - `npm test -- --run src/pages/TradePage.test.tsx src/pages/SettingsPage.test.tsx`
  - `npm run build`
  - `backend\\.venv\\Scripts\\python.exe -m ruff check app/services/settings_service.py app/repositories/trade_repository.py app/api/routes/opportunities.py tests/api/test_endpoints.py`
  - `backend\\.venv\\Scripts\\python.exe -m mypy app/services/settings_service.py app/repositories/trade_repository.py app/api/routes/opportunities.py`
  - note: `backend\\.venv\\Scripts\\python.exe -m pytest tests/api/test_endpoints.py -k passes_trade_filters -q` timed out in this environment before completion

## 2026-04-01 - OPPORTUNITY-REBUILD-TARGET-SCOPING
- Restricted global opportunity rebuilds to configured 	arget_market_location_ids instead of every resolved-demand location in the database.
- Added a sync-service regression test proving non-configured targets are skipped during _rebuild_opportunities.


## 2026-04-09 - NPC-ESI-DISAPPEARED-ORDER-VOLUME
- Fixed NPC station ESI delta inference so orders that disappear between snapshots now contribute their remaining units to traded-volume inference instead of being recorded as zero-volume trades.
- Added regression coverage for disappeared sell orders, disappeared buy orders, and demand-period aggregation that includes disappeared-order inferred volume.
- Updated opportunity generation so the `ESI Traded Vol` column for NPC targets uses the summed NPC-station ESI demand across the whole target region, then converts that regional period total into a per-day average.
- Added a sync-service guard that returns the existing active `opportunity_rebuild` job instead of starting a duplicate rebuild while one is already running or cancelling.
- Replaced the `ESI Traded Vol` source with official ESI regional market history volume (`/markets/{region}/history`) for all targets, storing rows in `esi_history_daily` and refreshing missing regional histories during rebuilds.
- validation:
  - `backend/.venv/bin/ruff check backend/app/services/npc_stations/deltas.py backend/tests/services/test_npc_station_deltas.py backend/tests/services/test_npc_station_demand_periods.py --fix`
  - `cd backend && ./.venv/bin/pytest -m integration tests/services/test_npc_station_deltas.py tests/services/test_npc_station_demand_periods.py`
  - `cd backend && ./.venv/bin/ruff check app/services/opportunities/generation.py tests/services/test_opportunity_generation.py --fix`
  - `cd backend && ./.venv/bin/pytest -m integration tests/services/test_opportunity_generation.py`
  - `cd backend && ./.venv/bin/ruff check app/services/sync/service.py tests/services/test_sync_service.py --fix`
  - `cd backend && ./.venv/bin/pytest -m integration tests/services/test_sync_service.py -k 'opportunity_rebuild'`
  - `cd backend && ./.venv/bin/pytest tests/services/test_esi_client.py`
  - `cd backend && ./.venv/bin/pytest -m integration tests/services/test_esi_history_ingestion.py tests/services/test_opportunity_generation.py tests/services/test_sync_service.py -k 'opportunity_rebuild or ingest_region_history or regionwide_esi_history_volume'`
  - `docker compose exec -T backend alembic upgrade head`
  - note: full backend `mypy .` and `pytest` are currently blocked by pre-existing branch failures in Adam4EVE client tests, aggregator typing/tests, and existing `rowcount` typing issues outside this bugfix scope

## 2026-04-01 - PRE-REBUILD-ESI-ORDER-REFRESH
- Opportunity rebuild now refreshes NPC ESI market orders immediately beforehand when the last successful esi_market_orders_sync is older than 10 minutes or missing.
- Refactored the ESI market order sync path into a shared helper so standalone syncs and pre-rebuild refreshes use the same ingestion flow and messaging.
- Added sync-service tests covering stale-refresh and fresh-skip behavior before rebuild.

## 2026-04-01 - TRADE-MARKETBROWSER-CONTEXT-MENU
- Added a prebuilt `market_browser_url` to trade opportunity item responses so the frontend can open EveMarketBrowser without reconstructing region or type identifiers client-side.
- Added a right-click context menu on grouped item opportunity rows with an `Open MarketBrowser` action that opens the target-region item page in a new tab.
- Added backend repository coverage for generated MarketBrowser URLs and frontend interaction coverage for the context menu action.

## 2026-04-01 - TARGET-DEMAND-DAY-PERIOD-AVERAGE
- Changed opportunity generation to compute `target_demand_day` from the selected-period demand average (`buy_from_sell_period / period_days`) instead of the latest-day snapshot (`buy_from_sell_yesterday`).
- Aligned source acquisition sizing with the same period-average demand so purchase units, D.O.S., and demand/day all reflect the analysis window consistently.
- Added opportunity-generation regression coverage for period-average demand/day behavior and updated existing expectations for purchase sizing and summary totals.

## 2026-04-01 - OPPORTUNITY-REBUILD-STALE-SCOPE-PRUNING
- Fixed full target-scope opportunity rebuilds to replace the entire stored target scope for that period instead of leaving stale source rows behind when a source fell out of the regenerated set.
- Re-ran the live `opportunity_rebuild` job so old whole-number demand/day rows were purged and replaced with period-average demand/day values.
- Added regression coverage proving full-scope generation prunes stale opportunity item and summary rows.


## 2026-04-01 - ADAM4EVE-MULTI-WEEK-DEMAND-IMPORT
- Expanded Adam4EVE market-order demand sync from a single latest weekly CSV to a rolling multi-export import that covers the active analysis-window lookback instead of collapsing the raw staging table to one scan date.
- Added multi-file Adam market-order ingestion, client export resolution for all weekly demand files after a since-date, and sync guards that only skip demand downloads when the raw table already covers the required history window.
- Added regression coverage for multi-export Adam resolution/import behavior and for the stale-one-week raw-window case that must force a fresh demand download even when the latest export key is already marked synced.

## 2026-04-02 - DATABASE-BROWSER-PAGINATION-FILTERS
- Replaced the hand-rolled database grid with a TanStack React Table browser that supports server-driven pagination, absolute ordering, and per-column filters on the Database page.
- Extended the diagnostics database endpoint to accept paging, sorting, global search, and `filter_<column>` query parameters while preserving Adam market order enrichment columns in the returned dataset.
- Updated frontend and backend regression coverage for database-table browsing, plus frontend container startup/install behavior so new table dependencies are available in Docker development runs.

## 2026-04-05 - SYNC-LAN-API-ACCESS
- Fixed the frontend API client fallback so a browser opened from a LAN host like `http://192.168.x.x:5173` now targets that same host on backend port `8000` instead of incorrectly calling the viewer's local `localhost:8000`.
- Expanded development CORS handling to allow private-network frontend origins, which unblocks `/sync` dashboard requests when the app is accessed from another machine on the same LAN.
- Added frontend regression tests for API base resolution and backend API tests covering LAN-origin CORS preflight behavior.
- validation:
  - `npm test`
  - `docker compose run --rm backend sh -lc "ruff check app/main.py tests/api/test_endpoints.py && mypy app/main.py tests/api/test_endpoints.py"`
  - `docker compose run --rm -e TEST_DATABASE_URL=postgresql+psycopg://eve_trader:eve_trader@postgres:5432/eve_trader_test backend sh -lc "pytest tests/api/test_endpoints.py -k 'cors or targets or sync_status'"`
  - note: full backend `mypy .` is currently blocked by pre-existing failures in `tests/services/test_esi_history_ingestion.py`

## 2026-04-10 - OPPORTUNITY-REBUILD-STAGE-TIMING-AND-DEADLINE
- Added durable `sync_job_stage_runs` telemetry for sync jobs and exposed per-stage timing results on sync job responses so opportunity rebuild progress survives cancellation and can be inspected after the run ends.
- Instrumented the total opportunity rebuild flow with stage timing checkpoints for pre-rebuild ESI refresh, scope loading, ESI history refresh, per-target scope generation, and target-scope sub-stages inside opportunity generation.
- Added a self-enforced 30 minute runtime cap for `opportunity_rebuild`; when exceeded, the job now cancels itself cleanly and preserves all completed and in-flight stage measurements gathered up to that point.
- validation:
  - `cd backend && ./.venv/bin/ruff check app/services/sync/service.py app/services/opportunities/generation.py app/api/schemas/sync.py app/models/all_models.py app/models/__init__.py tests/services/test_sync_service.py --fix`
  - `cd backend && ./.venv/bin/pytest -m integration tests/services/test_sync_service.py::test_trigger_job_opportunity_rebuild_persists_rows_and_sync_job tests/services/test_sync_service.py::test_trigger_job_opportunity_rebuild_persists_stage_timings tests/services/test_sync_service.py::test_opportunity_rebuild_only_processes_configured_target_markets tests/services/test_sync_service.py::test_opportunity_rebuild_refreshes_esi_orders_when_last_sync_is_stale tests/services/test_sync_service.py::test_opportunity_rebuild_skips_esi_orders_when_last_sync_is_fresh tests/services/test_sync_service.py::test_opportunity_rebuild_cancels_after_runtime_limit_and_keeps_partial_stage_timings`
  - note: targeted backend `mypy` remains blocked by pre-existing `rowcount` typing errors in `app/services/npc_stations/deltas.py` and `app/services/demand/market_demand.py`

## 2026-04-11 - ESI-HISTORY-SYNC-SPLIT-AND-LIVE-RATE-UPDATES
- Split scope-based ESI market history refresh out of `opportunity_rebuild` into a dedicated `esi_history_sync` job so rebuilds no longer block on region-history downloads.
- Added a new Sync Dashboard action for `Sync ESI History Now`, a matching clear path for ESI history data, and a new sync status card entry for the standalone history job.
- Added rate-aware progress messages for ESI history refresh, throttled to roughly once per second during type processing, and tightened Sync Dashboard polling to one second so operators can watch live throughput instead of only coarse progress totals.
- Made April 9 Alembic migrations for NPC station deltas and `esi_demand_day` idempotent so API integration startup can safely replay migrations against an already-initialized test schema.
- validation:
  - `cd backend && ./.venv/bin/ruff check app/services/sync/service.py app/domain/enums.py tests/services/test_sync_service.py tests/api/test_endpoints.py alembic/versions/20260409_0010_npc_station_order_deltas.py alembic/versions/20260409_0011_add_esi_demand_day.py --fix`
  - `cd backend && ./.venv/bin/pytest -m integration tests/services/test_sync_service.py::test_trigger_job_opportunity_rebuild_persists_rows_and_sync_job tests/services/test_sync_service.py::test_trigger_job_opportunity_rebuild_persists_stage_timings tests/services/test_sync_service.py::test_esi_history_sync_runs_separately_from_opportunity_rebuild tests/services/test_sync_service.py::test_opportunity_rebuild_does_not_refresh_esi_history_inline tests/services/test_sync_service.py::test_opportunity_rebuild_cancels_after_runtime_limit_and_keeps_partial_stage_timings tests/api/test_endpoints.py::test_run_esi_history_sync tests/api/test_endpoints.py::test_clear_esi_history_sync_data tests/api/test_endpoints.py::test_run_foundation_import_sync tests/api/test_endpoints.py::test_clear_opportunity_rebuild_data`
  - `docker compose exec -T frontend npm test -- --run src/pages/SyncPage.test.tsx`
  - note: targeted backend `mypy` still reports pre-existing failures in `app/services/npc_stations/deltas.py`, `app/services/demand/market_demand.py`, and `app/repositories/trade_repository.py`

## 2026-04-11 - EVEREF-HISTORY-FOUNDATION
- Added the new `app/services/everef` package with an `httpx` client for `totals.json`, rolling available-date resolution, and streamed Everef `.csv.bz2` download/decompression into cached CSV files.
- Added PostgreSQL-only Everef history file ingestion using a temp staging table plus delete-and-insert replacement into `esi_history_daily`, with cancellation checkpoints around the bulk load/upsert boundary.
- Added the `EveRefHistorySyncState` model, exported it from `app.models`, and created Alembic migration `20260411_0015` for the new sync-state table without removing the legacy ESI sync state yet.
- Added client and ingestion regression coverage for download/decompression, date selection, non-PostgreSQL rejection, and staging import replacement behavior.
- validation:
  - `cd backend && ./.venv/bin/ruff check app/services/everef app/models/all_models.py app/models/__init__.py tests/services/test_everef_client.py tests/services/test_everef_history_ingestion.py alembic/versions/20260411_0015_everef_history_sync_state.py --fix`
  - `cd backend && ./.venv/bin/mypy app/services/everef app/models/all_models.py app/models/__init__.py tests/services/test_everef_client.py tests/services/test_everef_history_ingestion.py`
  - `cd backend && ./.venv/bin/pytest tests/services/test_everef_client.py tests/services/test_everef_history_ingestion.py`
  - `cd backend && ./.venv/bin/pytest -m integration tests/services/test_everef_history_ingestion.py::test_ingest_history_file_replaces_existing_rows_and_runs_cancellation_checks`
  - `cd backend && ./.venv/bin/ruff check . --fix`
  - note: full backend `mypy .` is currently blocked by pre-existing failures in `app/services/opportunities/aggregator.py` and `tests/services/test_aggregator.py`; full backend `pytest` is currently blocked by pre-existing failures in `tests/services/test_adam4eve_client.py` and `tests/services/test_aggregator.py`

## 2026-04-12 - CHARACTER-HOLDINGS-AND-IN-TRANSIT-TRADE-METRICS
- Added persisted character asset, character order, and manual in-transit tables plus Alembic migration `20260412_0017`, then wired trade opportunity generation to populate `Assets`, `Active Sell Orders`, and `In Transit` from those sources instead of hard-coded zeroes.
- Extended character sync to refresh asset and character-order holdings alongside accessible structures, and updated the Characters page so the connect flow surfaces the requested scope set instead of only a count.
- Added trade-side in-transit APIs and a new `/trade` overlay for creating/removing target-specific in-transit entries, and updated shopping-list adds to subtract same-item in-transit quantity aggregated across all sources for the selected target while clamping the added quantity to at least `1`.
- validation:
  - `cd backend && ./.venv/bin/ruff check . --fix`
  - `cd backend && ./.venv/bin/pytest -m integration tests/services/test_character_service.py tests/services/test_opportunity_generation.py tests/services/test_trade_repository.py`
  - note: backend `mypy .` is still blocked by pre-existing failures in `app/services/npc_stations/deltas.py`, `app/services/demand/market_demand.py`, and older Alembic migration typing
  - note: frontend tests were not runnable because `frontend/node_modules` is root-owned and `npm ci` fails with `EACCES`, leaving no local `vitest` binary available

## 2026-04-12 - TRADE-MAX-ITEM-VOLUME-FILTER
- Added a new trade filter for maximum item volume in cubic meters, threaded from the trade controls through frontend query params, FastAPI opportunity routes, and trade repository filtering for both grouped source summaries and expanded item rows.
- Removed the grouped-trade helper note under the source summary table so the filter panel no longer shows that comment.
- Added regression coverage for the new volume-cap behavior in the trade page and repository tests, including the case where a strict cap removes every candidate item and drops the grouped source row entirely.
- validation:
  - `cd backend && ./.venv/bin/ruff check app/api/routes/opportunities.py app/repositories/trade_repository.py tests/services/test_trade_repository.py --fix`
  - `cd backend && ./.venv/bin/pytest -m integration tests/services/test_trade_repository.py`
  - `cd frontend && npm test -- --run src/pages/TradePage.test.tsx`

## 2026-04-12 - SHOPPING-LIST-PROFIT-TOTALS
- Extended shopping-list entries to retain per-unit `target_now_profit` and `target_period_profit`, and updated the shopping list overlay to show quantity-scaled row totals for both profit columns alongside total price and volume.
- Renamed the summary label from `Total` to `Total Price` and added aggregate `Total Now Profit` and `Total Period Profit` figures next to it so the overlay shows full list-level profit totals.
- Added frontend regression coverage that verifies both the row values and the summary totals update when the shopping-list quantity changes.
- validation:
  - `cd frontend && npm test -- --run src/pages/TradePage.test.tsx`

## 2026-04-13 - ESI-LIVE-DEMAND-FALLBACK-IN-RESOLVED-DEMAND
- Added nullable ESI-live diagnostics columns to `market_demand_resolved` and Alembic migration `20260412_0018` so resolved demand can persist fallback metadata directly.
- Reworked `MarketDemandResolutionService` so Adam4EVE wins when it resolves nonzero buy-from-sell demand, otherwise resolved demand falls back to a region-history ESI interpolation that estimates daily buy-from-sell vs sell-to-buy volume from the imported central price within the daily high/low range.
- Applied the same ESI-live fallback for structures when no local structure demand period exists, kept yesterday at `0` when the latest history day is missing or zero-volume, and stored diagnostics for valid day count, yesterday/period ratios, and fallback reason.
- validation:
  - `cd backend && ./.venv/bin/ruff check app/services/demand/market_demand.py app/models/all_models.py tests/services/test_market_demand.py alembic/versions/20260412_0018_market_demand_esi_live_diagnostics.py --fix`
  - `cd backend && ./.venv/bin/pytest -m integration tests/services/test_market_demand.py`
  - `cd backend && ./.venv/bin/pytest -m integration tests/services/test_opportunity_generation.py`

## 2026-04-13 - BACKEND-TEST-FAILURE-FIXES
- Updated Adam4EVE market-order export resolution to fetch each weekly CSV and derive `covered_through_date` from the maximum `scanDate` present in the file instead of assuming the ISO week Sunday.
- Changed `fetch_totals_json()` to return the raw Everef `totals.json` payload and adjusted Everef sync date resolution to extract nested `size` values when building the download queue.
- validation:
  - `cd backend && ./.venv/bin/pytest tests/services/test_adam4eve_client.py tests/services/test_everef_client.py --tb=short -q`
  - `cd backend && ./.venv/bin/pytest tests --tb=short -q`
  - `cd backend && ./.venv/bin/ruff check . --fix`
  - note: `cd backend && ./.venv/bin/mypy .` is still blocked by pre-existing failures in `app/services/npc_stations/deltas.py` and older Alembic migrations unrelated to this change

## 2026-04-13 - OPPORTUNITY-REBUILD-SOURCE-REGION-SCOPING
- Reworked opportunity generation to bulk preload items, resolved demand, target price periods, regional ESI history averages, sell-side station liquidity, target live minima, and source effective prices in chunked set-based queries instead of per-type lookups.
- Added configurable `source_region_ids` to backend settings and the Settings page, and changed ESI market-order sync to download only configured source regions plus the regions containing configured target markets.
- Updated regression coverage so settings persistence asserts `source_region_ids`, ESI sync tests assert target-region auto-inclusion alongside configured source regions, and known-system structure orders verify the new location auto-creation path.
- validation:
  - `cd backend && ./.venv/bin/ruff check . --fix`
  - `cd backend && ./.venv/bin/pytest -o addopts='' tests/services/test_sync_service.py::test_esi_market_orders_sync_creates_structure_locations_when_system_is_known tests/services/test_sync_service.py::test_esi_market_orders_sync_scopes_to_configured_source_regions_and_target_regions tests/services/test_opportunity_generation.py`
  - `cd frontend && npm test -- src/pages/SettingsPage.test.tsx`
  - note: `cd backend && ./.venv/bin/mypy .` is still blocked by pre-existing typing failures in older Alembic migrations and `app/services/npc_stations/deltas.py`
  - note: API endpoint integration tests are currently blocked by a pre-existing duplicate-table migration issue when `TestClient` boot runs migrations in the shared test database

## 2026-04-14 - FOUNDATION-IMPORT-TEST-ESI-STUB
- Added a test-only `_resolve_station_names_from_esi()` override to `StubCcpSdeClient` so foundation import tests never make live ESI HTTP calls when station names are absent from the fixture zip.
- Kept the change scoped to `backend/tests/services/test_foundation_import.py`, preserving production fallback behavior while enforcing the no-external-API test constraint.
- validation:
  - `cd backend && .venv/bin/pytest tests/services/test_foundation_import.py -m integration --tb=short -q`
  - `cd backend && .venv/bin/pytest -m "not integration" --tb=short -q`
  - `cd backend && .venv/bin/ruff check . --fix`
  - `cd backend && .venv/bin/pytest`
  - note: `cd backend && .venv/bin/mypy .` is still blocked by pre-existing typing failures in `app/services/npc_stations/deltas.py`, `alembic/versions/20260409_0012_restore_esi_history_daily.py`, and `alembic/versions/20260409_0013_widen_esi_history_volume.py`

## 2026-04-15 - MARKET-DEMAND-UPSERT-REFRESH-REMOVAL
- Removed the post-commit `session.refresh(record)` from `MarketDemandResolutionService._upsert_row`, keeping the returned ORM row populated from the values assigned before commit.
- Added a regression test that asserts the returned `result.row` immediately exposes `buy_from_sell_period`, `demand_source`, and `computed_at` without an explicit refresh in the test.
- validation:
  - `cd backend && .venv/bin/pytest tests/services/test_market_demand.py -m "" -q`
  - `cd backend && .venv/bin/ruff check . --fix`
  - `cd backend && .venv/bin/mypy .`
  - `cd backend && .venv/bin/pytest`

## 2026-04-15 - ADAM-COVERAGE-PRECHECK-FOR-ESI-DEMAND
- Added an `adam_covered` fast-path flag to `MarketDemandResolutionService.upsert_for_location()` and `_upsert_npc_from_adam()` so NPC demand resolution can skip the per-key Adam `MAX(scanDate)` lookup entirely when sync already knows a key has no Adam coverage.
- Updated EVE Ref history sync to preload internal/EVE identity maps from the warmed SQLAlchemy identity map, batch query distinct Adam-covered `(location_id, type_id)` pairs once, and pass that coverage result into each ESI-demand refresh iteration.
- Added regression coverage proving `adam_covered=False` forces the existing ESI-live fallback path even when Adam raw rows exist in the database, with zero Adam lookup time recorded.
- acceptance criteria covered:
  - NPC upsert accepts and propagates an `adam_covered` flag into the Adam-backed resolution path.
  - Non-covered keys skip the Adam lookup block and fall through to ESI-live fallback with the `adam_not_covered` reason.
  - EVE Ref history sync preloads Adam-covered keys in one batch and passes per-key coverage into the refresh loop.
  - Integration coverage verifies the non-covered path uses `esi_live` and records `adam_lookup_s == 0.0`.
- validation:
  - `cd backend && .venv/bin/ruff check . --fix`
  - `cd backend && .venv/bin/mypy .`
  - `cd backend && .venv/bin/pytest`

## 2026-04-15 - ESI-DEMAND-BATCH-COMMITS
- Added an `autocommit` flag through `MarketDemandResolutionService` so resolved-demand upserts and deletes can be staged without changing the existing Adam refresh behavior, which still defaults to per-call commits.
- Updated `_sync_everef_history()` to disable per-key autocommit for ESI demand refreshes, commit every 50 keys, and issue one final flush after the loop so the ESI path stops doing one transaction per key.
- Added regression coverage proving `upsert_for_location(..., autocommit=False)` leaves the row uncommitted and invisible to a separate session until an explicit `session.commit()`.
- validation:
  - `cd backend && .venv/bin/ruff check . --fix`
  - `cd backend && .venv/bin/mypy .`
  - `cd backend && .venv/bin/pytest`
  - `cd backend && .venv/bin/pytest -m integration tests/services/test_market_demand.py -q`
  - `cd backend && .venv/bin/pytest -m integration tests/services/test_sync_service.py::test_everef_history_sync_first_run_succeeds_with_mocked_downloads tests/services/test_sync_service.py::test_everef_history_sync_limits_downloads_to_analysis_window_even_with_existing_state tests/services/test_sync_service.py::test_everef_history_sync_triggers_esi_demand_refresh_after_ingest tests/services/test_sync_service.py::test_everef_history_sync_preload_keeps_esi_demand_values_correct -q`
  - note: `cd backend && .venv/bin/mypy .` is still blocked by pre-existing typing failures in `app/services/npc_stations/deltas.py`, `alembic/versions/20260409_0012_restore_esi_history_daily.py`, and `alembic/versions/20260409_0013_widen_esi_history_volume.py`

## 2026-04-15 - EVEREF-HISTORY-SYNC-CRON-SCHEDULE
- Changed the worker registration for `everef_history_sync` from a drifting 24-hour interval to a fixed APScheduler cron schedule at 08:00 UTC.
- Documented the investigation result in the root task tracker: EveRef history is expected to be 1 day behind CCP, and the original 2-day gap was a transient scheduler-timing issue rather than an ingestion bug.
- Left ingestion logic untouched because `get_available_dates(...)` intentionally excludes today and matches EveRef's publish cadence.
- validation:
  - `cd backend && python -m pytest`

## 2026-04-17 - SYNC-DASHBOARD-STATUS-CARD-FRESHNESS
- Updated the sync dashboard so the top status cards overlay live progress and message fields from active job-history rows when `/sync/jobs` is fresher than `/sync/status`.
- Kept the merge scoped by `job_type -> card.key`, preferring the latest active run per job type and preserving non-active cards unchanged.
- Added a regression test that feeds stale status-card data plus a running job row and asserts the top card shows the running progress message instead of the stale healthy snapshot.
- validation:
  - `cd frontend && npm test -- --run src/pages/SyncPage.test.tsx`

## 2026-04-17 - SETTINGS-SEARCHABLE-MULTISELECTS
- Replaced the always-expanded checkbox lists for `Target Market Hubs` and `Source Regions` with collapsed searchable multi-select dropdowns on the settings page.
- Added a new `/api/settings/source-regions` endpoint so source-region options come from imported `regions` rows instead of the old five-region frontend constant, allowing selection of any imported region.
- Added frontend coverage for the collapsed selector flow and backend API coverage for the new source-region options endpoint.
- validation:
  - `cd frontend && npm test -- --run src/pages/SettingsPage.test.tsx`
  - `cd backend && ./.venv/bin/pytest -m integration tests/api/test_endpoints.py::test_get_settings tests/api/test_endpoints.py::test_get_source_region_options`

## 2026-04-21 - ADAM-VOLUME-HISTORY-MIGRATION-MODELS
- Added Alembic revision `20260421_0022` to create `adam_market_volume_history_raw`, `adam_market_volume_history_daily`, and `market_volume_period` with the planned uniqueness and lookup indexes.
- Registered `AdamMarketVolumeHistoryRaw`, `AdamMarketVolumeHistoryDaily`, and `MarketVolumePeriod` in the SQLAlchemy model set and exported them through `app.models`.
- Added metadata tests covering the new raw, daily, and period table definitions, including keys, indexes, and nullability for the period aggregates.
- validation:
  - `cd backend && .venv/bin/ruff check . --fix`
  - `cd backend && .venv/bin/mypy .`
  - `cd backend && .venv/bin/pytest`
  - `cd backend && .venv/bin/alembic upgrade head`
  - `cd backend && .venv/bin/python - <<'PY' ... inspector.get_table_names() ... PY`
  - note: `cd backend && .venv/bin/mypy .` is still blocked by pre-existing typing failures in `alembic/versions/20260409_0012_restore_esi_history_daily.py`, `alembic/versions/20260409_0013_widen_esi_history_volume.py`, and `alembic/versions/20260415_0019_drop_demand_yesterday_columns.py`
