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
