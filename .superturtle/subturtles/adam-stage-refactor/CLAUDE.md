# Current task

Rewrite history_ingestion.py: load_csv_to_stage + populate_daily_from_stage + stage_has_export_key (step 3).

# End goal with specs

**Architecture change:**
- CSV files COPY'd once into permanent staging tables (external EVE IDs, typed columns, with export_key)
- Skip already-loaded export_keys (no re-COPY)
- One bulk INSERT INTO daily tables from staging via JOIN on locations/items (internal ID mapping)
- Drop `adam_market_price_history_raw` and `adam_market_volume_history_raw` tables entirely
- Eliminate per-file workset temp table recreation (was 50k+ rows COPY'd per file)

**New tables (via Alembic migration):**
- `adam_price_history_stage`: location_id BIGINT, region_id INT, type_id INT, date DATE, buy_price_low/avg/high FLOAT NULL, sell_price_low/avg/high FLOAT NULL, export_key TEXT NOT NULL. Index on (export_key). UNIQUE on (location_id, type_id, date) — latest export wins via ON CONFLICT UPDATE.
- `adam_volume_history_stage`: location_id BIGINT, region_id INT, type_id INT, date DATE, sell_volume_avg BIGINT NULL, export_key TEXT NOT NULL. Index on (export_key). UNIQUE on (location_id, type_id, date).
- DROP `adam_market_price_history_raw`, DROP `adam_market_volume_history_raw`

**File changes:**

1. `backend/alembic/versions/` — new migration
2. `backend/app/models/all_models.py` — add new stage models, remove Raw table objects
3. `backend/app/models/__init__.py` — update exports
4. `backend/app/services/adam4eve/history_ingestion.py` — major rewrite:
   - New `load_csv_to_stage(session, csv_file_path, export_key)`: COPY CSV into temp text table → INSERT INTO adam_price_history_stage with type casting + export_key, ON CONFLICT (location_id, type_id, date) DO UPDATE
   - New `populate_daily_from_stage(session, since_date)`: DELETE+INSERT into adam_market_price_history_daily via JOIN on locations+items. Return touched_internal_keys.
   - New `stage_has_export_key(session, export_key) -> bool` to check if already loaded
   - Keep temp text table for COPY but create once, TRUNCATE between files (no ON COMMIT DROP)
   - Remove: _prepare_stage_tables, _filtered_stage_sql, _materialize_filtered_stage, _transform_raw_history, all workset logic
   - Keep the ORM fallback path for non-PostgreSQL (tests use SQLite)
5. `backend/app/services/adam4eve/volume_ingestion.py` — same pattern as #4
6. `backend/app/services/sync/service.py`:
   - `_sync_adam_regional_price_history`: loop files calling load_csv_to_stage (skip if stage_has_export_key), then ONE call to populate_daily_from_stage. Remove workset_entries param from this method.
   - `_sync_adam_regional_volume_history`: same
   - `_clear_adam4eve_data`: add deletion of new stage tables, remove raw table references
   - `_history_sync_workset` — can be simplified or removed if only used for workset population
7. `backend/tests/services/test_adam4eve_ingestion.py` — update tests
8. `backend/tests/test_volume_history_models.py` — remove raw table model tests, add stage table tests

**Constraints (CRITICAL):**
- Do NOT change `adam_market_price_history_daily` or `adam_market_volume_history_daily` schemas — downstream reads from them unchanged
- Do NOT change opportunity generation logic
- All existing tests must pass after changes (run `cd backend && python -m pytest`)
- The ORM/SQLite fallback path in ingestion must still work for tests

## File ownership
- YOU OWN: history_ingestion.py, volume_ingestion.py, all_models.py, models/__init__.py, new migration
- SHARED: service.py (only touch _sync_adam_regional_price_history, _sync_adam_regional_volume_history, _clear_adam4eve_data, _history_sync_workset)
- SHARED: test files

# Roadmap (Completed)
- Analysis of current bottlenecks complete

# Roadmap (Upcoming)
- Create Alembic migration + new models
- Rewrite history_ingestion.py
- Rewrite volume_ingestion.py  
- Update service.py sync methods
- Update tests
- Run full test suite

# Backlog
- [x] Create Alembic migration: add adam_price_history_stage + adam_volume_history_stage, drop raw tables
- [x] Add new Table objects in all_models.py (AdamPriceHistoryStage + AdamVolumeHistoryStage added; Raw objects retained until ingestion rewrite removes them)
- [ ] Rewrite history_ingestion.py: load_csv_to_stage + populate_daily_from_stage + stage_has_export_key; remove AdamMarketPriceHistoryRaw from all_models + __init__ <- current
- [ ] Rewrite volume_ingestion.py: same pattern
- [ ] Update service.py: _sync_adam_regional_price_history loop → stage then populate, same for volume
- [ ] Update _clear_adam4eve_data to clear stage tables
- [ ] Update test_adam4eve_ingestion.py for new API
- [ ] Update test_volume_history_models.py: remove raw model tests, add stage model tests
- [ ] Run full test suite: cd backend && python -m pytest
- [ ] Commit with descriptive message
