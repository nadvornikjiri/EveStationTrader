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

- Status: `DONE`
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
  - the foundation bootstrap persists the seeded regions, systems, stations, locations, tracked structures, items, and default settings required by the app
  - bootstrap remains idempotent and is exposed through the operational sync flow
  - the provider abstraction plus file-backed snapshot source now align the persistence path with future SDE/ESI-backed refresh implementations without rewriting the bootstrap service
- Mismatches:
  - live CCP-backed reference-data refresh remains intentionally out of scope for this bootstrap packet

### T04A - Foundation Data Source Abstraction

- Status: `DONE`
- Objective: make foundation bootstrap read seed inputs through a provider abstraction instead of directly from hardcoded module constants, while preserving current behavior.
- Dependencies:
  - T02
- Acceptance criteria:
  - `FoundationDataService.bootstrap()` reads regions, systems, stations, items, tracked-structure metadata, and defaults through a single source interface
  - the default source still produces the current curated seed set without behavioral regression
  - bootstrap remains idempotent
  - the source boundary is shaped so a later SDE-backed implementation can plug in without rewriting bootstrap persistence logic
  - deterministic backend tests cover bootstrap via the default source, idempotence, and a small alternate/mock source proving the abstraction works
- Likely files/modules:
  - `backend/app/services/sync/foundation_data.py`
  - `backend/app/repositories/seed_data.py`
  - `backend/tests/services/test_foundation_data.py`
- Out of scope:
  - full CCP SDE import
  - ESI-backed foundation refresh
  - market group refresh
  - frontend changes
- Test hints:
  - keep the provider responsible only for normalized seed data, not persistence behavior
  - preserve the existing persisted shape exactly
  - use a tiny mock source to prove the abstraction boundary is real
- Implementation mapping:
  - `FoundationDataService` now reads all seed inputs from a provider abstraction, the curated default source preserves the existing bootstrap data set, and deterministic tests cover idempotence plus an alternate mock source.
- Mismatches:
  - this packet improves the bootstrap architecture but does not yet add a live SDE or ESI-backed source

### T04B - File-Backed Foundation Snapshot Source

- Status: `DONE`
- Objective: add a file-backed foundation seed source that loads normalized snapshot data without changing bootstrap persistence behavior.
- Dependencies:
  - T04A
- Acceptance criteria:
  - a file-backed `FoundationSeedSource` exists and supplies regions, systems, stations, items, structure locations, tracked structures, and default settings in the normalized shape consumed by `FoundationDataService`
  - `FoundationDataService.bootstrap()` works unchanged against the file-backed source
  - bootstrap remains idempotent when run repeatedly against the file-backed source
  - deterministic backend tests cover loading a minimal valid snapshot, successful bootstrap through the file-backed source, idempotent rerun behavior, and malformed or incomplete snapshot failures
  - the curated in-code source remains available as the safe default unless a file-backed source is explicitly selected
- Likely files/modules:
  - `backend/app/repositories/seed_data.py`
  - `backend/app/services/sync/foundation_data.py`
  - `backend/tests/services/test_foundation_data.py`
- Out of scope:
  - live CCP SDE download
  - live ESI universe refresh
  - market group import
  - schema changes
  - frontend changes
- Test hints:
  - keep the snapshot format minimal and normalized so it mirrors the seed dataclasses closely
  - fail deterministically when referenced dependencies like region/system ids are missing
  - preserve the current curated source as the default bootstrap path
- Implementation mapping:
  - `FileFoundationSeedSource` now loads a normalized JSON snapshot into the existing foundation seed dataclasses and validates duplicate IDs, missing references, and unsupported tracking tiers before bootstrap runs.
  - `FoundationDataService` works unchanged against the file-backed source because the persistence path still consumes the shared seed interface.
  - deterministic backend tests cover minimal snapshot loading, file-backed bootstrap/idempotence, malformed snapshots, invalid tracking tiers, duplicate IDs, and the curated default-source behavior.
- Mismatches:
  - this packet adds a checked-in snapshot source for deterministic bootstrap input, but it does not yet fetch or refresh live CCP SDE/ESI foundation data

## T05 - Trade Analysis API And Data Flow

- Status: `DONE`
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
  - API surface exists and the trade page renders targets, computed source summaries, item rows, and item detail from it.
- Mismatches:
  - item-detail order books remain placeholder-derived until live order ingestion is implemented

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

### T05D - Trade Page Item Detail Selection

- Status: `DONE`
- Objective: connect the existing item-detail API to the trade page so the lower-right execution context panel reflects the currently selected opportunity row.
- Dependencies:
  - T05B
  - T05C
- Acceptance criteria:
  - the trade page selects a deterministic default item row from the filtered/sorted result set
  - changing the selected item row requeries item detail for the selected `(target, source, type, period)` scope
  - the detail panel renders API-backed order rows and key metrics for the selected item
  - selection resets safely when target/source/filter changes remove the previously selected item
  - frontend tests cover default detail loading, row-driven detail changes, and selection reset behavior
- Likely files/modules:
  - `frontend/src/api/trade.ts`
  - `frontend/src/hooks/useTradeData.ts`
  - `frontend/src/components/trade/ItemOpportunityTable.tsx`
  - `frontend/src/components/trade/ItemDetailPanel.tsx`
  - `frontend/src/pages/TradePage.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
- Out of scope:
  - live order-book realism beyond the existing detail endpoint payload
  - backend-side item-detail analytics changes
  - keyboard-navigation polish for row selection
- Test hints:
  - mock item-detail responses for multiple items
  - verify the default selected row loads detail on first render
  - verify selecting a different row updates the rendered detail panel
  - verify target/source changes reset detail selection to an available item
- Implementation mapping:
  - the trade page now tracks selected item state and queries the item-detail endpoint for the active row
  - the item table exposes deterministic row selection and the detail panel renders API-backed order rows plus summary metrics
- Mismatches:
  - the item-detail endpoint still returns placeholder order stacks rather than live CCP order-book data

### T05E - Remove Placeholder Opportunity List Fallbacks

- Status: `DONE`
- Objective: stop serving placeholder source-summary and item-list rows once the computed opportunity pipeline is available, while keeping empty trade states deterministic in the UI.
- Dependencies:
  - T05A
  - T05D
  - T10
- Acceptance criteria:
  - source-summary reads return persisted `opportunity_source_summaries` rows only and do not synthesize demo rows when none exist
  - item-list reads return persisted `opportunity_items` rows only and do not synthesize demo rows when none exist
  - item detail remains stable for direct lookups without computed rows, using explicit zero/empty-state fallback values instead of misleading market metrics
  - the trade page renders deterministic empty states when a target/source has no computed opportunities
  - deterministic backend and frontend tests cover the empty-list behavior and empty-state rendering
- Likely files/modules:
  - `backend/app/repositories/trade_repository.py`
  - `backend/tests/services/test_trade_repository.py`
  - `backend/tests/api/test_endpoints.py`
  - `frontend/src/components/trade/SourceSummaryTable.tsx`
  - `frontend/src/components/trade/ItemOpportunityTable.tsx`
  - `frontend/src/pages/TradePage.test.tsx`
- Out of scope:
  - live market-order ingestion
  - source discovery endpoint redesign
  - richer empty-state UX polish
- Test hints:
  - verify unmatched `period_days` scopes return empty arrays rather than demo rows
  - keep direct item-detail fallback deterministic for unknown/uncomputed rows
  - assert the UI clears selection and shows explicit empty-state copy when no summaries/items exist
- Implementation mapping:
  - trade repository summary/item list reads now return only persisted computed rows and otherwise return empty arrays
  - fallback item detail now uses explicit zero/empty values and empty order lists instead of fake market metrics
  - frontend trade tables render explicit empty-state rows so the page remains stable when no computed opportunities are available
- Mismatches:
  - the detail panel still lacks live order-book data until market-order ingestion exists

### T05F - Computed Source Endpoint Resolution

- Status: `DONE`
- Objective: make `/api/sources` reflect the computed opportunity graph for the selected target/period instead of returning every NPC station.
- Dependencies:
  - T05E
  - T10
- Acceptance criteria:
  - `TradeRepository.list_sources(target_location_id, period_days)` resolves the selected target by its public `location_id`
  - source reads are derived from persisted `opportunity_source_summaries` rows for the selected target/period
  - the endpoint returns public location metadata for only the computed source markets in scope
  - when no computed source summaries exist, the endpoint returns an empty list deterministically
  - deterministic backend tests cover both computed-source and empty-source behavior
- Likely files/modules:
  - `backend/app/repositories/trade_repository.py`
  - `backend/tests/services/test_trade_repository.py`
  - `backend/tests/api/test_endpoints.py`
- Out of scope:
  - frontend trade-page wiring changes
  - source ranking/filtering beyond the persisted summary table
  - live order-book ingestion
- Test hints:
  - seed a persisted `OpportunitySourceSummary` row and assert the endpoint returns the matching public source location
  - verify unmatched `period_days` scopes return `[]`
  - keep repository methods tolerant of public API ids at the boundary
- Implementation mapping:
  - the source endpoint now resolves the selected target by public `location_id` and reads only persisted computed source markets from `opportunity_source_summaries`
  - API and repository tests cover both populated and empty computed-source scopes
- Mismatches:
  - the endpoint still depends on computed opportunity summaries and therefore remains empty until rebuilds have populated those rows

## T06 - Sync Operations Dashboard

- Status: `DONE`
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
  - the sync dashboard is API-backed with persisted job history, history-derived status cards, real fallback diagnostics, and a persisted worker-heartbeat card
  - manual sync actions exist for the implemented operations and route through the same persisted sync-service workflow
  - backend sync route tests and frontend sync page render tests cover the operational dashboard baseline
- Mismatches:
  - richer scheduler timing and ESI rate-limit telemetry remain future operational polish beyond this packet

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

### T06C - Persisted Fallback Diagnostics

- Status: `DONE`
- Objective: replace synthetic fallback diagnostics with rows derived from persisted structure demand-resolution data.
- Dependencies:
  - T06B
  - T11C
- Acceptance criteria:
  - `SyncService.get_fallback_status()` reads persisted structure-target rows instead of returning hardcoded examples
  - diagnostics are derived from real structure locations and persisted resolved-demand fields for implemented sources like `local_structure` and `regional_fallback`
  - NPC locations are excluded
  - empty-data behavior is stable and deterministic
  - deterministic backend tests cover structure rows using local demand, structure rows using fallback, and no persisted structure-demand rows
- Likely files/modules:
  - `backend/app/services/sync/service.py`
  - `backend/tests/services/test_sync_service.py`
- Out of scope:
  - worker health telemetry
  - ESI rate-limit telemetry
  - frontend sync page redesign
  - new sync orchestration
- Test hints:
  - seed tracked-structure and resolved-demand rows directly
  - use persisted structure/location names rather than synthetic labels
  - keep repeated calls deterministic in ordering and values
- Implementation mapping:
  - `SyncService.get_fallback_status()` now derives diagnostics from persisted tracked-structure and structure-demand rows instead of hardcoded samples
- Mismatches:
  - this packet grounds fallback diagnostics in persisted data but does not add worker or rate-limit telemetry

### T06D - Persisted Worker Health Card

- Status: `DONE`
- Objective: replace the synthetic worker health card with a value derived from a real persisted heartbeat source.
- Dependencies:
  - T06B
- Acceptance criteria:
  - `SyncService.get_status()` derives the `worker` card from persisted worker-health data instead of hardcoding it
  - worker health exposes at least `status`, `last_successful_sync` or equivalent heartbeat timestamp, and deterministic default behavior
  - the card remains stable when no worker heartbeat exists yet
  - deterministic backend tests cover fresh heartbeat, stale heartbeat, and no heartbeat data
- Likely files/modules:
  - `backend/app/services/sync/service.py`
  - `backend/app/models/all_models.py`
  - `backend/tests/services/test_sync_service.py`
  - `backend/alembic/versions/*` if a new persisted heartbeat field or table is required
- Out of scope:
  - scheduler-derived `next_scheduled_sync`
  - ESI rate-limit telemetry
  - frontend redesign
  - broader sync-job orchestration
- Test hints:
  - keep the heartbeat freshness rule explicit and deterministic
  - do not reuse manual `sync_job_runs` as a fake worker heartbeat
  - verify stable defaults when no heartbeat has been recorded yet
- Implementation mapping:
  - `SyncService.get_status()` now derives the worker card from the latest persisted heartbeat row and marks it degraded once the heartbeat becomes stale
- Mismatches:
  - this packet removes the synthetic worker card but does not add scheduler timing or rate-limit telemetry

## T07 - Characters, Auth, And Multi-User Support

- Status: `DONE`
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
  - auth and character routes are backed by persisted users, characters, tokens, sync state, and accessible-structure rows
  - first-character creation, additional-character linking, connect/login entrypoints, and mocked character sync/discovery flows are implemented end to end for the single-user MVP
  - backend service and API tests cover persisted reads, updates, user linking, structure discovery, and sync-state updates
- Mismatches:
  - advanced multi-user session ownership and live ESI ingestion remain future scope beyond this packet

### T07A - Persisted Character Reads

- Status: `DONE`
- Objective: replace the demo-backed character list/detail reads with persisted character, sync-state, and accessible-structure data.
- Dependencies:
  - T02
  - T07 auth callback persistence
- Acceptance criteria:
  - `CharacterService.list_characters()` reads persisted `esi_characters` rows and joins available sync-state data
  - accessible structure counts come from persisted `character_accessible_structures`
  - `CharacterService.get_character(character_id)` returns persisted character detail and structures for the requested public EVE character id
  - missing characters fail deterministically instead of returning demo data
  - deterministic backend tests cover list, detail, structure mapping, and missing-character behavior
- Likely files/modules:
  - `backend/app/services/characters/service.py`
  - `backend/tests/services/test_character_service.py`
  - `backend/tests/api/test_endpoints.py`
- Out of scope:
  - live EVE SSO token exchange changes
  - per-toggle sync preferences persistence
  - structure discovery from ESI assets/orders
- Test hints:
  - seed `EsiCharacter`, `EsiCharacterSyncState`, and `CharacterAccessibleStructure` rows directly in SQLite fixtures
  - verify public `character_id` values are preserved at the service/API boundary
  - verify empty-structure characters still return stable defaults
- Implementation mapping:
  - the character service now reads persisted character, sync-state, and accessible-structure rows instead of serving hardcoded demo payloads
  - missing characters now raise a deterministic not-found error for the API layer
- Mismatches:
  - character sync toggles are still a simple shared `sync_enabled` projection rather than per-domain persisted settings
  - skills remain placeholder empty data until a real character sync pipeline exists

### T07B - Persisted Character Sync Toggle Updates

- Status: `DONE`
- Objective: make `PATCH /api/characters/{id}` update persisted character sync enablement instead of returning a stub message.
- Dependencies:
  - T07A
- Acceptance criteria:
  - patching a public EVE `character_id` with `sync_enabled` persists the new value to `esi_characters`
  - list/detail reads reflect the updated `sync_enabled` state after the patch
  - missing characters fail deterministically instead of returning a success stub
  - deterministic backend tests cover update, no-op payload behavior, and missing-character behavior
- Implementation mapping:
  - `PATCH /api/characters/{id}` now persists the shared `sync_enabled` flag and the existing list/detail reads reflect the updated value
- Mismatches:
  - only the shared `sync_enabled` flag is persisted; granular sync toggles remain future work

### T07C - Persisted Character Structure Tracking Flag

- Status: `DONE`
- Objective: make `POST /api/characters/{id}/structures/{structure_id}/track` persist the character-scoped tracking flag instead of returning a stub message.
- Dependencies:
  - T07A
- Acceptance criteria:
  - the route resolves the target by public EVE `character_id`
  - tracking an accessible structure persists `tracking_enabled=True` on `character_accessible_structures`
  - repeated track requests are deterministic and idempotent
  - missing characters or inaccessible structures fail deterministically instead of returning a success stub
  - deterministic backend tests cover first-time tracking, idempotent re-track behavior, and missing-character or missing-structure behavior
- Implementation mapping:
  - the structure-track route now persists `tracking_enabled=True` on the matching accessible-structure row and reuses the same value on repeat calls
- Mismatches:
  - this packet only persists the character-scoped tracking flag; shared tracked-structure pool updates remain future work

### T07D - Link Additional EVE SSO Characters To Existing User

- Status: `DONE`
- Objective: make a second distinct EVE SSO callback attach the new character to the existing user instead of creating a second user row.
- Dependencies:
  - T07 auth callback persistence
- Acceptance criteria:
  - first callback for a new installation still creates the initial user, character, token, and sync-state rows
  - a callback for a different public `character_id` links that character to the existing user instead of creating a second user
  - existing-character callbacks still update the same character/token records without duplication
  - the existing user's `primary_character_id` remains stable unless it is currently unset
  - deterministic backend tests cover first-character creation, second-character linking, repeat callbacks, and duplicate prevention
- Likely files/modules:
  - `backend/app/services/auth/service.py`
  - `backend/tests/services/test_auth_service.py`
- Out of scope:
  - real authenticated session ownership
  - `/api/characters/connect` route redesign
  - queueing initial sync jobs
  - structure discovery from assets/orders
- Test hints:
  - reuse the mocked ESI callback client with two distinct `character_id` values
  - assert one `users` row with two linked `esi_characters`
  - keep the single-user assumption explicit in test naming and assertions
- Implementation mapping:
  - `AuthService.handle_callback()` now links a second distinct character to the first existing user row under the current single-user MVP assumption
  - existing-character callbacks still update in place without duplicating token or sync-state rows
- Mismatches:
  - linking still relies on the current single-user app assumption rather than real session ownership

### T07E - Character Connect Entry Point

- Status: `DONE`
- Objective: make `/api/characters/connect` return the actionable EVE SSO login payload instead of a stub message.
- Dependencies:
  - T07 auth route scaffold
- Acceptance criteria:
  - `/api/characters/connect` returns the same redirect payload shape as `/api/auth/login`
  - the login redirect remains defined in one place so the two entry points stay aligned
  - backend tests cover the connect route and guard the shared login payload shape
- Likely files/modules:
  - `backend/app/api/routes/auth.py`
  - `backend/app/api/routes/characters.py`
  - `backend/tests/api/test_endpoints.py`
- Out of scope:
  - callback persistence changes
  - real browser/session redirects
  - frontend characters-page wiring
- Test hints:
  - assert the response contains `authorize_url` and `scopes`
  - keep `/api/auth/login` as the source of truth rather than duplicating query construction
- Implementation mapping:
  - `/api/characters/connect` now returns the shared auth-login redirect payload instead of a stub message
- Mismatches:
  - this packet improves the connect entry point but does not add real session ownership or browser redirect handling

### T07F - Persist Accessible Structure Discovery From Character Sync Inputs

- Status: `DONE`
- Objective: persist discovered accessible structures for a character from mocked asset/order-derived structure inputs.
- Dependencies:
  - T07A
  - T07C
- Acceptance criteria:
  - a backend service accepts a target public `character_id` plus resolved discovered-structure inputs
  - unique structure ids from combined inputs are deduplicated before persistence
  - the service upserts `character_accessible_structures` rows for that character and preserves `tracking_enabled=True` on existing rows
  - existing discovered structures are updated in place when metadata changes instead of duplicated
  - deterministic backend tests cover asset-only discovery, combined duplicate inputs, update-in-place behavior, and missing-character handling
- Likely files/modules:
  - `backend/app/services/characters/service.py`
  - `backend/tests/services/test_character_service.py`
- Out of scope:
  - live ESI HTTP calls
  - wiring `/api/characters/{id}/sync` end to end
  - shared `tracked_structures` updates
  - frontend characters-page work
- Test hints:
  - pass resolved structure metadata objects rather than raw asset/order payloads
  - verify rediscovery does not reset `tracking_enabled`
  - assert one row per `(character, structure_id)` after duplicate inputs
- Implementation mapping:
  - `CharacterService.discover_character_accessible_structures()` now deduplicates resolved inputs by `structure_id`, upserts rows in place, and preserves existing `tracking_enabled=True` values
  - deterministic service tests cover asset-only discovery, duplicate inputs, metadata refresh, and missing-character handling
- Mismatches:
  - this packet persists discovered accessible structures but does not yet wire live ESI fetches or sync orchestration

### T07G - Character Sync Route Triggers Structure Discovery

- Status: `DONE`
- Objective: make `POST /api/characters/{id}/sync` invoke a mocked character-sync path that persists discovered accessible structures and updates sync-state metadata.
- Dependencies:
  - T07F
- Acceptance criteria:
  - `POST /api/characters/{character_id}/sync` resolves the public EVE `character_id` and fails deterministically for missing characters
  - the sync path calls the existing discovery persistence behavior with mocked/resolved structure inputs
  - `esi_character_sync_state` is updated deterministically for the character, at minimum `last_successful_sync` and `structures_sync_status`
  - repeated sync calls are deterministic and do not duplicate accessible-structure rows
  - backend tests cover successful sync, missing-character handling, read-after-write on discovered structures, and sync-state updates
- Likely files/modules:
  - `backend/app/api/routes/characters.py`
  - `backend/app/services/characters/service.py`
  - `backend/tests/api/test_endpoints.py`
  - `backend/tests/services/test_character_service.py`
- Out of scope:
  - live ESI HTTP calls
  - full asset/order/skills persistence
  - worker/job orchestration
  - shared `tracked_structures` updates
  - frontend characters-page changes
- Test hints:
  - reuse the T07F discovery service instead of duplicating discovery logic in the route
  - keep mocked structure inputs deterministic
  - assert both sync-state updates and discovered-structure persistence
- Implementation mapping:
  - `POST /api/characters/{character_id}/sync` now runs the mocked discovery path, persists discovered structures, and updates sync-state metadata in place
- Mismatches:
  - this packet wires mocked sync behavior only; live ESI sync and broader character data ingestion remain future work

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

- Status: `DONE`
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
  - backend formula, API, and service tests exist; frontend render tests exist for the routed shells and core trade/sync pages.
  - backend `uv sync` now installs the `ruff`, `mypy`, and `pytest` quality gates by default so the documented repository checks are directly runnable.
- Mismatches:
  - broader end-to-end coverage is still intentionally out of scope for this baseline packet

## T10 - Live Ingestion And Opportunity Computation

- Status: `DONE`
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
  - live public ESI regional-history and Adam4EVE NPC-demand clients now persist normalized raw data into the internal history tables
  - period pricing, resolved demand, opportunity items, and opportunity source summaries are computed from stored data through deterministic service pipelines
  - manual and scheduler-driven rebuild paths now populate the query-ready opportunity tables consumed by the trade API instead of demo rows
- Mismatches:
  - live order-book liquidity inputs and richer regional fallback demand remain future enhancements beyond this packet

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

### T10G - Scheduler-Driven Opportunity Rebuild

- Status: `DONE`
- Objective: make the worker scheduler invoke the real persisted opportunity rebuild flow instead of leaving background rebuild orchestration as a placeholder.
- Dependencies:
  - T10F
  - T06A
- Acceptance criteria:
  - the worker-facing opportunity rebuild task delegates to the existing persisted `opportunity_rebuild` sync path
  - scheduler registration keeps the heartbeat task and registers the real opportunity rebuild task without changing the existing cadence contract
  - deterministic backend tests cover task delegation and scheduler/job registration for the rebuild task
  - the background entrypoint does not reintroduce placeholder opportunity generation behavior
- Likely files/modules:
  - `backend/app/workers/tasks/sync_tasks.py`
  - `backend/app/workers/scheduler/runner.py`
  - `backend/tests/`
- Out of scope:
  - scheduler persistence or distributed locking
  - live order ingestion
  - frontend changes
  - changing the current rebuild selection logic
- Test hints:
  - assert the worker task calls the same sync-service path used by the manual API trigger
  - keep scheduler tests focused on registered job IDs and callables rather than sleeping on real intervals
  - preserve the existing heartbeat job registration
- Implementation mapping:
  - the worker rebuild task now delegates to the existing `SyncService().trigger_job("opportunity_rebuild")` path instead of logging a placeholder
  - scheduler registration keeps the heartbeat and rebuild jobs on their existing 5-minute and 10-minute intervals
  - deterministic worker tests cover rebuild delegation, scheduler registration, and the runner entrypoint wiring
- Mismatches:
  - the background rebuild now runs the real persisted rebuild flow, but the underlying opportunity generation still uses placeholder liquidity inputs until live order ingestion exists

### T10H - Live ESI Regional History Client

- Status: `DONE`
- Objective: replace the mocked ESI regional-history fetcher with a real live client while preserving the existing normalized ingestion contract.
- Dependencies:
  - T10B
- Acceptance criteria:
  - `EsiClient.fetch_regional_history(region_id, type_ids)` fetches live market-history payloads from ESI for the requested scope
  - the client returns normalized `EsiRegionalHistoryRecord` rows that continue to work with the existing ingestion service unchanged
  - deterministic tests cover request/parse behavior plus malformed or empty response handling
  - the implementation does not require character auth or change the sync-service ingestion contract
- Likely files/modules:
  - `backend/app/services/esi/client.py`
  - `backend/tests/services/test_esi_history_ingestion.py`
  - `backend/tests/services/`
- Out of scope:
  - EVE SSO token exchange
  - Adam4EVE demand fetching
  - rate-limit/backoff orchestration beyond minimal client hygiene
  - frontend changes
  - scheduler changes
- Test hints:
  - keep request logic isolated so parsing can be tested deterministically with mocked HTTP responses
  - preserve the current `EsiRegionalHistoryRecord` shape exactly
  - fail clearly on malformed payload rows rather than silently returning partial data
- Implementation mapping:
  - `EsiClient.fetch_regional_history()` now calls public ESI market-history endpoints for each requested `type_id` and normalizes the payload into the existing ingestion record shape
  - deterministic tests cover request formation, header propagation, empty responses, and malformed payload rejection
  - the sync-service ingestion contract remains unchanged because the client still returns the same `EsiRegionalHistoryRecord` structure
- Mismatches:
  - live ESI availability and rate limiting remain external dependencies, but the client contract is now real and public-only

### T10I - Live Adam4EVE NPC Demand Client

- Status: `DONE`
- Objective: replace the mocked Adam4EVE NPC-demand fetcher with a real public client while preserving the existing normalized ingestion contract.
- Dependencies:
  - T10C
- Acceptance criteria:
  - `Adam4EveClient.fetch_npc_demand(location_ids, type_ids)` fetches public NPC-demand payloads for the requested scope
  - the client returns normalized `AdamNpcDemandRecord` rows that continue to work with the existing ingestion service unchanged
  - deterministic tests cover request/parse behavior plus malformed or empty response handling
  - the implementation does not require EVE SSO auth or change sync-service wiring
- Likely files/modules:
  - `backend/app/services/adam4eve/client.py`
  - `backend/tests/services/test_adam4eve_ingestion.py`
  - `backend/tests/services/`
- Out of scope:
  - character auth
  - scheduler changes
  - frontend changes
  - resolved-demand logic
  - broader rate-limit/backoff orchestration
- Test hints:
  - keep request logic isolated so parsing can be tested deterministically with mocked HTTP responses
  - preserve the current `AdamNpcDemandRecord` shape exactly
  - fail clearly on malformed payload rows rather than silently returning partial data
- Implementation mapping:
  - `Adam4EveClient.fetch_npc_demand()` now resolves the latest public MarketOrdersTrades export, filters it to the requested location/type scope, and normalizes matching rows into the existing demand record shape.
  - deterministic tests cover the live-request shape, aggregation of matching rows, empty responses, and malformed CSV payload handling.
  - the sync-service ingestion contract remains unchanged because the client still returns the same `AdamNpcDemandRecord` structure.
- Mismatches:
  - the client still depends on the availability of Adam4EVE's public static export pages, but it no longer uses the hardcoded placeholder demand rows.

## T11 - Structure Snapshots And Demand Inference

- Status: `DONE`
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
  - tracked-structure snapshot batches, persisted order deltas, and demand-period aggregations are implemented through dedicated structure services
  - confidence-gated local structure demand now feeds market-demand resolution, with deterministic fallback to regional placeholder demand when coverage is insufficient
  - the sync layer exposes a structure snapshot orchestration path so tracked structures can participate in downstream opportunity computation
- Mismatches:
  - live authenticated structure polling and richer CCP-derived fallback demand remain future work beyond this packet

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

### T11D - Structure Snapshot Sync Orchestration

- Status: `DONE`
- Objective: add a sync entrypoint that runs the existing structure snapshot, delta, and demand-period pipeline for tracked structures.
- Dependencies:
  - T11A
  - T11B
  - T06A
- Acceptance criteria:
  - `SyncService` or the worker task layer exposes a structure snapshot sync job for tracked structures
  - the job runs the existing snapshot persistence, delta computation, and structure demand-period refresh pipeline end to end
  - reruns are deterministic for the same input and do not duplicate persisted work unexpectedly
  - deterministic backend tests cover orchestration plus persisted snapshot/delta/demand updates
- Likely files/modules:
  - `backend/app/services/sync/service.py`
  - `backend/app/workers/tasks/sync_tasks.py`
  - `backend/tests/services/test_sync_service.py`
  - `backend/tests/services/test_structure_snapshots.py`
  - `backend/tests/services/test_structure_demand_periods.py`
- Out of scope:
  - live structure HTTP polling
  - EVE SSO/auth changes
  - frontend changes
  - broader confidence heuristic changes
- Test hints:
  - reuse the existing structure snapshot and demand-period services instead of reimplementing the pipeline in the sync layer
  - keep orchestration tests deterministic with mocked structure-order inputs
  - verify reruns update the expected derived rows without uncontrolled duplication
- Implementation mapping:
  - `SyncService` now exposes `structure_snapshot_sync` and reuses the existing snapshot and demand-period services to persist snapshots, compute deltas, and refresh affected structure demand periods.
  - the sync path is orchestration-only and uses an injectable snapshot batch source, so reruns with the same snapshot input safely no-op instead of duplicating rows.
  - deterministic sync-service coverage verifies the persisted snapshot, delta, and demand-period updates plus rerun stability.
- Mismatches:
  - the orchestration path exists now, but without an injected/live structure snapshot client it skips rather than polling CCP structure data directly

### T12A - Bulk Rebuild Market Price Periods

- Status: `TODO`
- Objective: replace the per-location, per-item, per-period market price refresh loop with a set-based rebuild that uses regional ESI history once and writes `market_price_period` rows in bulk.
- Dependencies:
  - existing Postgres-backed `esi_history_daily`
  - existing raw ESI COPY ingestion path
- Acceptance criteria:
  - `esi_history_sync` no longer calls `MarketPricePeriodService.upsert_from_history` once per `(period, location, item)` combination
  - market price stats for `3/7/14/30` day periods are derived from `esi_history_daily` in a set-based way and persisted in bulk
  - refreshed `market_price_period` rows remain identical in business meaning for `current_price`, `period_avg_price`, `price_min`, `price_max`, `risk_pct`, and `warning_flag`
  - deterministic backend tests cover both first-build and rerun/update behavior
  - benchmark evidence shows the market-price refresh phase is materially faster than the current ~49-55s region refresh on the debug dataset
- Likely files/modules:
  - `backend/app/services/sync/service.py`
  - `backend/app/services/pricing/market_price_periods.py`
  - `backend/tests/services/test_market_price_periods.py`
  - `backend/tests/services/test_sync_service.py`
- Out of scope:
  - changing demand resolution semantics
  - changing opportunity-generation formulas
  - widening debug mode beyond the current single-region cap
- Test hints:
  - compare first-build vs rerun results for the same region/location/item set
  - assert bulk output matches the existing single-row service semantics on a fixed seeded dataset
  - include a timing-oriented benchmark script or reproducible measurement notes in the devlog
- Implementation mapping:
  - compute period aggregates once per `(region, type, period_days)` and fan them out to the region's locations
  - bulk replace affected `market_price_period` rows instead of issuing thousands of per-row commits
- Mismatches:
  - current implementation still recomputes identical regional history per location and commits one row at a time

### T12B - Fix Adam4EVE Demand Completion Semantics And Bulk Demand Refresh

- Status: `TODO`
- Objective: make `adam4eve_sync` treat weekly Adam4EVE demand exports as incomplete until each region's `synced_through_date` truly reaches the export coverage date, then replace the current full `locations x items` demand rebuild with a set-based refresh over only affected demand keys.
- Dependencies:
  - Adam4EVE weekly demand ingest now append-only with per-region sync state
  - current Postgres-backed `adam_npc_demand_daily`
- Acceptance criteria:
  - Adam demand sync-state does not treat `export_key` alone as proof of full regional completion
  - a region is considered fully synced for a weekly export only when its `synced_through_date` reaches that export's covered-through date
  - `adam4eve_sync` no longer brute-forces all NPC locations against all items when rebuilding `market_demand_resolved`
  - demand refresh work is limited to touched `(location_id, type_id, period_days)` keys plus any explicitly required cleanup keys
  - deterministic backend tests cover partial-week state, fully-synced state, reruns, and no-op reruns
  - benchmark evidence shows Adam4EVE sync time is dominated neither by weekly export discovery nor by an all-locations-all-items demand rebuild
- Likely files/modules:
  - `backend/app/services/sync/service.py`
  - `backend/app/services/demand/market_demand.py`
  - `backend/app/services/adam4eve/client.py`
  - `backend/tests/services/test_sync_service.py`
  - `backend/tests/services/test_adam4eve_ingestion.py`
  - `backend/tests/services/test_market_demand.py`
- Out of scope:
  - switching to a different raw Adam4EVE demand source
  - redesigning opportunity-generation formulas
  - frontend UX changes
- Test hints:
  - seed a region with `export_key` matching the latest export but `synced_through_date` behind the export coverage date and assert the sync still fetches deltas
  - seed a truly complete region and assert the sync skips download entirely
  - benchmark the live path before and after replacing the full `location_ids x type_ids` demand refresh loop
- Implementation mapping:
  - compute weekly export completeness from `covered_through_date` rather than `export_key` equality
  - derive affected demand keys from imported Adam rows and rebuild only those keys in bulk
- Mismatches:
  - current live state marks some regions with `export_key='2026-13'` even when `synced_through_date` is only `2026-03-24` or `NULL`
  - current demand refresh still loops across roughly `5,154 NPC locations x 17,136 items`, which is the dominant Adam4EVE sync bottleneck
