# Current task

Modify generation.py lines 424-427: replace hard skip with 3-tier fallback (live ESI → yesterday → period_avg), track price source, include in row dict.

# End goal with specs

Items with demand but no live ESI sell orders should still generate opportunities using historical prices from MarketPricePeriod. Track which price source was used via a new `target_price_source` column.

## Fallback chain
1. Live ESI min sell price (`target_min_price_by_type`) → `target_price_source = "live"`
2. Yesterday's avg price (`MarketPricePeriod.current_price`) → `target_price_source = "yesterday"`
3. Period avg price (`MarketPricePeriod.period_avg_price`) → `target_price_source = "period_avg"`
4. If all three are None → skip (same as current)

## File ownership
- backend/app/services/opportunities/generation.py — modify opportunity loop
- backend/app/models/all_models.py — add column to OpportunityItem
- backend/alembic/versions/ — new migration
- backend/app/api/schemas/trade.py — expose field
- frontend/src/types/trade.ts — add type
- frontend/src/api/trade.ts — add type
- backend/tests/services/test_opportunity_generation.py — new tests

## Key context
- `generation.py` lines 424-427: currently `target_now_price = target_min_price_by_type.get(type_id)` then `if target_now_price is None: continue` — this is the hard skip to replace
- `target_prices_by_type` (dict[int, MarketPricePeriod]) is ALREADY loaded at lines 245-258, keyed by type_id
- `MarketPricePeriod.current_price` = most recent EveRef history day average (= yesterday due to 1-day lag)
- `MarketPricePeriod.period_avg_price` = average across the 14-day window
- `target_price` variable at line 424 already holds the MarketPricePeriod for the type_id
- When using fallback price, `target_now_profit` becomes an estimate (expected, acceptable)
- OpportunityItem model is at line 466 of all_models.py

## Constraints
- Do NOT change opportunity generation logic beyond the price fallback (no demand changes, no source price changes)
- Do NOT alter existing column types or remove columns
- New migration must be backward-compatible (server_default='live')
- All existing tests must continue to pass

## Verification
After implementation, run this SQL to compare opportunity counts before/after:
```sql
SELECT COUNT(*) as total_items, COUNT(DISTINCT type_id) as unique_items FROM opportunity_items;
SELECT target_price_source, COUNT(*) FROM opportunity_items GROUP BY target_price_source;
```

# Roadmap (Completed)
- [x] Identified gap: items skipped when no live ESI sell orders

# Roadmap (Upcoming)
- [ ] Implement price fallback and verify opportunity count increase

# Backlog
- [x] Add `target_price_source` column to OpportunityItem model in all_models.py (String(16), default="live")
- [x] Create Alembic migration 20260416_0020 adding the column with server_default='live'
- [x] Apply migration with `cd backend && alembic upgrade head`
- [ ] Modify generation.py lines 424-427: replace hard skip with 3-tier fallback, track price source, include in row dict <- current
- [ ] Expose target_price_source in API schema (trade.py) and frontend types (trade.ts, trade.ts)
- [ ] Add tests: live price used when available, yesterday fallback, period_avg fallback, skip when all None
- [ ] Run full test suite: `cd backend && python -m pytest`
- [ ] Trigger opportunity rebuild and verify counts increased via SQL
- [ ] Commit with descriptive message
