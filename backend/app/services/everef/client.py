import bz2
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

EVEREF_HISTORY_BASE_URL = "https://data.everef.net/market-history"
TOTALS_URL = f"{EVEREF_HISTORY_BASE_URL}/totals.json"


def fetch_totals_json() -> dict[str, dict[str, Any]]:
    response = httpx.get(TOTALS_URL, timeout=120.0, follow_redirects=True)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Unexpected totals.json payload; expected a JSON object.")
    return {
        str(key): value
        for key, value in payload.items()
        if isinstance(value, dict)
    }


def get_available_dates(days_back: int = 30) -> list[date]:
    if days_back <= 0:
        return []

    today = date.today()
    start = today - timedelta(days=days_back)
    return [start + timedelta(days=offset) for offset in range(days_back)]


def download_history_file(target_date: date, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)

    year = target_date.strftime("%Y")
    filename = f"market-history-{target_date.isoformat()}.csv"
    csv_path = cache_dir / filename
    archive_path = cache_dir / f"{filename}.bz2"
    url = f"{EVEREF_HISTORY_BASE_URL}/{year}/{filename}.bz2"

    with httpx.stream("GET", url, timeout=120.0, follow_redirects=True) as response:
        response.raise_for_status()
        decompressor = bz2.BZ2Decompressor()
        with archive_path.open("wb") as compressed_handle:
            with csv_path.open("wb") as csv_handle:
                for chunk in response.iter_bytes():
                    if not chunk:
                        continue
                    compressed_handle.write(chunk)
                    csv_chunk = decompressor.decompress(chunk)
                    if csv_chunk:
                        csv_handle.write(csv_chunk)

    return csv_path
