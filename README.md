# EVE Station Trader

`eve-station-trader` is now a small local web app plus a Python backend that downloads EVE Online market orders, filters them to a source station and a destination station, and ranks items that look attractive for hub-to-hub hauling and day trading.

The first version is intentionally simple:

- Uses official ESI region market order pages as the core bulk feed.
- Runs as a local browser + server app with no third-party web framework required.
- Ships with the main empire trade hubs built in.
- Supports two strategies:
  - `instant`: buy from source sell orders, then dump into destination buy orders.
  - `relist`: buy from source sell orders, then relist against destination sell prices.
- Caches ESI responses locally so repeated runs do not hammer the API.

## Why this design

As of February 24, 2026, CCP rate-limits the ESI region market orders route and still expects clients to respect the 5-minute cache window. This app is designed around that by pulling the bulk order pages once per region and reusing a local cache.

Official references:

- [ESI X-Pages pagination](https://developers.eveonline.com/docs/services/esi/pagination/x-pages/)
- [Market order rate-limit rollout on February 24, 2026](https://developers.eveonline.com/blog/market-orders-rate-limit-rolls-out-on-february-24-2026)

## Quick start

1. Install Python 3.11+.
2. From the repo root, run:

```powershell
python -m pip install -e .
```

3. Set a descriptive User-Agent before hitting ESI:

```powershell
$env:EVE_STATION_TRADER_USER_AGENT = "eve-station-trader/0.1 (your-name-or-app-contact)"
```

4. Start the local web server:

```powershell
python -m eve_station_trader.web
```

5. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.
   The scanner lives at `/` and the ingestion/database page lives at `/ingestion`.

6. If you still want the CLI, it is still available:

```powershell
python -m eve_station_trader.cli --source-hub jita --destination-hub dodixie --format json
```

## Browser workflow

The browser app currently supports:

- Picking source and destination hubs.
- Choosing `instant` or `relist` mode.
- Adjusting min profit, min ROI, tax, broker fee, and result count.
- Forcing a fresh ESI pull when you want to bypass the local cache.
- Running a dedicated ingestion flow that stores market orders in a local SQLite database.

## Local database

The app now keeps a SQLite database at `.localdata/eve-station-trader.sqlite3`.

- The ingestion page can pull one hub region or all built-in hub regions.
- Each ingestion replaces the stored snapshot for that region with the latest market orders.
- The scanner prefers database-backed region data when it exists, so repeated analysis is faster and does not depend on a fresh ESI round trip.

## Custom stations

If you want to scan any station instead of the built-in hubs, pass region and location IDs:

```powershell
eve-station-trader `
  --source-region-id 10000002 `
  --source-location-id 60003760 `
  --destination-region-id 10000043 `
  --destination-location-id 60008494
```

## Current scoring model

Each candidate is ranked by estimated total profit, then ROI. The calculation currently uses:

- Best source sell price.
- Best destination buy price for `instant`, or best destination sell price for `relist`.
- Destination sales tax and optional destination broker fee.
- Available units at the relevant best-price levels.

This gives a useful day-trading baseline, but it is not yet a full EveGuru replacement. Notable next steps:

- Cargo-aware profit per m3 scoring using type volume data.
- Historical volume and turnover scoring.
- Route risk and jump-distance weighting.
- Wallet-size and buy-order budgeting.
- Multiple provider backends beyond ESI.

## Built-in hubs

- `jita`
- `amarr`
- `dodixie`
- `rens`
- `hek`
