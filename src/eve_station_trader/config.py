from __future__ import annotations

from pathlib import Path

from .models import Hub


DEFAULT_CACHE_DIR = Path(".cache") / "eve-station-trader"
DEFAULT_DB_PATH = Path(".localdata") / "eve-station-trader.sqlite3"
DEFAULT_CACHE_TTL_SECONDS = 300
DEFAULT_USER_AGENT = "eve-station-trader/0.1.0 (set EVE_STATION_TRADER_USER_AGENT)"
ESI_BASE_URL = "https://esi.evetech.net/latest"

BROKER_FEE_DEFAULT = 0.03
SALES_TAX_DEFAULT = 0.036
TOP_RESULTS_DEFAULT = 30

KNOWN_HUBS: dict[str, Hub] = {
    "jita": Hub(
        key="jita",
        name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
        region_id=10000002,
        location_id=60003760,
    ),
    "amarr": Hub(
        key="amarr",
        name="Amarr VIII (Oris) - Emperor Family Academy",
        region_id=10000043,
        location_id=60008494,
    ),
    "dodixie": Hub(
        key="dodixie",
        name="Dodixie IX - Moon 20 - Federation Navy Assembly Plant",
        region_id=10000032,
        location_id=60011866,
    ),
    "rens": Hub(
        key="rens",
        name="Rens VI - Moon 8 - Brutor Tribe Treasury",
        region_id=10000030,
        location_id=60004588,
    ),
    "hek": Hub(
        key="hek",
        name="Hek VIII - Moon 12 - Boundless Creation Factory",
        region_id=10000042,
        location_id=60005686,
    ),
}
