# TASKS.md

Baseline reconstruction from `DESIGN_PROMPT.md`, `README.md`, and the current codebase.

Status legend:

- `DONE`: implemented and validated with reasonable confidence
- `PARTIAL`: some implementation exists, but acceptance criteria are incomplete
- `MISSING`: task intent is clear but implementation is absent
- `AMBIGUOUS`: implementation/spec alignment cannot be established confidently

## Priority Order

Execution priority from this point forward:

1. `T10` Live Ingestion And Opportunity Computation
2. `T05` Trade Analysis API And Data Flow
3. `T11` Structure Snapshots And Demand Inference
4. `T07` Characters, Auth, And Multi-User Support
5. `T06` Sync Operations Dashboard
6. `T04` Foundation Data Bootstrap
7. `T09` Testing Baseline
8. `T02` Core Scaffold And Runtime
9. `T03` Core Trading Formulas
10. `T08` Frontend Shells And Routing
11. `T01` Workflow Adoption Artifacts

Priority rationale:

- `T10` is first because it unlocks real computed trade data, which is the core product behavior.
- `T05` follows because the trade API and UI should consume the real computed data as soon as it exists.
- `T11` is next because structure-local demand is the other major data pipeline still missing.
- `T07` and `T06` come after the core market-data path because they depend on or benefit from real sync/computation behavior.
- `T04` remains important, but its current seeded bootstrap is sufficient to unblock product work, so deeper SDE/import polish is lower priority than real trade computation.
- `T09` continues alongside work, but its biggest missing areas should follow the highest-priority product tasks rather than lead them.
- `T02`, `T03`, `T08`, and `T01` are already in a strong enough state and do not currently block forward progress.

## T01 - Workflow Adoption Artifacts

- Status: `DONE`
- Objective: establish the Planner -> Developer -> Tester -> Reviewer workflow and repository artifacts for future work.
- Dependencies: none
- Acceptance criteria:
  - `AGENTS.md` exists with role definitions, one-task-at-a-time rule, definition of done, quality gates, devlog requirement, and legacy code rule.
  - `TASKS.md` exists with structured task packets and conservative statuses.
  - `DEVLOG.md` exists with imported entries for pre-adoption work.
  - `DEFECTS.md` exists if confirmed defects are found.
  - `CLARIFICATIONS.md` exists only if spec ambiguity needs a recorded decision.
- Likely files/modules:
  - `AGENTS.md`
  - `TASKS.md`
  - `DEVLOG.md`
  - `DEFECTS.md`
  - `CLARIFICATIONS.md`
- Out of scope:
  - implementing missing product features
- Test hints:
  - manual audit of artifact completeness
- Implementation mapping:
  - `AGENTS.md`, `TASKS.md`, and `DEVLOG.md` were created during the baseline audit pass.
- Mismatches:
  - Governance process was not represented in the repo before this audit; the baseline pass now establishes it.

## T02 - Core Scaffold And Runtime

- Status: `DONE`
- Objective: provide the initial modular-monolith scaffold with FastAPI, React, Docker, SQLAlchemy, Alembic, and worker wiring.
- Dependencies: none
- Acceptance criteria:
  - backend app boots and mounts API routes
  - frontend app routes exist
  - Docker Compose stack exists for frontend/backend/postgres/redis/worker
  - database metadata and migration scaffolding exist
- Likely files/modules:
  - `backend/app/main.py`
  - `backend/app/db/session.py`
  - `backend/alembic/`
  - `frontend/src/app/App.tsx`
  - `frontend/src/routes/AppRoutes.tsx`
  - `docker-compose.yml`
- Out of scope:
  - full live integrations
- Test hints:
  - backend `pytest`
  - Docker smoke checks
- Implementation mapping:
  - Scaffold exists across backend/frontend/docker and boots successfully.
- Mismatches:
  - none significant for scaffold-level acceptance

## T03 - Core Trading Formulas

- Status: `DONE`
- Objective: implement explicit domain formulas for risk, warning, profit, ROI, DOS, and purchase units.
- Dependencies: T02
- Acceptance criteria:
  - formulas exist in a dedicated rules/domain layer
  - unit tests cover positive/negative risk, threshold behavior, profit, ROI, DOS, and purchase units
- Likely files/modules:
  - `backend/app/domain/rules.py`
  - `backend/tests/domain/test_rules.py`
- Out of scope:
  - full opportunity pipeline
- Test hints:
  - backend `pytest`
- Implementation mapping:
  - Domain formulas are implemented and tested directly.
- Mismatches:
  - coverage is good for the baseline formulas, but not exhaustive across all future business scenarios

## T04 - Foundation Data Bootstrap

- Status: `PARTIAL`
- Objective: load or seed the core reference data required to bootstrap the app.
- Dependencies: T02
- Acceptance criteria:
  - regions, systems, stations, locations, tracked structures, and default settings are persisted
  - bootstrap path is idempotent
  - foundation sync can be invoked operationally
  - solution aligns with eventual SDE/ESI-backed refresh path
- Likely files/modules:
  - `backend/app/services/sync/foundation_data.py`
  - `backend/app/db/session.py`
  - `backend/app/repositories/seed_data.py`
- Out of scope:
  - full SDE import implementation
  - market groups refresh
- Test hints:
  - idempotence test
  - route test for manual foundation sync
- Implementation mapping:
  - Small reference seed set is persisted and tested.
- Mismatches:
  - uses hardcoded seed data instead of real SDE import or ESI refresh behavior

## T05 - Trade Analysis API And Data Flow

- Status: `PARTIAL`
- Objective: serve target/source/opportunity data for the main trade workflow.
- Dependencies: T02, T03, T04
- Acceptance criteria:
  - endpoints exist for targets, sources, source summaries, item rows, and item detail
  - responses use typed schemas
  - trade page can query the API and render the hierarchy
  - data should come mostly from query-ready tables rather than demo rows
- Likely files/modules:
  - `backend/app/repositories/trade_repository.py`
  - `backend/app/api/routes/targets.py`
  - `backend/app/api/routes/opportunities.py`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/hooks/useTradeData.ts`
- Out of scope:
  - full live ingestion and compute pipeline
- Test hints:
  - API integration tests
  - frontend trade page render tests
- Implementation mapping:
  - API surface exists and the trade page renders data from it.
- Mismatches:
  - source summaries, items, and detail are still demo/seeded responses instead of precomputed DB-backed opportunity data
  - filter/sort/search behavior is mostly unimplemented

### T05A - Trade Repository Reads Computed Opportunity Tables

- Status: `DONE`
- Objective: make the trade repository consume persisted `opportunity_source_summaries` and `opportunity_items` when they exist, while preserving the current placeholder fallback until the compute pipeline is complete.
- Dependencies:
  - T10
- Acceptance criteria:
  - source summary reads prefer `opportunity_source_summaries` rows when present
  - item reads prefer `opportunity_items` rows when present
  - safe placeholder fallback remains when computed rows are absent
  - trade refresh uses computed timestamps when available
  - deterministic tests cover computed-read behavior, fallback behavior, and refresh timestamp handling
- Likely files/modules:
  - `backend/app/repositories/trade_repository.py`
  - `backend/tests/services/test_trade_repository.py`
- Out of scope:
  - generating opportunity rows
  - item-detail order-book realism
  - frontend filter/sort/search completion
- Test hints:
  - seed in-memory `opportunity_source_summaries` and `opportunity_items`
  - verify fallback still returns the placeholder-backed rows
  - verify refresh timestamps normalize to UTC-aware values
- Implementation mapping:
  - the trade repository now reads computed opportunity tables when matching rows exist and falls back safely otherwise
  - refresh timestamps are derived from computed rows instead of always using current time when data is present
- Mismatches:
  - `get_item_detail()` still uses placeholder order-book rows even when metrics are computed
  - the overall trade API remains partial until the opportunity generation pipeline is real

### T05B - Precise Item Detail Resolution

- Status: `DONE`
- Objective: make `get_item_detail()` resolve the selected item deterministically from persisted opportunity rows and preserve public item identifiers in the response.
- Dependencies:
  - T05A
- Acceptance criteria:
  - `get_item_detail(target_location_id, source_location_id, type_id, period_days)` returns metrics for the requested public EVE `type_id` when a computed row exists
  - fallback detail remains internally consistent for the requested public `type_id` when no computed row exists
  - deterministic tests cover both computed and fallback detail resolution
  - no unrelated frontend changes are required
- Likely files/modules:
  - `backend/app/repositories/trade_repository.py`
  - `backend/tests/services/test_trade_repository.py`
- Out of scope:
  - live order-book ingestion
  - frontend detail-panel polish
  - advanced item-detail analytics
- Test hints:
  - seed a computed `OpportunityItem` row whose internal FK id differs from the public `Item.type_id`
  - verify both `detail.type_id` and `detail.metrics.type_id` preserve the public value
  - verify fallback detail returns the requested item name and type id
- Implementation mapping:
  - item detail now resolves computed rows by public `Item.type_id` and keeps response identifiers on the public EVE item id
  - fallback detail construction is tied to the requested item rather than reusing the first placeholder row
- Mismatches:
  - order-book panels remain placeholder-derived even when the metrics row is computed

### T05C - Trade Page Controls And Client-Side Filtering

- Status: `DONE`
- Objective: wire the existing trade-page controls into the query flow and make the item table respond deterministically to user-entered search, threshold, and sort inputs.
- Dependencies:
  - T05A
  - T05B
- Acceptance criteria:
  - target-market and analysis-period controls drive the source-summary and item queries
  - item search filters rows by case-insensitive item-name substring
  - min ROI and warning-threshold controls filter item rows deterministically from loaded query results
  - item-table sorting is user-driven and deterministic for at least the exposed sortable columns
  - frontend tests cover default filtering, control-driven requeries, source reset behavior, and sortable row rendering
- Likely files/modules:
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/components/trade/TradeControls.tsx`
  - `frontend/src/components/trade/ItemOpportunityTable.tsx`
  - `frontend/src/hooks/useTradeData.ts`
  - `frontend/src/api/trade.ts`
  - `frontend/src/pages/TradePage.test.tsx`
- Out of scope:
  - backend-side opportunity filtering APIs
  - source-type, security-band, and demand-source filters
  - item-detail panel interactions
- Test hints:
  - mock hook results across multiple targets and periods
  - verify default ROI/risk thresholds exclude weaker rows
  - verify a target switch resets the selected source when the prior source is unavailable
  - verify a sortable-column click changes rendered row order deterministically
- Implementation mapping:
  - the trade page now owns controlled target, period, search, ROI, warning-threshold, and sort state
  - the source-summary and item queries now include the selected `period_days`
  - client-side filtering/sorting is applied to the loaded item rows before rendering
- Mismatches:
  - server-side filtering and additional trade filters remain unimplemented
  - the item-detail panel is still not driven from row selection

## T06 - Sync Operations Dashboard

- Status: `PARTIAL`
- Objective: provide operational visibility and manual sync actions on `/sync`.
- Dependencies: T02, T04
- Acceptance criteria:
  - status cards render sync health
  - manual actions exist for major sync operations
  - job history table exists
  - fallback diagnostics exist
  - worker and rate-limit status are grounded in actual system state
- Likely files/modules:
  - `backend/app/services/sync/service.py`
  - `backend/app/api/routes/sync.py`
  - `frontend/src/pages/SyncPage.tsx`
  - `frontend/src/components/sync/`
- Out of scope:
  - Phase 4 telemetry polish
- Test hints:
  - sync route tests
  - frontend sync page render tests
- Implementation mapping:
  - Sync page is API-backed and supports a real foundation seed action.
- Mismatches:
  - most status cards and job history rows are synthetic
  - no persistent `sync_job_runs` workflow or ESI rate-limit telemetry yet

### T06A - Persisted Sync Job History

- Status: `DONE`
- Objective: replace synthetic sync job history with persisted `sync_job_runs` rows for manual sync execution paths.
- Dependencies:
  - T02
  - T04
  - T10B
  - T10C
- Acceptance criteria:
  - `trigger_job()` persists a `sync_job_runs` row for real manual jobs
  - successful synchronous jobs are marked complete with `finished_at` and `duration_ms`
  - `list_jobs()` returns persisted rows newest first
  - deterministic backend tests cover job creation and listing for at least one real manual job path
- Likely files/modules:
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_sync_service.py`
- Out of scope:
  - richer worker-health telemetry
  - ESI rate-limit monitoring
  - frontend dashboard redesign
- Test hints:
  - trigger a real manual sync path such as `foundation_seed_sync`
  - verify stored job ordering and completion fields
  - run full backend quality gates because this packet touches the operational service layer
- Implementation mapping:
  - sync jobs are now persisted in `sync_job_runs` and returned by `list_jobs()`
  - manual foundation, Adam4EVE, and ESI history syncs all flow through the persisted job-run path
- Mismatches:
  - sync status cards and fallback diagnostics are still mostly synthetic
  - background scheduler-triggered runs are not yet recorded through the same persistence path

### T06B - History-Backed Sync Status Cards

- Status: `DONE`
- Objective: replace hardcoded sync status-card timestamps with values derived from persisted `sync_job_runs` for the implemented manual job types.
- Dependencies:
  - T06A
- Acceptance criteria:
  - `get_status()` derives `last_successful_sync` and `recent_error_count` from persisted `sync_job_runs` for implemented job types
  - cards remain stable when no job history exists
  - deterministic backend tests cover both history-backed and no-history cases
  - scope remains backend-only
- Likely files/modules:
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_sync_service.py`
- Out of scope:
  - frontend sync dashboard redesign
  - worker health telemetry
  - ESI rate-limit reporting
- Test hints:
  - seed successful and failed `sync_job_runs` rows directly
  - verify UTC-normalized timestamps and derived error counts
  - verify idle defaults when no history exists
- Implementation mapping:
  - sync status cards now derive key fields from persisted job history for the implemented sync types
  - default idle cards remain in place for scopes that have not run yet
- Mismatches:
  - worker health and fallback diagnostics are still synthetic
  - next scheduled sync is still not derived from a real scheduler state

## T07 - Characters, Auth, And Multi-User Support

- Status: `PARTIAL`
- Objective: support EVE SSO users, linked characters, and per-user data overlays.
- Dependencies: T02
- Acceptance criteria:
  - auth routes exist and are shaped for EVE SSO
  - character endpoints exist for list/detail/sync/structures
  - tokens and sync state are represented in the data model
  - first-character user creation and linking flow works
  - structure discovery from assets/orders is implemented
- Likely files/modules:
  - `backend/app/api/routes/auth.py`
  - `backend/app/api/routes/characters.py`
  - `backend/app/services/characters/service.py`
  - `backend/app/models/all_models.py`
- Out of scope:
  - advanced skills-derived fee logic
- Test hints:
  - mocked auth callback tests
  - mocked character discovery tests
- Implementation mapping:
  - route shapes and models exist, but the behavior is still mostly stubbed.
- Mismatches:
  - token exchange, persistence, user linking, and structure discovery are not implemented end to end

## T08 - Frontend Shells And Routing

- Status: `DONE`
- Objective: provide the page shells and route skeleton for `/trade`, `/sync`, `/characters`, and `/settings`.
- Dependencies: T02
- Acceptance criteria:
  - routes exist for all primary pages
  - page shells render and are styled
  - smoke tests cover the main route shells
- Likely files/modules:
  - `frontend/src/routes/AppRoutes.tsx`
  - `frontend/src/pages/*.tsx`
  - `frontend/src/styles/global.css`
- Out of scope:
  - feature-complete workflows on every page
- Test hints:
  - frontend Vitest route/page render tests
- Implementation mapping:
  - All page routes exist with basic shells and tests.
- Mismatches:
  - characters/settings remain mostly shell-level

## T09 - Testing Baseline

- Status: `PARTIAL`
- Objective: establish meaningful backend and frontend test coverage from the start.
- Dependencies: T02, T03
- Acceptance criteria:
  - backend formula tests exist
  - key API route tests exist
  - service tests exist for early logic
  - frontend render tests exist
  - repo quality gates are known and runnable where available
- Likely files/modules:
  - `backend/tests/`
  - `frontend/src/**/*.test.tsx`
  - `backend/pyproject.toml`
  - `frontend/package.json`
- Out of scope:
  - comprehensive end-to-end coverage for all future integrations
- Test hints:
  - backend `pytest`
  - frontend `docker compose run --rm frontend npm test`
- Implementation mapping:
  - backend and frontend baseline tests exist and currently pass.
- Mismatches:
  - ingestion tests, ESI auth/setup tests, and deeper UI behavior tests are still missing

## T10 - Live Ingestion And Opportunity Computation

- Status: `PARTIAL`
- Objective: ingest Adam4EVE and ESI market data, compute periods/demand, and populate query-ready opportunity tables.
- Dependencies: T03, T04
- Acceptance criteria:
  - Adam4EVE NPC demand ingestion persists internal data
  - ESI regional history ingestion persists internal data
  - period price rows and resolved demand rows are computed
  - `opportunity_items` and `opportunity_source_summaries` are derived from stored data
  - trade API reads from computed tables rather than demo rows
- Likely files/modules:
  - `backend/app/services/adam4eve/client.py`
  - `backend/app/services/esi/client.py`
  - `backend/app/services/pricing/`
  - `backend/app/services/opportunities/`
  - `backend/app/workers/tasks/sync_tasks.py`
- Out of scope:
  - structure-local demand inference
- Test hints:
  - ingestion mapping tests
  - aggregation tests against persisted fixtures
- Implementation mapping:
  - derived-data slices now exist for persisted regional history, Adam4EVE NPC demand, resolved demand, and opportunity generation
  - live clients are still placeholders and the sync-driven bulk rebuild path is still incomplete
- Mismatches:
  - current trade outputs still rely on fallback rows unless opportunity rebuilds are run

### T10A - Market Price Period Computation

- Status: `DONE`
- Objective: compute `market_price_period` rows from persisted `esi_history_daily` rows so later opportunity logic can consume query-ready price period data.
- Dependencies:
  - T03
  - T04
- Acceptance criteria:
  - a service reads stored `esi_history_daily` rows for a `(location_id, type_id, period_days)` scope and upserts a `market_price_period` row
  - `risk_pct` uses the spec formula
  - `warning_flag` follows the configured threshold rule
  - empty or insufficient history is handled deterministically
  - logic is covered by small deterministic tests
- Likely files/modules:
  - `backend/app/services/pricing/market_price_periods.py`
  - `backend/tests/services/test_market_price_periods.py`
- Out of scope:
  - Adam4EVE ingestion
  - live ESI HTTP integration
  - opportunity row generation
  - frontend changes
- Test hints:
  - use in-memory SQLite fixtures
  - verify exact `current_price`, `period_avg_price`, `price_min`, `price_max`, `risk_pct`, and `warning_flag`
  - include empty-history and threshold-boundary tests
- Implementation mapping:
  - implemented in a dedicated pricing service and validated with deterministic service tests plus full backend `pytest`
- Mismatches:
  - computation is based on persisted regional history only; current live order-book pricing is still not wired in

### T10B - Persisted ESI Regional History Ingestion

- Status: `DONE`
- Objective: ingest normalized ESI regional history payloads into `esi_history_daily` so the existing pricing pipeline can compute `market_price_period` rows from stored data.
- Dependencies:
  - T03
  - T04
  - T10A
- Acceptance criteria:
  - a backend service accepts a batch of regional history records and persists them into `esi_history_daily`
  - ingestion is idempotent on the repo's unique history key
  - stored rows contain the fields needed by `T10A`
  - a sync entrypoint can invoke the ingestion service for one region batch
  - deterministic tests cover mapping, upsert/idempotence, and a round-trip into `T10A`
- Likely files/modules:
  - `backend/app/services/esi/history_ingestion.py`
  - `backend/app/services/esi/client.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
- Out of scope:
  - live authenticated ESI HTTP plumbing
  - market order ingestion
  - opportunity row generation
  - frontend changes
- Test hints:
  - use in-memory SQLite fixtures
  - verify exact persisted values and duplicate update behavior
  - assert the sync path feeds `T10A` successfully
- Implementation mapping:
  - regional history ingestion is implemented as a dedicated service with internal region/item resolution and update-on-conflict behavior
  - `esi_history_sync` now exercises the ingestion path through the sync service with the mock ESI client
- Mismatches:
  - the ESI client remains mock-backed, so the ingestion path is validated structurally rather than against live CCP responses

### T10C - Adam4EVE NPC Demand Ingestion

- Status: `DONE`
- Objective: ingest Adam4EVE NPC demand into `adam_npc_demand_daily` so NPC demand can later be resolved from persisted data instead of placeholders.
- Dependencies:
  - T04
  - T10B
- Acceptance criteria:
  - a backend service accepts Adam4EVE NPC demand batches and persists them into `adam_npc_demand_daily`
  - ingestion is idempotent on the repo's daily NPC demand uniqueness key
  - stored rows preserve the demand-day values and source metadata needed by later demand resolution
  - a sync entrypoint can invoke the Adam4EVE ingestion service
  - deterministic tests cover mapping, update behavior, and sync-path persistence
- Likely files/modules:
  - `backend/app/services/adam4eve/ingestion.py`
  - `backend/app/services/adam4eve/client.py`
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_adam4eve_ingestion.py`
- Out of scope:
  - live Adam4EVE HTTP integration
  - resolved demand computation
  - opportunity row generation
  - frontend changes
- Test hints:
  - verify internal location and item FK resolution
  - verify duplicate daily rows update instead of inserting a second row
  - assert the sync path persists rows for NPC locations
- Implementation mapping:
  - Adam4EVE ingestion is implemented as a dedicated service with internal location/item resolution and update-on-conflict behavior
  - `adam4eve_sync` now persists NPC demand rows through the sync service with the mock Adam4EVE client
- Mismatches:
  - the Adam4EVE client remains mock-backed, so the ingestion path is validated structurally rather than against live API payloads

### T10D - Persisted Market Demand Resolution

- Status: `DONE`
- Objective: compute `market_demand_resolved` rows from persisted raw demand data so later opportunity generation can consume query-ready demand metrics.
- Dependencies:
  - T10C
  - T11 for full structure-local behavior
- Acceptance criteria:
  - a backend service upserts `market_demand_resolved` rows for NPC targets from persisted Adam4EVE daily demand
  - the service uses available daily rows deterministically when the full requested period is not present
  - stale computed rows are removed when no NPC demand history exists
  - structure targets are marked as fallback until the structure-local pipeline exists
  - deterministic tests cover NPC resolution, short-history behavior, stale-row cleanup, and structure fallback behavior
- Likely files/modules:
  - `backend/app/services/demand/market_demand.py`
  - `backend/tests/services/test_market_demand.py`
- Out of scope:
  - full structure-local demand inference
  - opportunity row generation
  - frontend changes
- Test hints:
  - verify exact averaged demand-day values for NPC targets
  - verify stale-row cleanup behavior
  - verify structure targets resolve to `regional_fallback` with zero confidence for now
- Implementation mapping:
  - market demand resolution is implemented as a dedicated service that writes query-ready rows to `market_demand_resolved`
  - NPC targets resolve from persisted Adam4EVE daily demand while structure targets are explicitly parked on fallback until T11 lands
- Mismatches:
  - structure fallback currently uses a neutral zero-demand placeholder rather than real CCP regional fallback data

### T10E - Persisted Opportunity Generation

- Status: `DONE`
- Objective: compute and persist `opportunity_items` and `opportunity_source_summaries` from the precomputed price and demand tables.
- Dependencies:
  - T10A
  - T10D
  - T05A
- Acceptance criteria:
  - a backend service generates `opportunity_items` for a target/source/type/period scope using the existing domain formulas
  - reruns replace prior rows for the same opportunity key instead of duplicating them
  - source summaries are aggregated and persisted from the generated item rows
  - deterministic tests cover item generation, summary aggregation, and rerun behavior
  - the generation path reads from precomputed tables rather than placeholder API rows
- Likely files/modules:
  - `backend/app/services/opportunities/generation.py`
  - `backend/app/services/opportunities/aggregator.py`
  - `backend/tests/services/test_opportunity_generation.py`
- Out of scope:
  - live order-book liquidity ingestion
  - structure-local demand inference
  - frontend trade filter/sort/search completion
- Test hints:
  - seed `market_price_period` and `market_demand_resolved` rows directly in SQLite fixtures
  - verify exact generated profit, ROI, capital, and warning fields
  - verify reruns replace prior persisted opportunity rows
- Implementation mapping:
  - opportunity generation is now implemented as a dedicated service that persists item and source-summary rows from computed demand/price inputs
  - the service uses the existing domain formulas and summary aggregator instead of API placeholder rows
- Mismatches:
  - source liquidity and target supply are still zero-default placeholders until live order/snapshot ingestion exists
  - no sync/service orchestration is invoking the generation path in bulk yet

### T10F - Sync-Driven Opportunity Rebuild

- Status: `DONE`
- Objective: make the manual `opportunity_rebuild` sync path invoke the persisted opportunity generation pipeline over available computed scopes.
- Dependencies:
  - T06A
  - T10E
- Acceptance criteria:
  - `SyncService.trigger_job("opportunity_rebuild")` runs the persisted opportunity generation path using computed price and demand rows
  - the rebuild job persists meaningful `sync_job_runs` metadata including `records_processed` and message text
  - deterministic backend tests cover the manual rebuild path creating opportunity rows and a persisted sync job record
  - the rebuild path does not rely on placeholder API rows
- Likely files/modules:
  - `backend/app/services/sync/service.py`
  - `backend/app/services/opportunities/generation.py`
  - `backend/tests/services/test_sync_service.py`
- Out of scope:
  - scheduler-driven rebuild execution
  - live market-order liquidity ingestion
  - frontend dashboard polish
- Test hints:
  - seed only `market_price_period` and `market_demand_resolved` rows
  - verify the rebuild creates both opportunity items and source summaries
  - verify the persisted sync job row records meaningful counts and status
- Implementation mapping:
  - `opportunity_rebuild` now scans persisted demand scopes, finds eligible source price scopes, and invokes the generation service
  - the rebuild path writes real `sync_job_runs` metadata and produces persisted opportunity rows
- Mismatches:
  - rebuild scope selection is currently simple and based only on available computed tables
  - the underlying generated opportunity rows still use zero-default liquidity placeholders until live order data exists

## T11 - Structure Snapshots And Demand Inference

- Status: `MISSING`
- Objective: persist periodic structure snapshots, compute deltas, infer local demand, and apply fallback logic.
- Dependencies: T04, T07, T10
- Acceptance criteria:
  - structure order snapshots are ingested and stored
  - deltas between snapshots are computed and persisted
  - `demand_min`, `demand_max`, and `demand_chosen` are produced
  - confidence gating selects local vs fallback demand
  - tracked structures can participate in opportunity computation
- Likely files/modules:
  - `backend/app/services/structures/inference.py`
  - `backend/app/services/demand/`
  - `backend/app/workers/tasks/sync_tasks.py`
- Out of scope:
  - broader structure management UX polish
- Test hints:
  - snapshot ingestion tests
  - confidence threshold tests
- Implementation mapping:
  - only a delta helper exists; the full snapshot/inference pipeline is not present.
- Mismatches:
  - no periodic snapshot job or persisted local demand inference exists

### T11A - Structure Snapshot Persistence And Deltas

- Status: `DONE`
- Objective: persist structure market snapshots and compute/persist basic order deltas between snapshots.
- Dependencies:
  - T04
- Acceptance criteria:
  - one structure snapshot batch with orders can be persisted into `structure_snapshots` and `structure_snapshot_orders`
  - two snapshots for the same structure can be diffed into persisted `structure_order_deltas`
  - basic inferred trade side and units follow the existing reduction rules for sell and buy orders
  - deterministic tests cover snapshot persistence and delta computation
  - no live HTTP integration is required yet
- Likely files/modules:
  - `backend/app/services/structures/snapshots.py`
  - `backend/app/services/structures/inference.py`
  - `backend/tests/services/test_structure_snapshots.py`
- Out of scope:
  - live structure polling
  - demand-period aggregation
  - fallback selection logic
- Test hints:
  - persist two snapshots for the same structure with overlapping and disappeared orders
  - verify `buy_from_sell`, `sell_to_buy`, and disappeared-order persistence
  - verify timestamps remain UTC-aware at the service boundary
- Implementation mapping:
  - a dedicated snapshot service now persists snapshots/orders and computes persisted deltas between snapshot pairs
  - the service reuses the existing inference helper for matching-order volume reductions
- Mismatches:
  - disappeared orders are still treated conservatively with no inferred trade side/units
  - no periodic sync orchestration exists for structure snapshots yet

### T11B - Structure Demand Period Aggregation

- Status: `DONE`
- Objective: aggregate persisted structure order deltas into `structure_demand_period` rows that can later feed local structure demand resolution.
- Dependencies:
  - T11A
- Acceptance criteria:
  - a service reads persisted `structure_order_deltas` and upserts `structure_demand_period` rows
  - `demand_min`, `demand_max`, and `demand_chosen` are computed deterministically from inferred trade units over the selected period
  - `coverage_pct` and `confidence_score` are persisted using a simple deterministic MVP rule
  - reruns update the same `(structure_id, type_id, period_days)` row instead of duplicating it
  - deterministic tests cover aggregation and rerun behavior
- Likely files/modules:
  - `backend/app/services/structures/demand_periods.py`
  - `backend/tests/services/test_structure_demand_periods.py`
- Out of scope:
  - demand resolution into `market_demand_resolved`
  - live structure polling
  - advanced confidence heuristics
- Test hints:
  - seed multiple persisted deltas, including disappeared orders
  - verify the exact aggregated demand values over a fixed period window
  - verify reruns update the existing row
- Implementation mapping:
  - structure demand periods are now computed from persisted order deltas and written into `structure_demand_period`
  - the MVP confidence rule is deterministic and tied to coverage plus recency
- Mismatches:
  - confidence is still a simple heuristic rather than the full long-window gating described in the product spec

### T11C - Structure-Local Demand Resolution

- Status: `DONE`
- Objective: allow structure targets to resolve local demand from persisted `structure_demand_period` rows when confidence is sufficient.
- Dependencies:
  - T10D
  - T11B
- Acceptance criteria:
  - `MarketDemandResolutionService` uses `structure_demand_period` for structure locations when coverage/confidence thresholds are met
  - otherwise structure locations still persist `regional_fallback`
  - NPC demand resolution remains unchanged
  - deterministic tests cover sufficient-confidence local demand, insufficient-confidence fallback, and NPC no-regression behavior
- Likely files/modules:
  - `backend/app/services/demand/market_demand.py`
  - `backend/tests/services/test_market_demand.py`
- Out of scope:
  - live CCP regional fallback demand
  - structure polling orchestration
  - advanced confidence heuristics
- Test hints:
  - seed `StructureDemandPeriod` rows with both sufficient and insufficient confidence inputs
  - verify the resolved demand source and value written to `market_demand_resolved`
  - keep existing NPC demand tests as regression coverage
- Implementation mapping:
  - market demand resolution now consults persisted local structure demand periods before falling back
  - structure-local demand is gated by explicit coverage/confidence thresholds in the service layer
- Mismatches:
  - fallback for structures still uses the temporary zero-demand regional fallback placeholder rather than real CCP-derived fallback demand
