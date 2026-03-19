# Devlog

## 2026-03-19

### Summary

This project started as a greenfield EVE Online market scanner focused on finding items worth buying in one trade hub and moving to another for a higher sale price. The initial build was a Python CLI that pulled bulk market order pages from ESI, filtered them down to known trade hubs, and ranked arbitrage opportunities for `instant` and `relist` strategies.

### What was built

- Created a Python package with a reusable ESI client, local cache, analysis logic, and hub metadata.
- Added a CLI entrypoint for quick scans and JSON output.
- Converted the project into a local browser + server app so the workflow runs through a web UI instead of only the CLI.
- Added a reusable service layer that backs both the CLI and the web app.
- Added a local SQLite database at `.localdata/eve-station-trader.sqlite3` for storing ingested market snapshots.
- Added an ingestion page that can pull one hub region or all built-in hub regions from ESI into the local database.
- Updated scanning to prefer database-backed region data when available for faster repeated analysis.
- Added an ingestion progress bar backed by a lightweight in-memory job manager and polling API.

### App structure

- `src/eve_station_trader/esi.py`
  Handles ESI pagination and name resolution.
- `src/eve_station_trader/analysis.py`
  Computes best visible opportunities between hubs.
- `src/eve_station_trader/service.py`
  Shared application service for scans, caching, DB access, and name lookup.
- `src/eve_station_trader/db.py`
  SQLite persistence for market orders, ingestion runs, and item names.
- `src/eve_station_trader/ingestion.py`
  Ingestion workflow for region snapshots.
- `src/eve_station_trader/jobs.py`
  Background ingestion job tracking and progress state.
- `src/eve_station_trader/web.py`
  Local HTTP server and API routes.
- `src/eve_station_trader/web_static/`
  Browser UI for scanning and ingestion.

### Verification done

- Installed the package into the detected local Python environment.
- Verified the CLI help output.
- Verified the web app help output.
- Verified localhost health and ingestion status endpoints.
- Added and ran unit tests covering analysis logic, database behavior, and ingestion job progress.

### Current status

The app now supports:

- Browser-based scanning
- Browser-based ingestion into SQLite
- Cached and database-backed local analysis
- Progress reporting for ingestion jobs

### Good next steps

- Add a dedicated local search page over the SQLite database.
- Store more normalized market metadata for richer queries.
- Add cargo-volume, route distance, and turnover-aware scoring.
- Add item and hub filtering controls in the scanner UI.
