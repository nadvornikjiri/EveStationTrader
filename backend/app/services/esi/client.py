from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.esi.history_ingestion import EsiRegionalHistoryRecord


ESI_BASE_URL = "https://esi.evetech.net/latest"


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
                response.raise_for_status()
                history.extend(self._parse_history_payload(type_id, response.json()))
        return history

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
