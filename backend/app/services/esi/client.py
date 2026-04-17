import base64
import json
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
EVE_SSO_TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"

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


class EsiCharacterAssetRecord(TypedDict):
    type_id: int
    quantity: int
    location_id: int | None
    location_name: str | None


class EsiCharacterOrderRecord(TypedDict):
    order_id: int
    type_id: int
    location_id: int | None
    volume_remain: int
    is_buy_order: bool
    price: float | None
    issued: str | None
    duration: int | None


class EsiAccessibleStructureRecord(TypedDict):
    structure_id: int
    structure_name: str
    system_name: str | None
    region_name: str | None
    confidence_score: float
    polling_tier: str


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

    def exchange_code(self, code: str, *, code_verifier: str | None = None) -> dict:
        """Exchange an authorization code for access/refresh tokens via EVE SSO (PKCE)."""
        settings = get_settings()
        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.esi_client_id,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        else:
            data["client_secret"] = settings.esi_client_secret
        response = httpx.post(
            EVE_SSO_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
        if not response.is_success:
            print(f"SSO TOKEN EXCHANGE FAILED: {response.status_code} {response.text[:500]}", flush=True)
        response.raise_for_status()
        data = response.json()
        expires_in = int(data.get("expires_in", 1199))
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        # CCP PKCE flow: scopes may be in token response or in the JWT payload
        scopes_str = data.get("scope", "")
        if not scopes_str:
            try:
                jwt_payload = self._decode_jwt_payload(data["access_token"])
                scp = jwt_payload.get("scp", [])
                scopes_str = " ".join(scp) if isinstance(scp, list) else str(scp)
            except Exception:
                pass

        return {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_at": expires_at.isoformat(),
            "scopes": scopes_str.split() if scopes_str else [],
        }

    def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token via EVE SSO."""
        settings = get_settings()
        response = httpx.post(
            EVE_SSO_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.esi_client_id,
                "client_secret": settings.esi_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        expires_in = int(data.get("expires_in", 1199))
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", refresh_token),
            "expires_at": expires_at.isoformat(),
        }

    @staticmethod
    def _decode_jwt_payload(token: str) -> dict:
        """Decode the payload of an EVE SSO JWT without verification (ESI validates it)."""
        parts = token.split(".")
        if len(parts) < 2:
            raise ValueError("Invalid JWT format")
        payload_b64 = parts[1]
        # Fix padding
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))

    def fetch_character_identity(self, access_token: str) -> dict:
        """Extract character identity from the JWT and fetch corporation from ESI."""
        jwt_payload = self._decode_jwt_payload(access_token)
        # EVE SSO JWT subject format: "CHARACTER:EVE:<character_id>"
        sub = jwt_payload.get("sub", "")
        character_id = int(sub.split(":")[-1])
        character_name = jwt_payload.get("name", "Unknown")

        # Fetch corporation info from ESI
        corporation_name = None
        try:
            with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=15.0) as client:
                char_response = self._request_with_rate_limit(client, "GET", f"/characters/{character_id}/")
                char_data = char_response.json()
                corp_id = char_data.get("corporation_id")
                if corp_id:
                    corp_response = self._request_with_rate_limit(client, "GET", f"/corporations/{corp_id}/")
                    corp_data = corp_response.json()
                    corporation_name = corp_data.get("name")
        except Exception:
            logger.warning("Failed to fetch corporation for character %d", character_id)

        return {
            "character_id": character_id,
            "character_name": character_name,
            "corporation_name": corporation_name,
        }

    def fetch_character_assets(self, access_token: str) -> list[EsiCharacterAssetRecord]:
        """Fetch all character assets from ESI (paginated)."""
        character_id = self._character_id_from_token(access_token)
        assets: list[EsiCharacterAssetRecord] = []
        with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            first_response = self._authenticated_request(
                client, "GET", f"/characters/{character_id}/assets/",
                access_token=access_token, params={"page": 1},
            )
            if first_response.status_code == 304:
                return assets
            total_pages = int(first_response.headers.get("X-Pages", "1"))
            assets.extend(self._parse_asset_records(first_response.json()))
            for page in range(2, total_pages + 1):
                page_response = self._authenticated_request(
                    client, "GET", f"/characters/{character_id}/assets/",
                    access_token=access_token, params={"page": page},
                )
                if page_response.status_code != 304:
                    assets.extend(self._parse_asset_records(page_response.json()))
        logger.info("Fetched %d asset records for character %d", len(assets), character_id)
        return assets

    def _parse_asset_records(self, payload: object) -> list[EsiCharacterAssetRecord]:
        if not isinstance(payload, list):
            return []
        records: list[EsiCharacterAssetRecord] = []
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            records.append({
                "type_id": int(entry.get("type_id", 0)),
                "quantity": int(entry.get("quantity", 0)),
                "location_id": entry.get("location_id"),
                "location_name": None,
            })
        return records

    def fetch_character_orders(self, access_token: str) -> list[EsiCharacterOrderRecord]:
        """Fetch all active character orders from ESI."""
        character_id = self._character_id_from_token(access_token)
        with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            response = self._authenticated_request(
                client, "GET", f"/characters/{character_id}/orders/",
                access_token=access_token,
            )
            if response.status_code == 304:
                return []
            payload = response.json()
            if not isinstance(payload, list):
                return []
            orders: list[EsiCharacterOrderRecord] = []
            for entry in payload:
                if not isinstance(entry, dict):
                    continue
                orders.append({
                    "order_id": int(entry.get("order_id", 0)),
                    "type_id": int(entry.get("type_id", 0)),
                    "location_id": entry.get("location_id"),
                    "volume_remain": int(entry.get("volume_remain", 0)),
                    "is_buy_order": bool(entry.get("is_buy_order", False)),
                    "price": float(entry["price"]) if entry.get("price") is not None else None,
                    "issued": entry.get("issued"),
                    "duration": int(entry["duration"]) if entry.get("duration") is not None else None,
                })
            logger.info("Fetched %d orders for character %d", len(orders), character_id)
            return orders

    def fetch_accessible_structures(self, access_token: str) -> list[EsiAccessibleStructureRecord]:
        """Discover player-owned structures the character can access.

        Strategy: collect unique location_ids from character assets and orders that
        look like structure IDs (> 1_000_000_000_000), then resolve each via
        /universe/structures/{id}/ which requires the character's token.
        """
        character_id = self._character_id_from_token(access_token)
        structure_ids: set[int] = set()

        # Collect structure IDs from assets — only location_type="station" with ID > 1T
        # (location_type="item" means the item is inside a ship/container, not a structure)
        try:
            with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
                page = 1
                while True:
                    resp = self._authenticated_request(
                        client, "GET", f"/characters/{character_id}/assets/",
                        access_token=access_token, params={"page": page},
                    )
                    if resp.status_code == 304:
                        break
                    items = resp.json()
                    if not isinstance(items, list) or not items:
                        break
                    for item in items:
                        loc_type = item.get("location_type", "")
                        loc_id = item.get("location_id")
                        if loc_type == "station" and isinstance(loc_id, int) and loc_id > 1_000_000_000_000:
                            structure_ids.add(loc_id)
                    total_pages = int(resp.headers.get("X-Pages", "1"))
                    if page >= total_pages:
                        break
                    page += 1
        except Exception:
            logger.warning("Failed to scan assets for structures (character %d)", character_id)

        # Collect structure IDs from active orders (order location_id is always the station/structure)
        try:
            with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
                resp = self._authenticated_request(
                    client, "GET", f"/characters/{character_id}/orders/",
                    access_token=access_token,
                )
                if resp.status_code != 304:
                    orders = resp.json()
                    if isinstance(orders, list):
                        for order in orders:
                            loc_id = order.get("location_id")
                            if isinstance(loc_id, int) and loc_id > 1_000_000_000_000:
                                structure_ids.add(loc_id)
        except Exception:
            logger.warning("Failed to scan orders for structures (character %d)", character_id)

        logger.info("Found %d candidate structure IDs for character %d", len(structure_ids), character_id)

        # Resolve each structure via authenticated ESI endpoint
        records: list[EsiAccessibleStructureRecord] = []
        # Cache system_id -> (system_name, region_name)
        system_cache: dict[int, tuple[str | None, str | None]] = {}
        with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            for sid in sorted(structure_ids):
                try:
                    resp = self._authenticated_request(
                        client, "GET", f"/universe/structures/{sid}/",
                        access_token=access_token,
                    )
                    if resp.status_code in (304, 403, 404):
                        continue
                    data = resp.json()
                    structure_name = data.get("name", f"Structure {sid}")
                    solar_system_id = data.get("solar_system_id")

                    system_name: str | None = None
                    region_name: str | None = None
                    if solar_system_id and solar_system_id not in system_cache:
                        try:
                            sys_resp = self._request_with_rate_limit(client, "GET", f"/universe/systems/{solar_system_id}/")
                            sys_data = sys_resp.json()
                            s_name = sys_data.get("name")
                            constellation_id = sys_data.get("constellation_id")
                            r_name: str | None = None
                            if constellation_id:
                                con_resp = self._request_with_rate_limit(client, "GET", f"/universe/constellations/{constellation_id}/")
                                con_data = con_resp.json()
                                region_id = con_data.get("region_id")
                                if region_id:
                                    reg_resp = self._request_with_rate_limit(client, "GET", f"/universe/regions/{region_id}/")
                                    r_name = reg_resp.json().get("name")
                            system_cache[solar_system_id] = (s_name, r_name)
                        except Exception:
                            system_cache[solar_system_id] = (None, None)

                    if solar_system_id and solar_system_id in system_cache:
                        system_name, region_name = system_cache[solar_system_id]

                    records.append({
                        "structure_id": sid,
                        "structure_name": structure_name,
                        "system_name": system_name,
                        "region_name": region_name,
                        "confidence_score": 0.7,
                        "polling_tier": "user",
                    })
                except Exception:
                    logger.warning("Failed to resolve structure %d", sid)

        logger.info("Resolved %d accessible structures for character %d", len(records), character_id)
        return records

    def resolve_structure_info(self, access_token: str, structure_id: int) -> dict | None:
        """Resolve a structure's name and solar system via authenticated ESI call.

        Returns {"name": ..., "solar_system_id": ...} or None on failure/403.
        """
        try:
            with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=15.0) as client:
                resp = self._authenticated_request(
                    client, "GET", f"/universe/structures/{structure_id}/",
                    access_token=access_token,
                )
                if resp.status_code in (304, 403, 404):
                    return None
                data = resp.json()
                return {
                    "name": data.get("name"),
                    "solar_system_id": data.get("solar_system_id"),
                    "type_id": data.get("type_id"),
                }
        except Exception:
            return None

    def _character_id_from_token(self, access_token: str) -> int:
        """Extract character ID from an EVE SSO JWT access token."""
        jwt_payload = self._decode_jwt_payload(access_token)
        sub = jwt_payload.get("sub", "")
        return int(sub.split(":")[-1])

    def _authenticated_request(
        self,
        client: httpx.Client,
        method: str,
        url: str,
        *,
        access_token: str,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an authenticated ESI request with rate-limit tracking."""
        state = self.rate_limit_state

        if state.should_backoff():
            wait = state.backoff_seconds()
            logger.warning("ESI error limit low (%d remain), backing off %.1fs", state.error_limit_remain, wait)
            time.sleep(wait)

        headers: dict[str, str] = {"Authorization": f"Bearer {access_token}"}
        cache_key = f"{method}:{url}:{params}"
        etag = self._etag_cache.get(cache_key)
        if etag:
            headers["If-None-Match"] = etag

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            response = client.request(method, url, params=params, headers=headers)
            state.update_from_headers(response.headers)

            new_etag = response.headers.get("ETag")
            if new_etag:
                self._etag_cache[cache_key] = new_etag

            if response.status_code == 304:
                state.cached_responses += 1
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
        raise RuntimeError("ESI authenticated request failed after retries")

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
