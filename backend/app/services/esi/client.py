from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any, TypedDict

import httpx

from app.core.config import get_settings
from app.repositories.seed_data import ItemSeed, RegionSeed, StationSeed, SystemSeed
from app.services.esi.history_ingestion import EsiRegionalHistoryRecord


ESI_BASE_URL = "https://esi.evetech.net/latest"


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
    def __init__(self) -> None:
        self.settings = get_settings()

    def get_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.settings.a4e_user_agent,
            "X-Compatibility-Date": self.settings.esi_compatibility_date,
        }

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

    def fetch_regional_history(self, region_id: int, type_ids: Iterable[int]) -> list[EsiRegionalHistoryRecord]:
        requested_type_ids = tuple(type_ids)
        if not requested_type_ids:
            return []

        history: list[EsiRegionalHistoryRecord] = []
        with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            for type_id in requested_type_ids:
                response = client.get(f"/markets/{region_id}/history/", params={"type_id": type_id})
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                history.extend(self._parse_history_payload(type_id, response.json()))
        return history

    def fetch_universe_regions(self) -> list[RegionSeed]:
        with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            region_ids_response = client.get("/universe/regions/")
            region_ids_response.raise_for_status()
            region_ids = self._require_integer_list(region_ids_response.json(), "region ids")

            regions: list[RegionSeed] = []
            for region_id in region_ids:
                region_response = client.get(f"/universe/regions/{region_id}/")
                region_response.raise_for_status()
                payload = self._require_mapping(region_response.json(), "region detail")
                regions.append(RegionSeed(region_id=region_id, name=self._require_string(payload, "name")))
            return regions

    def fetch_universe_systems(self) -> list[SystemSeed]:
        with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            system_ids_response = client.get("/universe/systems/")
            system_ids_response.raise_for_status()
            system_ids = self._require_integer_list(system_ids_response.json(), "system ids")

            constellation_region_ids: dict[int, int] = {}
            systems: list[SystemSeed] = []
            for system_id in system_ids:
                system_response = client.get(f"/universe/systems/{system_id}/")
                system_response.raise_for_status()
                payload = self._require_mapping(system_response.json(), "system detail")
                constellation_id = self._require_integer(payload, "constellation_id")
                if constellation_id not in constellation_region_ids:
                    constellation_response = client.get(f"/universe/constellations/{constellation_id}/")
                    constellation_response.raise_for_status()
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
            first_response = client.get("/universe/types/", params={"page": 1})
            first_response.raise_for_status()
            type_ids = self._require_integer_list(first_response.json(), "type ids")
            total_pages = int(first_response.headers.get("X-Pages", "1"))
            for page in range(2, total_pages + 1):
                page_response = client.get("/universe/types/", params={"page": page})
                page_response.raise_for_status()
                type_ids.extend(self._require_integer_list(page_response.json(), "type ids"))

            items: list[ItemSeed] = []
            for type_id in type_ids:
                items.append(self.fetch_universe_item(type_id, client=client))
            return items

    def fetch_universe_item(self, type_id: int, *, client: httpx.Client | None = None) -> ItemSeed:
        if client is None:
            with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as managed_client:
                return self.fetch_universe_item(type_id, client=managed_client)

        response = client.get(f"/universe/types/{type_id}/")
        response.raise_for_status()
        payload = self._require_mapping(response.json(), "type detail")
        return ItemSeed(
            type_id=type_id,
            name=self._require_string(payload, "name"),
            volume_m3=self._require_numeric(payload, "volume"),
            group_name=str(payload.get("group_id")) if isinstance(payload.get("group_id"), int) else None,
            category_name=None,
        )

    def fetch_station(self, station_id: int, *, client: httpx.Client | None = None) -> StationSeed:
        if client is None:
            with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as managed_client:
                return self.fetch_station(station_id, client=managed_client)

        response = client.get(f"/universe/stations/{station_id}/")
        response.raise_for_status()
        payload = self._require_mapping(response.json(), "station detail")
        return StationSeed(
            station_id=station_id,
            system_id=self._require_integer(payload, "system_id"),
            region_id=0,
            name=self._require_string(payload, "name"),
        )

    def fetch_regional_orders(self, region_id: int) -> list[EsiRegionalOrderRecord]:
        with httpx.Client(base_url=ESI_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            first_response = client.get(f"/markets/{region_id}/orders/", params={"order_type": "all", "page": 1})
            first_response.raise_for_status()
            orders = self._parse_regional_orders_payload(first_response.json())
            total_pages = int(first_response.headers.get("X-Pages", "1"))
            for page in range(2, total_pages + 1):
                page_response = client.get(
                    f"/markets/{region_id}/orders/",
                    params={"order_type": "all", "page": page},
                )
                page_response.raise_for_status()
                orders.extend(self._parse_regional_orders_payload(page_response.json()))
            return orders

    def _parse_history_payload(
        self,
        type_id: int,
        payload: object,
    ) -> list[EsiRegionalHistoryRecord]:
        if not isinstance(payload, list):
            raise ValueError("ESI market history response must be a list of rows.")

        rows: list[EsiRegionalHistoryRecord] = []
        for entry in payload:
            rows.append(self._normalize_history_entry(type_id, entry))
        return rows

    def _normalize_history_entry(
        self,
        type_id: int,
        entry: object,
    ) -> EsiRegionalHistoryRecord:
        if not isinstance(entry, dict):
            raise ValueError("ESI market history rows must be objects.")

        normalized_date = self._normalize_history_date(entry.get("date"))
        return {
            "type_id": type_id,
            "date": normalized_date,
            "average": self._require_numeric(entry, "average"),
            "highest": self._require_numeric(entry, "highest"),
            "lowest": self._require_numeric(entry, "lowest"),
            "order_count": self._require_integer(entry, "order_count"),
            "volume": self._require_integer(entry, "volume"),
        }

    def _normalize_history_date(self, value: object) -> str:
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, str):
            return date.fromisoformat(value).isoformat()
        raise ValueError("ESI market history rows must include an ISO date string.")

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
