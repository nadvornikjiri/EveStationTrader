# Project Instructions

This project uses Super Turtle for autonomous coding via Telegram.

## Current task
Data coverage gap fixes complete. Pipeline now captures all legitimately tradeable sell-to-sell items.

## Backlog
- [x] Audit data coverage for the opportunity pipeline
- [x] Gap 1: `npc_station_demand_period` not flowing to `market_demand_resolved` (+8,213 rows, +4,177 opportunity items)
- [x] Gap 2: 797 items with regional trade volume but zero demand record (history_based_pairs third source added)
- [x] Gap 4: EveRef history staleness — 1-day lag is inherent (EveRef lags CCP by 1 day); scheduler fixed to cron 08:00 UTC to prevent drift

## Ideas (not planned)
- Buy-order-side opportunities (source sell → target buy order = instant sell; 300k buy orders captured but unused) — deferred, not in scope for now

## Tech stack
- Backend: Python (FastAPI + SQLAlchemy + psycopg), PostgreSQL 16
- Frontend: React/TypeScript, Vite, port 5173
- Worker: APScheduler (opportunity rebuild every 10m, everef history sync daily at 08:00 UTC)
- Docker Compose dev stack (backend :8000, frontend :5173, postgres :5432, redis :6379)
- Run tests: `cd backend && python -m pytest`
- Apply migrations: `cd backend && alembic upgrade head`

## Constraints
- Do NOT change opportunity generation logic (generation.py) without explicit approval
- Do NOT alter existing `DemandSource` enum values (only add new ones)
- All demand resolution changes must be backward-compatible (existing rows must not be degraded)
- No direct DB schema changes without a new Alembic migration
- After any frontend code change, always run `docker compose restart frontend` so the changes take effect

## Notes

### Key DB stats (as of 2026-04-15)
- ESI market orders: Jita 16,594 items / Amarr 11,638 / Dodixie 9,182 / Hek 7,497 / Rens 6,775 (sell-side)
- market_demand_resolved: 129,399 rows, 15,927 items, period_days=14 only
- npc_station_demand_period: Jita 13,904 / Amarr 8,430 / Dodixie 6,229 / Hek 4,514 / Rens 3,836 items (period_days=14)
- opportunity_items: ~134k rows across all source/target pairs
- Analysis period: 14 days (user_settings defaults)
- EveRef history is expected to lag CCP by 1 day; `get_available_dates(...)` correctly excludes today.
- The transient 2-day gap came from scheduler drift when the worker's 24-hour interval ran before EveRef published the next file.
- Worker sync now runs `everef_history_sync` daily at 08:00 UTC to avoid drift-induced 2-day gaps.
