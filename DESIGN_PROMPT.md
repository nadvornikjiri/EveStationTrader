Build a greenfield web application for EVE Online regional and structure trading analysis.

Primary goal: Create a web app similar in workflow and density to the EveGuru Regional Day Trader screenshots, but with better architecture and separate operational pages for sync and character management.

Core product behavior:
* User selects a target market
* Target market can be an NPC station or a player-owned structure
* App shows all source markets worth buying from and moving goods to the selected target
* Top grid shows one row per source market
* Expanding a source market shows item-level opportunities
* Selecting an item shows detailed execution/order-book context

Tech stack:
* Frontend: React + TypeScript
* Backend: Python + FastAPI
* Database: PostgreSQL
* ORM: SQLAlchemy 2.0
* Migrations: Alembic
* Background jobs: Python worker, APScheduler acceptable for MVP, Celery acceptable if preferred
* Optional cache/broker: Redis
* Testing:
  * Backend: pytest
  * Frontend: vitest + React Testing Library acceptable
  * API/integration tests where practical

Architecture style:
* Modular monolith
* Frontend separated from backend API
* Background workers separated from API
* UI must read mostly from precomputed/query-ready tables, not compute everything on request from raw snapshots

High-level modules:
1. Frontend web UI
2. FastAPI backend
3. Background sync/compute worker
4. PostgreSQL database

Application pages:
* /trade
* /sync
* /characters
* /settings

==================================================
1. TRADE PAGE SPEC
==================================================

Purpose: Main analysis page for source -> target market opportunities.

General layout:
* Top control bar
* Source market summary table
* Expandable item-level table
* Item detail panel

Top controls:
* target market selector
* source region(s) filter (e.g. "Major Trade Hub Regions", individual regions, or all)
* analysis period selector, default 14 days
* source type filter: npc / structure / all
* min security filter: high sec / low sec / null sec / all (default: high sec)
* demand source filter: Adam4EVE / Local / Fallback / Blended / All
* warning toggle: enable or disable price warning hints
* warning threshold %, default 50
* last refresh timestamp
* item name search box (filters item-level table by name substring match)
* optional filters for min ROI, min demand/day, max DOS, min confidence

Default item inclusion filters (configurable on trade page):
* target_now_profit > 0
* min_item_profit (absolute ISK floor, e.g. 15,000,000)
* min_order_margin_pct (minimum spread %, e.g. 20%)
* roi_now > 0.05 (5%)
* target_demand_day > 1
* source_units_available > 0

UI update behavior:
* Poll API on configurable interval, default 60 seconds
* Manual refresh button
* Display last refresh timestamp

Trade page data hierarchy:
1. Source summary row
2. Item row inside selected source
3. Item detail/order-book panel

1A. SOURCE MARKET SUMMARY TABLE

Each row represents:
* one source market evaluated against one selected target market
* aggregate metrics across all viable items

All columns sortable by click. Default sort: descending by roi_now_weighted.

Columns, in this explicit order:

1. Source Market
   * source_market_name

2. Sec
   * source_security_status
   * security status of the source system (e.g. 0.9, 0.5, -0.3)

3. Purchase Units
   * purchase_units_total
   * aggregate recommended buy quantity across included item opportunities

4. Source Units Available
   * source_units_available_total
   * aggregate source sell-side liquidity across included items

5. Target Demand / Day
   * target_demand_day_total or weighted_target_demand_day
   * resolved target demand based on source rules below

6. Target Supply Units
   * target_supply_units_total or weighted_target_supply_units
   * aggregate current sell-side supply in target across included items

7. Target D.O.S
   * target_dos_weighted
   * weighted days-of-supply value for the included items

8. In Transit
   * in_transit_units
   * authenticated character data if available

9. Assets
   * assets_units
   * authenticated character assets already in target or assigned relevant scope

10. Active Sell Orders
    * active_sell_orders_units
    * user's current sell order quantity in target if available

11. Source Avg Price
    * source_avg_price_weighted
    * weighted source-side sell price basis across included items

12. Target Now Price
    * target_now_price_weighted
    * weighted current target sell price basis across included items

13. Target Period Avg Price
    * target_period_avg_price_weighted
    * weighted target average price across selected period

14. Risk %
    * risk_pct_weighted

15. Warning
    * warning_count or warning_flag_aggregate
    * count of items triggering warning or boolean aggregate indicator

16. Target Now Profit
    * target_now_profit_weighted
    * IMPORTANT: this is per-unit margin style, not total daily profit
    * formula at item level: target_now_profit = target_station_sell_price * (1 - sales_tax_rate - broker_fee_rate) - source_station_sell_price
    * summary row should show weighted average or another explicit aggregate, not a naive sum

17. Target Period Profit
    * target_period_profit_weighted
    * profit based on period average price instead of current price
    * formula at item level: target_period_profit = target_period_avg_price * (1 - sales_tax_rate - broker_fee_rate) - source_station_sell_price
    * summary row should show weighted average

18. Capital Required
    * capital_required_total
    * IMPORTANT: this is based on one day of target demand
    * formula at item level: capital_required = source_station_sell_price * target_demand_day
    * summary row should sum item capital_required values

19. ROI Now
    * roi_now_weighted
    * weighted ROI across included items

20. ROI Period
    * roi_period_weighted
    * ROI based on period average price
    * formula at item level: roi_period = target_period_profit / source_station_sell_price

21. Item Volume
    * total_item_volume_m3
    * aggregate m3 to transport across included items

22. Shipping Cost
    * shipping_cost_total

23. Demand Source
    * demand_source_summary
    * Adam4EVE / Local / Fallback / Blended
    * if mixed, show Mixed or dominant source plus detail tooltip

24. Confidence
    * confidence_score_summary
    * weighted or lowest confidence indicator for included items

1B. ITEM-LEVEL TABLE

Each row represents:
* one item opportunity from selected source market to selected target market

All columns sortable by click. Default sort: descending by roi_now.
Item name search box filters rows by substring match.

Columns, in this explicit order:

1. Sec
   * source_security_status
   * security status of the source system

2. Item Name
   * item_name
   * include icon if available

3. Purchase Units
   * purchase_units
   * recommended quantity to acquire now

4. Source Units Available
   * source_units_available
   * current source market sell-side liquidity relevant to purchase

5. Target Demand / Day
   * target_demand_day
   * for NPC use Adam4EVE
   * for structures use local inferred demand if sufficient confidence
   * otherwise CCP fallback

6. Target Supply Units
   * target_supply_units
   * current target sell-side supply

7. Target D.O.S
   * target_dos
   * formula: target_supply_units / max(target_demand_day, epsilon)

8. In Transit
   * in_transit_units_item

9. Assets
   * assets_units_item

10. Active Sell Orders
    * active_sell_orders_units_item

11. Source Avg Price
    * source_station_sell_price
    * source-side lowest sell order price

12. Target Now Price
    * target_station_sell_price
    * target-side lowest sell order price

13. Target Period Avg Price
    * target_period_avg_price
    * based on selected period length, default 14 days

14. Risk %
    * risk_pct
    * formula: risk_pct = (target_period_avg_price - target_station_sell_price) / target_station_sell_price
    * risk can be negative
    * positive means current target price is below period average
    * negative means current target price is above period average

15. Warning
    * warning_flag
    * formula: abs(risk_pct) > warning_threshold
    * default threshold 50%

16. Target Now Profit
    * target_now_profit
    * IMPORTANT: target_now_profit = target_station_sell_price * (1 - sales_tax_rate - broker_fee_rate) - source_station_sell_price
    * this is per-unit margin after taxes

17. Target Period Profit
    * target_period_profit
    * target_period_profit = target_period_avg_price * (1 - sales_tax_rate - broker_fee_rate) - source_station_sell_price
    * per-unit margin based on period average price after taxes

18. Capital Required
    * capital_required
    * IMPORTANT: capital_required = source_station_sell_price * target_demand_day
    * represents the ISK needed to fund one day of target demand at source acquisition price

19. ROI Now
    * roi_now
    * formula: roi_now = target_now_profit / source_station_sell_price

20. ROI Period
    * roi_period
    * formula: roi_period = target_period_profit / source_station_sell_price

21. Item Volume
    * item_volume_m3

22. Shipping Cost
    * shipping_cost

23. Demand Source
    * demand_source
    * one of: Adam4EVE Local Fallback Blended

24. Confidence
    * confidence_score

Optional internal-only fields for later:
* daily_profit_potential = target_now_profit * target_demand_day
* profit_after_shipping = target_now_profit - shipping_cost_per_unit
* ranking_score

1C. ITEM DETAIL PANEL

Purpose: Show order-book and execution context for selected item.

Panels:
1. Target Market Sell Orders
2. Source Market Sell Orders
3. Source Market Buy Orders
4. Trade Metrics Summary

Target Market Sell Orders columns:
* price
* volume
* order value
* cumulative volume (optional)

Source Market Sell Orders columns:
* price
* volume
* order value

Source Market Buy Orders columns:
* price
* volume
* order value

Trade Metrics Summary fields:
* source best sell
* source weighted sell
* target best sell
* target weighted sell
* spread
* target_now_profit
* target_period_profit
* target_demand_day
* target_supply_units
* target_dos
* demand_source
* confidence_score
* period_days
* target_period_avg_price
* risk_pct
* warning_flag
* roi_now
* roi_period
* item_volume_m3
* shipping_cost

==================================================
2. PRICE BASIS RULES
==================================================

source_station_sell_price = lowest price sell order in source market for the item
target_station_sell_price = lowest price sell order in target market for the item

These are used consistently across all opportunity calculations, item rows, and source summaries.

==================================================
3. DEMAND SOURCE RULES
==================================================

NPC target markets:
* use Adam4EVE for demand/day
* Adam4EVE is the primary demand source for NPC hubs
* store demand source as Adam4EVE

Player-owned structure target markets:
* use local inferred demand from periodic snapshots if sufficient data exists
* otherwise fall back to CCP regional statistics
* optional later: blended local + fallback source

Demand source enum:
* adam4eve
* local_structure
* regional_fallback
* blended

Confidence rules for structure local demand:
* compute confidence based on: observation_window_hours snapshot_coverage_pct observed_order_change_count recency_of_latest_snapshot
* simple MVP gate: if observation window >= 72 hours and snapshot coverage >= 75%, local demand may be used otherwise use fallback

Adam4EVE API documentation: https://www.adam4eve.eu/api/

==================================================
4. PLAYER-OWNED STRUCTURE TRACKING RULES
==================================================

Do not attempt to track all public structures in the game.

Structure tracking sources:
1. Built-in seed list of known player trade hubs (~10 structures)
2. Character-discovered structures — any structure where a connected character has assets or orders
3. Manual user additions — entered by structure_id

Seed built-in tracked structures with approximately 10 known trade-focused structures:
* include major Perimeter / Jita-adjacent hubs
* include Ashab / Amarr-adjacent hubs
* include Amamake lowsec trade hub
* include other known player trade hubs
* store by structure_id and display name
* make this seed list editable later

Polling tiers:
* core hubs: every 10 minutes
* secondary hubs: every 30 to 60 minutes
* user-added hubs: configurable, default 30 minutes

User structure management:
* allow manual add of a structure
* allow enable/disable tracking
* allow poll interval override
* allow promote to core or demote to secondary later

==================================================
5. CHARACTER STRUCTURE DISCOVERY
==================================================

When a character is connected via EVE SSO:
* Query character's accessible structures via ESI
  - GET /characters/{character_id}/assets/ — extract unique structure_id values from asset locations
  - GET /characters/{character_id}/orders/ — extract unique structure_id values from active orders
  - GET /universe/structures/{structure_id}/ (authed) — resolve name, system, type for each discovered structure_id
* Persist discovered structures to character_accessible_structures
* Structures discovered by ANY character in the user pool become available for tracking
* Refresh structure discovery on each character sync cycle
* User can then enable tracking on any discovered structure from the Characters page or Settings

==================================================
6. FOUNDATION DATA SYNC
==================================================

Static/semi-static data (download once, refresh weekly or on EVE patch day):
* Universe types — item names, volume, group/category
  - Use CCP Static Data Export (SDE) via Fuzzwork SQL dump (https://www.fuzzwork.co.uk/dump/) or hoboleaks
  - Only use ESI for deltas if needed
* Universe regions — GET /universe/regions/ — region list + names
* Universe systems — GET /universe/systems/ — systems with region mapping
* Universe stations — NPC station names/locations, available in SDE
* Market groups — GET /markets/groups/ — item categorization

Live data (every poll cycle, freshness matters):
* Market orders — GET /markets/{region_id}/orders/ for NPC regions, GET /markets/structures/{structure_id}/ for player structures
  - These are the only data requiring 10-minute freshness
* Market history — GET /markets/{region_id}/history/ — daily OHLCV per type per region, refresh daily

Character-discovered data (on character connect + each sync cycle):
* Character assets — GET /characters/{character_id}/assets/
* Character orders — GET /characters/{character_id}/orders/
* Accessible structures — resolved via GET /universe/structures/{structure_id}/ (authed)

ESI bulk download strategy:
* Use aggregated/bulk endpoints wherever possible (download all data needed, not one-by-one)
* GET /markets/{region_id}/orders/ returns ALL orders for a region — use this instead of per-type queries
* GET /markets/{region_id}/history/ is per-type — batch these efficiently

==================================================
7. ESI RATE LIMITING
==================================================

ESI has strict rate limits. Implement rate-limit tracking as a first-class concern:
* Track X-ESI-Error-Limit-Remain header on every ESI response
* Back off when X-ESI-Error-Limit-Remain drops below 20
* Use ETag / If-None-Modified headers to skip unchanged responses and reduce load
* Implement exponential backoff on 5xx and 420 (error limited) responses
* Use Redis or in-memory token bucket for rate tracking
* Log rate limit state for debugging on sync page

==================================================
8. LOCAL STRUCTURE DEMAND INFERENCE
==================================================

Goal: Infer buys-from-sells and sells-to-buys from periodic structure snapshots.

Snapshot model:
* poll structure market orders on cadence
* persist raw snapshots
* diff consecutive snapshots

Inference rules:
* reduction in remaining volume on a sell order implies buys from sell orders
* reduction in remaining volume on a buy order implies sells to buy orders
* disappeared orders are uncertain
* keep min, max, and chosen demand estimates

Store:
* demand_min
* demand_max
* demand_chosen

Use:
* demand_chosen as primary local demand/day metric

Structure fallback:
* if insufficient local data, use CCP regional statistics for the corresponding region
* mark demand source as regional_fallback

==================================================
9. RISK AND WARNING RULES
==================================================

Selected analysis period:
* configurable
* default 14 days

Period average price:
* compute target period average price for the selected period
* must support 3, 7, 14, 30 days, plus extensible custom period later

Risk %:
* exact formula: risk_pct = (target_period_avg_price - target_station_sell_price) / target_station_sell_price

Interpretation:
* positive risk_pct means current price is below the selected period average
* negative risk_pct means current price is above the selected period average

Warning rule:
* optional warning hint if abs(risk_pct) > threshold
* default threshold = 50%
* threshold configurable in settings and on the trade page filter bar

==================================================
10. OPPORTUNITY CALCULATION RULES
==================================================

For each item opportunity:
* source_station_sell_price = lowest sell order price in source market for the item
* target_station_sell_price = lowest sell order price in target market for the item
* target_period_avg_price = average target price over selected period
* risk_pct = (target_period_avg_price - target_station_sell_price) / target_station_sell_price
* warning_flag = abs(risk_pct) > warning_threshold
* target_demand_day = resolved demand/day
* target_supply_units = current target-side supply
* target_dos = target_supply_units / max(target_demand_day, epsilon)
* purchase_units = recommended buy quantity, typically capped by demand and source availability
* target_now_profit = target_station_sell_price * (1 - sales_tax_rate - broker_fee_rate) - source_station_sell_price
* target_period_profit = target_period_avg_price * (1 - sales_tax_rate - broker_fee_rate) - source_station_sell_price
* capital_required = source_station_sell_price * target_demand_day
* roi_now = target_now_profit / source_station_sell_price
* roi_period = target_period_profit / source_station_sell_price

Purchase units rule for MVP:
* purchase_units = min(source_units_available, target_demand_day)
* keep architecture flexible so this can later be replaced with a smarter cap

Important distinction:
* target_now_profit is per-unit margin after taxes based on current price
* target_period_profit is per-unit margin after taxes based on period average price
* capital_required is cost to fund one day of target demand at source price
* roi_now is per-unit margin divided by source price
* roi_period is period margin divided by source price

Optional future field:
* daily_profit_potential = target_now_profit * target_demand_day

==================================================
11. MULTI-USER SUPPORT
==================================================

User identity:
* First EVE SSO character connection creates the user account
* User identity is tied to EVE SSO
* A user can connect multiple characters
* Additional EVE SSO logins link to the existing user if already connected

Data ownership model:
* Market data, orders, snapshots, and computed opportunities are SHARED across all users (computed once)
* Character data (assets, orders, in-transit) is per-user, joined at query time
* Settings are per-user with system-level defaults as fallback
* Structure tracking is shared — any user's character can discover structures for the pool

Auth tables:
* users (id, created_at, primary_character_id)
* Link esi_characters to users via user_id foreign key
* Settings table has user_id (nullable — null means system default)

==================================================
12. PAGE SPECS OUTSIDE TRADE
==================================================

12A. SYNC PAGE

Purpose: Operational dashboard for sync health and manual sync execution.

Sections:
1. Overall status cards
2. Manual sync actions
3. Job history table
4. Demand fallback diagnostics

Status cards:
* Adam4EVE sync
* ESI region sync
* structure snapshot sync
* character sync
* worker health
* ESI rate limit status

Each card shows:
* status
* last successful sync
* next scheduled sync if applicable
* recent error count

Manual sync actions:
* Sync Adam4EVE now
* Sync ESI history now
* Sync tracked structures now
* Sync all characters now
* Rebuild opportunities now

Job history table columns:
* started_at
* finished_at
* job_type
* status
* duration
* records_processed
* target_type
* target_id
* message
* error_details

Fallback diagnostics:
* structures using local demand
* structures using fallback
* structures using blended demand
* confidence state

12B. CHARACTERS PAGE

Purpose: Manage EVE SSO connected characters and character-based sync inputs.

Character list columns:
* character_name
* corporation_name
* granted_scopes
* sync_enabled
* last_token_refresh
* last_successful_sync
* assets_sync_status
* orders_sync_status
* skills_sync_status
* structures_sync_status
* accessible_structure_count

Character detail sections:
1. identity
2. sync toggles
3. accessible structures
4. skills

Sync toggles:
* sync assets
* sync active market orders
* sync skills
* sync structures

Accessible structures table columns:
* structure_name
* structure_id
* system_name
* region_name
* access_verified_at
* tracking_enabled
* polling_tier
* last_snapshot_at
* confidence_score

Character flows:
* connect new character via EVE SSO
* persist tokens securely
* queue initial sync jobs after successful connect
* on initial sync: discover accessible structures from assets and orders
* use official ESI docs for exact current OAuth scopes when implementing

12C. SETTINGS PAGE

Per-user settings (with system defaults):
* default_analysis_period_days (default: 14)
* warning_threshold_pct (default: 50)
* warning_enabled (default: true)
* sales_tax_rate (default: 0.036 — 3.6% base rate)
* broker_fee_rate (default: 0.03 — 3.0% base rate)
* min_confidence_for_local_structure_demand
* default_user_structure_poll_interval_minutes
* snapshot_retention_days
* fallback_policy
* shipping_cost_per_m3 (labeled as "estimated" in UI)
* default_filters JSON or structured config

Note: sales_tax_rate and broker_fee_rate are user-editable flat values for MVP. Not computed from character skills.

==================================================
13. DATABASE TABLES
==================================================

User/auth tables:
* users
* esi_characters (with user_id FK)
* esi_character_tokens
* esi_character_sync_state

Reference tables:
* regions
* systems
* items
* stations (NPC stations from SDE)
* locations (unified table: id, location_id, location_type [npc_station|structure], system_id, region_id, name)
* tracked_structures

Character data tables:
* character_accessible_structures

Raw ingestion tables:
* esi_history_daily
* adam_npc_demand_daily
* structure_snapshots
* structure_snapshot_orders

Derived tables:
* structure_order_deltas
* structure_demand_period
* market_price_period
* market_demand_resolved
* opportunity_items
* opportunity_source_summaries
* sync_job_runs
* user_settings

Explicit table sketches:

users:
* id
* created_at
* primary_character_id

locations:
* id
* location_id (bigint — EVE station_id or structure_id)
* location_type (enum: npc_station, structure)
* system_id
* region_id
* name

tracked_structures:
* id
* structure_id
* name
* system_id
* region_id
* tracking_tier
* poll_interval_minutes
* is_enabled
* last_polled_at
* last_successful_poll_at
* confidence_score
* notes
* discovered_by_character_id (nullable — null for seed/manual)

structure_snapshots:
* id
* structure_id
* snapshot_time

structure_snapshot_orders:
* id
* snapshot_id
* structure_id
* type_id
* order_id
* is_buy_order
* price
* volume_remain
* issued
* duration

structure_order_deltas:
* id
* structure_id
* type_id
* order_id
* from_snapshot_time
* to_snapshot_time
* old_volume
* new_volume
* delta_volume
* disappeared
* inferred_trade_side
* inferred_trade_units
* price

structure_demand_period:
* id
* structure_id
* type_id
* period_days
* computed_at
* demand_min
* demand_max
* demand_chosen
* coverage_pct
* confidence_score

market_price_period:
* id
* location_id
* type_id
* period_days
* current_price
* period_avg_price
* price_min
* price_max
* computed_at
* risk_pct
* warning_flag

market_demand_resolved:
* id
* location_id
* type_id
* period_days
* demand_source
* confidence_score
* demand_day
* computed_at

opportunity_items:
* id
* target_location_id
* source_location_id
* type_id
* period_days
* purchase_units
* source_units_available
* target_demand_day
* target_supply_units
* target_dos
* in_transit_units
* assets_units
* active_sell_orders_units
* source_station_sell_price
* target_station_sell_price
* target_period_avg_price
* risk_pct
* warning_flag
* target_now_profit
* target_period_profit
* capital_required
* roi_now
* roi_period
* source_security_status
* item_volume_m3
* shipping_cost
* demand_source
* confidence_score
* computed_at

opportunity_source_summaries:
* id
* target_location_id
* source_location_id
* source_security_status
* period_days
* purchase_units_total
* source_units_available_total
* target_demand_day_total
* target_supply_units_total
* target_dos_weighted
* in_transit_units
* assets_units
* active_sell_orders_units
* source_avg_price_weighted
* target_now_price_weighted
* target_period_avg_price_weighted
* risk_pct_weighted
* warning_count
* target_now_profit_weighted
* target_period_profit_weighted
* capital_required_total
* roi_now_weighted
* roi_period_weighted
* total_item_volume_m3
* shipping_cost_total
* demand_source_summary
* confidence_score_summary
* computed_at

sync_job_runs:
* id
* job_type
* status
* triggered_by
* started_at
* finished_at
* duration_ms
* records_processed
* target_type
* target_id
* message
* error_details

user_settings:
* id
* user_id (FK to users, nullable — null = system default)
* key
* value
* updated_at

==================================================
14. API ENDPOINTS
==================================================

Trade:
* GET /api/targets
* GET /api/sources?target_location_id=...&period_days=...
* GET /api/opportunities/source-summaries?target_location_id=...&period_days=...
* GET /api/opportunities/items?target_location_id=...&source_location_id=...&period_days=...
* GET /api/opportunities/item-detail?target_location_id=...&source_location_id=...&type_id=...&period_days=...

Sync:
* GET /api/sync/status
* GET /api/sync/jobs
* POST /api/sync/run/{job_type}
* GET /api/sync/fallback-status

Characters:
* GET /api/characters
* POST /api/characters/connect
* GET /api/characters/{id}
* POST /api/characters/{id}/sync
* PATCH /api/characters/{id}
* GET /api/characters/{id}/structures
* POST /api/characters/{id}/structures/{structure_id}/track

Auth:
* GET /api/auth/login (redirect to EVE SSO)
* GET /api/auth/callback (EVE SSO callback, creates user if first character)
* GET /api/auth/me (current user)
* POST /api/auth/logout

Settings:
* GET /api/settings
* PUT /api/settings

==================================================
15. PROJECT STRUCTURE
==================================================

Backend structure:
backend/
  app/
    api/
      routes/
      schemas/
      deps/
    core/
      config.py
      logging.py
      security.py
    db/
      base.py
      session.py
    models/
    services/
      adam4eve/
      esi/
      structures/
      demand/
      pricing/
      opportunities/
      sync/
      characters/
    repositories/
    workers/
      scheduler/
      tasks/
    domain/
      enums.py
      constants.py
      rules.py
  main.py
  alembic/
  tests/

Frontend structure:
frontend/
  src/
    app/
    pages/
      TradePage.tsx
      SyncPage.tsx
      CharactersPage.tsx
      CharacterDetailPage.tsx
      SettingsPage.tsx
    components/
      trade/
      sync/
      characters/
      settings/
      common/
    api/
    types/
    hooks/
    routes/
    main.tsx

==================================================
16. TESTING REQUIREMENTS
==================================================

Write basic but meaningful tests from the start. Do not leave the project without tests.

Backend tests:
* use pytest
* include unit tests for core formulas
* include service tests for ingestion/transformation logic
* include API tests for key endpoints
* include tests around ESI user setup flows using mocks/stubs

Frontend tests:
* use vitest
* add basic component/render tests for the main page shells
* add at least a few tests for trade table rendering and filter controls if practical

Minimum backend test coverage areas:

1. Column/formula calculation tests
   Test exact formulas and edge cases for:
   * risk_pct = (target_period_avg_price - target_station_sell_price) / target_station_sell_price
   * warning_flag = abs(risk_pct) > threshold
   * target_now_profit = target_station_sell_price * (1 - sales_tax_rate - broker_fee_rate) - source_station_sell_price
   * target_period_profit = target_period_avg_price * (1 - sales_tax_rate - broker_fee_rate) - source_station_sell_price
   * capital_required = source_station_sell_price * target_demand_day
   * roi_now = target_now_profit / source_station_sell_price
   * roi_period = target_period_profit / source_station_sell_price
   * target_dos = target_supply_units / max(target_demand_day, epsilon)
   * purchase_units = min(source_units_available, target_demand_day)
   Include edge cases:
   * zero or tiny demand
   * zero or tiny source price
   * negative risk
   * positive risk
   * threshold boundary cases

2. Ingestion tests
   Write tests for:
   * Adam4EVE ingestion mapping into internal tables/schemas
   * ESI regional history ingestion mapping
   * structure snapshot ingestion
   * structure order delta computation between snapshots
   * local demand inference from sell-order and buy-order volume reductions

3. Demand resolution tests
   Write tests for:
   * NPC target uses Adam4EVE
   * structure target with insufficient local data uses fallback
   * structure target with sufficient local data uses local demand
   * confidence threshold behavior

4. Opportunity aggregation tests
   Write tests for:
   * item opportunity row generation
   * source summary aggregation
   * weighted fields behaving correctly
   * capital_required totals summing correctly
   * warning_count aggregation

5. ESI character setup tests
   Write tests for:
   * character connect flow handler with mocked EVE SSO callback
   * token persistence and update behavior
   * creation of initial character record
   * user creation on first character connect
   * initial sync job enqueue behavior
   * accessible structure discovery from mocked asset/order responses

6. Sync/job tests
   Write tests for:
   * manual sync endpoint triggers correct job type
   * sync job run record creation
   * job status transitions at a basic level

7. API endpoint tests
   Write basic integration tests for:
   * GET /api/targets
   * GET /api/opportunities/source-summaries
   * GET /api/opportunities/items
   * GET /api/sync/status
   * GET /api/characters
   * GET /api/settings
   * GET /api/auth/me

Testing style requirements:
* prefer small deterministic fixtures
* mock external Adam4EVE and ESI HTTP calls
* do not rely on live external APIs in tests
* include factories/fixtures for locations, items, structures, characters, and users
* tests should be runnable locally and in CI

==================================================
17. IMPLEMENTATION PHASES
==================================================

Phase 1:
* backend skeleton
* frontend skeleton
* PostgreSQL schema
* Alembic migrations
* page routing
* placeholder UI
* basic API route stubs
* user and auth table setup
* initial test scaffolding and first formula tests
* foundation data sync (SDE import for types, stations, systems, regions)

Phase 2:
* Adam4EVE NPC demand ingestion
* ESI regional history ingestion
* market price period calculations
* risk calculations
* opportunity_items and opportunity_source_summaries generation
* trade page summary and item grids working end-to-end
* ingestion and aggregation tests

Phase 3:
* EVE SSO character connection and user creation
* character sync for assets, orders, skills, structures
* character structure discovery
* tracked structures management
* structure snapshots
* structure delta inference
* fallback demand logic
* ESI user setup tests and structure inference tests

Phase 4:
* sync dashboard actions and logs
* confidence reporting
* demand source badges
* warning badges
* ESI rate limit monitoring on sync page
* performance tuning
* cleanup and docs
* API integration tests and UI smoke tests

==================================================
18. CODING RULES
==================================================

* Keep API handlers thin
* Put business logic in services
* Keep raw ingestion tables separate from derived query tables
* Use background jobs for sync and recomputation
* Do not compute heavy opportunity logic inside request handlers
* Use typed schemas for request/response contracts
* Keep formulas explicit and unit-tested
* Prefer readability over premature optimization
* Build a runnable MVP scaffold first, then flesh out integrations
* Add tests alongside implementation, not as an afterthought

==================================================
19. GENERATE NOW
==================================================

1. Full backend project scaffold
2. Full frontend project scaffold
3. SQLAlchemy models
4. Alembic initial migration
5. Pydantic schemas
6. FastAPI route stubs
7. Worker job stubs
8. React routes and page shells
9. Seed mechanism for built-in tracked structures
10. Backend test scaffold with initial meaningful tests
11. Frontend test scaffold with basic page/component tests
12. README with architecture, local run instructions, and test instructions

Important implementation preference:
* create the project in a way that is runnable early
* add TODO markers only where external live integration details are still pending
* use mocks/placeholders for Adam4EVE and ESI clients where needed so the app and tests can run before full integration
