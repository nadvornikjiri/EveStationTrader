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
