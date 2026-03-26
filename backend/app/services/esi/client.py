import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

import httpx

from app.core.config import get_settings
from app.repositories.seed_data import ItemSeed, RegionSeed, StationSeed, SystemSeed

logger = logging.getLogger(__name__)

ESI_BASE_URL = "https://esi.evetech.net/latest"

# Rate limit thresholds
ERROR_LIMIT_BACKOFF_THRESHOLD = 20
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0


@dataclass
class EsiRateLimitState:
    """Tracks ESI error-limit state from response headers."""

    error_limit_remain: int = 100
    error_limit_reset: int = 60
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_requests: int = 0
    cached_responses: int = 0
    error_limited_count: int = 0

    def update_from_headers(self, headers: httpx.Headers) -> None:
        self.total_requests += 1
        remain = headers.get("X-ESI-Error-Limit-Remain")
        reset = headers.get("X-ESI-Error-Limit-Reset")
        if remain is not None:
            self.error_limit_remain = int(remain)
        if reset is not None:
            self.error_limit_reset = int(reset)
        self.last_updated = datetime.now(UTC)

    def should_backoff(self) -> bool:
        return self.error_limit_remain < ERROR_LIMIT_BACKOFF_THRESHOLD

    def backoff_seconds(self) -> float:
        if not self.should_backoff():
            return 0.0
        return float(self.error_limit_reset)

    def to_dict(self) -> dict[str, object]:
        return {
            "error_limit_remain": self.error_limit_remain,
            "error_limit_reset": self.error_limit_reset,
            "last_updated": self.last_updated.isoformat(),
            "total_requests": self.total_requests,
            "cached_responses": self.cached_responses,
            "error_limited_count": self.error_limited_count,
        }


class EsiRegionalOrderRecord(TypedDict):
    order_id: int
    type_id: int
    location_id: int
    system_id: int
    is_buy_order: bool
    price: float
    volume_total: int
    volume_remain: int
    min_volume: int
    range: str
    issued: str
    duration: int


class EsiClient:
    # Shared rate limit state across all EsiClient instances
    rate_limit_state: EsiRateLimitState = EsiRateLimitState()

    def __init__(self) -> None:
        self.settings = get_settings()
        self._etag_cache: dict[str, str] = {}

    @classmethod
    def get_rate_limit_state(cls) -> EsiRateLimitState:
        return cls.rate_limit_state

    def get_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.settings.a4e_user_agent,
            "X-Compatibility-Date": self.settings.esi_compatibility_date,
        }

    def _request_with_rate_limit(
        self,
        client: httpx.Client,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an ESI request with rate-limit tracking, ETag support, and retry."""
        state = self.rate_limit_state

        # Pre-request backoff if near error limit
        if state.should_backoff():
            wait = state.backoff_seconds()
            logger.warning("ESI error limit low (%d remain), backing off %.1fs", state.error_limit_remain, wait)
            time.sleep(wait)

        headers: dict[str, str] = {}
        cache_key = f"{method}:{url}:{params}"
        etag = self._etag_cache.get(cache_key)
        if etag:
            headers["If-None-Match"] = etag

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            response = client.request(method, url, params=params, headers=headers)
            state.update_from_headers(response.headers)

            # ETag caching
            new_etag = response.headers.get("ETag")
            if new_etag:
                self._etag_cache[cache_key] = new_etag

            if response.status_code == 304:
                state.cached_responses += 1
                logger.debug("ESI cache hit (304) for %s", url)
                return response

            if response.status_code == 420:
                state.error_limited_count += 1
                backoff = INITIAL_BACKOFF_SECONDS * (2**attempt)
                logger.warning("ESI error limited (420), retry %d after %.1fs", attempt + 1, backoff)
                time.sleep(backoff)
                last_exc = httpx.HTTPStatusError(
                    f"ESI error limited: {response.status_code}",
                    request=response.request,
                    response=response,
                )
                continue

            if response.status_code >= 500:
                backoff = INITIAL_BACKOFF_SECONDS * (2**attempt)
                logger.warning("ESI server error (%d), retry %d after %.1fs", response.status_code, attempt + 1, backoff)
                time.sleep(backoff)
                last_exc = httpx.HTTPStatusError(
                    f"ESI server error: {response.status_code}",
                    request=response.request,
                    response=response,
                )
                continue

            response.raise_for_status()
            return response

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("ESI request failed after retries")

    def exchange_code(self, code: str) -> dict:
        # TODO: Implement real EVE SSO token exchange.
        del code
        return {
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=20)).isoformat(),
            "scopes": [],
        }

    def fetch_character_identity(self, access_token: str) -> dict:
        del access_token
        return {
            "character_id": 90000001,
            "character_name": "Demo Trader",
            "corporation_name": "Open Traders Union",
        }

    def fetch_universe_regions(self) -> list[RegionSeed]:
        with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            region_ids_response = self._request_with_rate_limit(client, "GET", "/universe/regions/")
            region_ids = self._require_integer_list(region_ids_response.json(), "region ids")

            regions: list[RegionSeed] = []
            for region_id in region_ids:
                region_response = self._request_with_rate_limit(client, "GET", f"/universe/regions/{region_id}/")
                payload = self._require_mapping(region_response.json(), "region detail")
                regions.append(RegionSeed(region_id=region_id, name=self._require_string(payload, "name")))
            return regions

    def fetch_universe_systems(self) -> list[SystemSeed]:
        with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            system_ids_response = self._request_with_rate_limit(client, "GET", "/universe/systems/")
            system_ids = self._require_integer_list(system_ids_response.json(), "system ids")

            constellation_region_ids: dict[int, int] = {}
            systems: list[SystemSeed] = []
            for system_id in system_ids:
                system_response = self._request_with_rate_limit(client, "GET", f"/universe/systems/{system_id}/")
                payload = self._require_mapping(system_response.json(), "system detail")
                constellation_id = self._require_integer(payload, "constellation_id")
                if constellation_id not in constellation_region_ids:
                    constellation_response = self._request_with_rate_limit(
                        client, "GET", f"/universe/constellations/{constellation_id}/"
                    )
                    constellation_payload = self._require_mapping(
                        constellation_response.json(),
                        "constellation detail",
                    )
                    constellation_region_ids[constellation_id] = self._require_integer(
                        constellation_payload,
                        "region_id",
                    )

                systems.append(
                    SystemSeed(
                        system_id=system_id,
                        region_id=constellation_region_ids[constellation_id],
                        name=self._require_string(payload, "name"),
                        security_status=self._require_numeric(payload, "security_status"),
                    )
                )
            return systems

    def fetch_universe_items(self) -> list[ItemSeed]:
        with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            first_response = self._request_with_rate_limit(client, "GET", "/universe/types/", params={"page": 1})
            type_ids = self._require_integer_list(first_response.json(), "type ids")
            total_pages = int(first_response.headers.get("X-Pages", "1"))
            for page in range(2, total_pages + 1):
                page_response = self._request_with_rate_limit(client, "GET", "/universe/types/", params={"page": page})
                type_ids.extend(self._require_integer_list(page_response.json(), "type ids"))

            group_cache: dict[int, tuple[str, str | None]] = {}
            items: list[ItemSeed] = []
            for type_id in type_ids:
                items.append(self.fetch_universe_item(type_id, client=client, group_cache=group_cache))
            return items

    def fetch_universe_item(
        self,
        type_id: int,
        *,
        client: httpx.Client | None = None,
        group_cache: dict[int, tuple[str, str | None]] | None = None,
    ) -> ItemSeed:
        if client is None:
            with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as managed_client:
                return self.fetch_universe_item(type_id, client=managed_client, group_cache=group_cache)

        response = self._request_with_rate_limit(client, "GET", f"/universe/types/{type_id}/")
        payload = self._require_mapping(response.json(), "type detail")
        group_id = payload.get("group_id")
        group_name: str | None = None
        category_name: str | None = None
        if isinstance(group_id, int):
            group_name, category_name = self._resolve_group(client, group_id, group_cache or {})
        return ItemSeed(
            type_id=type_id,
            name=self._require_string(payload, "name"),
            volume_m3=self._require_numeric(payload, "volume"),
            group_name=group_name,
            category_name=category_name,
        )

    def _resolve_group(
        self,
        client: httpx.Client,
        group_id: int,
        cache: dict[int, tuple[str, str | None]],
    ) -> tuple[str, str | None]:
        if group_id in cache:
            return cache[group_id]
        try:
            group_response = self._request_with_rate_limit(client, "GET", f"/universe/groups/{group_id}/")
            group_payload = self._require_mapping(group_response.json(), "group detail")
            group_name = self._require_string(group_payload, "name")
            category_id = group_payload.get("category_id")
            category_name: str | None = None
            if isinstance(category_id, int):
                category_name = self._resolve_category(client, category_id)
            cache[group_id] = (group_name, category_name)
            return group_name, category_name
        except Exception:
            logger.warning("Failed to resolve group %d, using fallback", group_id)
            cache[group_id] = (str(group_id), None)
            return str(group_id), None

    def _resolve_category(self, client: httpx.Client, category_id: int) -> str | None:
        try:
            response = self._request_with_rate_limit(client, "GET", f"/universe/categories/{category_id}/")
            payload = self._require_mapping(response.json(), "category detail")
            return self._require_string(payload, "name")
        except Exception:
            logger.warning("Failed to resolve category %d", category_id)
            return None

    def fetch_station(self, station_id: int, *, client: httpx.Client | None = None) -> StationSeed:
        if client is None:
            with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as managed_client:
                return self.fetch_station(station_id, client=managed_client)

        response = self._request_with_rate_limit(client, "GET", f"/universe/stations/{station_id}/")
        payload = self._require_mapping(response.json(), "station detail")
        return StationSeed(
            station_id=station_id,
            system_id=self._require_integer(payload, "system_id"),
            region_id=0,
            name=self._require_string(payload, "name"),
        )

    def fetch_regional_orders(self, region_id: int) -> list[EsiRegionalOrderRecord]:
        with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            first_response = self._request_with_rate_limit(
                client, "GET", f"/markets/{region_id}/orders/", params={"order_type": "all", "page": 1}
            )
            orders = self._parse_regional_orders_payload(first_response.json())
            total_pages = int(first_response.headers.get("X-Pages", "1"))
            for page in range(2, total_pages + 1):
                page_response = self._request_with_rate_limit(
                    client, "GET", f"/markets/{region_id}/orders/", params={"order_type": "all", "page": page}
                )
                orders.extend(self._parse_regional_orders_payload(page_response.json()))
            return orders

    def _parse_regional_orders_payload(self, payload: object) -> list[EsiRegionalOrderRecord]:
        if not isinstance(payload, list):
            raise ValueError("ESI regional orders response must be a list of rows.")
        return [self._normalize_regional_order_row(entry) for entry in payload]

    def _normalize_regional_order_row(self, entry: object) -> EsiRegionalOrderRecord:
        payload = self._require_mapping(entry, "regional order row")
        return {
            "order_id": self._require_integer(payload, "order_id"),
            "type_id": self._require_integer(payload, "type_id"),
            "location_id": self._require_integer(payload, "location_id"),
            "system_id": self._require_integer(payload, "system_id"),
            "is_buy_order": self._require_boolean(payload, "is_buy_order"),
            "price": self._require_numeric(payload, "price"),
            "volume_total": self._require_integer(payload, "volume_total"),
            "volume_remain": self._require_integer(payload, "volume_remain"),
            "min_volume": self._require_integer(payload, "min_volume"),
            "range": self._require_string(payload, "range"),
            "issued": self._normalize_datetime(payload.get("issued")),
            "duration": self._require_integer(payload, "duration"),
        }

    def _normalize_datetime(self, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("ESI rows must include an ISO datetime string.")
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).isoformat()

    @staticmethod
    def _require_numeric(entry: dict[str, Any], key: str) -> float:
        value = entry.get(key)
        if not isinstance(value, (int, float)):
            raise ValueError(f"ESI market history rows must include numeric '{key}'.")
        return float(value)

    @staticmethod
    def _require_integer(entry: dict[str, Any], key: str) -> int:
        value = entry.get(key)
        if not isinstance(value, int):
            raise ValueError(f"ESI market history rows must include integer '{key}'.")
        return value

    @staticmethod
    def _require_boolean(entry: Mapping[str, object], key: str) -> bool:
        value = entry.get(key)
        if not isinstance(value, bool):
            raise ValueError(f"ESI rows must include boolean '{key}'.")
        return value

    @staticmethod
    def _require_string(entry: Mapping[str, object], key: str) -> str:
        value = entry.get(key)
        if not isinstance(value, str):
            raise ValueError(f"ESI rows must include string '{key}'.")
        return value

    @staticmethod
    def _require_mapping(payload: object, label: str) -> dict[str, object]:
        if not isinstance(payload, dict):
            raise ValueError(f"ESI {label} must be an object.")
        return payload

    @staticmethod
    def _require_integer_list(payload: object, label: str) -> list[int]:
        if not isinstance(payload, list) or any(not isinstance(entry, int) for entry in payload):
            raise ValueError(f"ESI {label} response must be a list of integers.")
        return list(payload)
