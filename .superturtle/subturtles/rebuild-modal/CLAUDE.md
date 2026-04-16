# Current task

Create RebuildProgressModal.tsx: polls /sync/jobs for job_type=target_rebuild, shows phase+progress bar, green success, red error, Close button.

# End goal with specs

When user clicks "Rebuild Selected Target": modal opens immediately, polls /sync/jobs every 1s for a target_rebuild job, shows live progress phase + bar, then shows green success state when done. Close button required (no auto-dismiss).

Backend: wrap refresh_opportunities in a SyncJobRun lifecycle using isolated sessions so the running job is visible to frontend polls. job_type="target_rebuild", status="running" on start, update to "success"/"error" on finish.

Frontend: new RebuildProgressModal component that polls /sync/jobs, filters for job_type === "target_rebuild" with started_at >= rebuildStartedAt. Shows spinner if no job yet, progress bar + phase text when job found (reuse .sync-progress / .sync-progress-fill CSS classes), green banner on isComplete, red message on error. TradePage wires it in: open modal before POST, set isComplete=true when POST returns, pass refreshError as error prop.

Modal overlay pattern: similar to ShoppingListOverlay. Progress bar pattern: same CSS as StatusCards.tsx.

Acceptance: clicking button opens modal, modal shows live phase text, green success when done, error on failure, Close button works. tsc --noEmit passes, pytest passes.

# Roadmap (Completed)

- Explored sync infrastructure and identified the gap (no SyncJobRun tracking on /opportunities/refresh)

# Roadmap (Upcoming)

- Backend: add SyncJobRun lifecycle to refresh_opportunities
- Frontend: create RebuildProgressModal and wire into TradePage

# Backlog

- [x] Read trade_repository.py refresh_opportunities (lines 1020-1079) and SyncJobRun model (all_models.py ~532)
- [x] Read ShoppingListOverlay.tsx and StatusCards.tsx for modal/progress bar patterns
- [x] Backend: wrap refresh_opportunities body in SyncJobRun create/update/finish using isolated sessions (separate session_factory() calls, each committed immediately)
- [ ] Frontend: create frontend/src/components/RebuildProgressModal.tsx (polls /sync/jobs, shows phase+bar, green success, red error, Close button) <- current
- [ ] Frontend: update TradePage.tsx handleRebuildSelectedTarget to open modal before POST and set isComplete on success
- [ ] Run cd frontend && npx tsc --noEmit and fix any TS errors
- [ ] Run cd backend && python -m pytest and confirm passes
- [ ] Commit all changes with descriptive message
