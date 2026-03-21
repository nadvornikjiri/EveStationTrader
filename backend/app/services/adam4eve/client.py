import re
from collections.abc import Iterable, Mapping
from csv import DictReader
from datetime import date
from io import StringIO

import httpx

from app.core.config import get_settings
from app.services.adam4eve.ingestion import AdamNpcDemandRecord


ADAM4EVE_STATIC_BASE_URL = "https://static.adam4eve.eu"
_MARKET_ORDERS_ROOT_PATH = "/MarketOrdersTrades/"
_YEAR_DIRECTORY_RE = re.compile(r"^(\d{4})/$")
_WEEKLY_EXPORT_RE = re.compile(r"^marketOrderTrades_weekly_(\d{4})-(\d+)\.csv$")


class Adam4EveClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def get_headers(self) -> dict[str, str]:
        return {"User-Agent": self.settings.a4e_user_agent}

    def fetch_npc_demand(self, location_ids: Iterable[int], type_ids: Iterable[int]) -> list[AdamNpcDemandRecord]:
        requested_locations = tuple(dict.fromkeys(location_ids))
        requested_types = tuple(dict.fromkeys(type_ids))
        if not requested_locations or not requested_types:
            return []

        with httpx.Client(base_url=ADAM4EVE_STATIC_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            export_path = self._resolve_latest_market_orders_export(client)
            response = client.get(export_path)
            response.raise_for_status()
            return self._parse_market_orders_csv(
                response.text,
                requested_locations=set(requested_locations),
                requested_types=set(requested_types),
            )

    def _resolve_latest_market_orders_export(self, client: httpx.Client) -> str:
        root_response = client.get(_MARKET_ORDERS_ROOT_PATH)
        root_response.raise_for_status()
        year_directories = self._extract_year_directories(root_response.text)
        if not year_directories:
            raise ValueError("Adam4EVE market orders exports could not be located.")

        for year in sorted(year_directories, reverse=True):
            year_response = client.get(f"{_MARKET_ORDERS_ROOT_PATH}{year}/")
            year_response.raise_for_status()
            latest_export = self._extract_latest_weekly_export(year, year_response.text)
            if latest_export is not None:
                return f"{_MARKET_ORDERS_ROOT_PATH}{year}/{latest_export}"

        raise ValueError("Adam4EVE market orders CSV export could not be located.")

    @staticmethod
    def _extract_year_directories(html: str) -> list[int]:
        years: list[int] = []
        for href in re.findall(r'href="([^"]+)"', html, flags=re.IGNORECASE):
            match = _YEAR_DIRECTORY_RE.fullmatch(href)
            if match is not None:
                years.append(int(match.group(1)))
        return years

    @staticmethod
    def _extract_latest_weekly_export(year: int, html: str) -> str | None:
        candidates: list[tuple[int, str]] = []
        for href in re.findall(r'href="([^"]+)"', html, flags=re.IGNORECASE):
            match = _WEEKLY_EXPORT_RE.fullmatch(href)
            if match is None or int(match.group(1)) != year:
                continue
            candidates.append((int(match.group(2)), href))

        if not candidates:
            return None
        return max(candidates)[1]

    def _parse_market_orders_csv(
        self,
        csv_text: str,
        *,
        requested_locations: set[int],
        requested_types: set[int],
    ) -> list[AdamNpcDemandRecord]:
        if not csv_text.strip():
            return []

        reader = DictReader(StringIO(csv_text), delimiter=";")
        required_columns = {"location_id", "type_id", "scanDate", "amount"}
        if reader.fieldnames is None or not required_columns.issubset(set(reader.fieldnames)):
            raise ValueError("Adam4EVE market orders export is missing required columns.")

        grouped_amounts: dict[tuple[int, int, str], float] = {}
        for row in reader:
            location_id, type_id, scan_date, amount = self._normalize_market_order_row(row)
            if location_id not in requested_locations:
                continue
            if type_id not in requested_types:
                continue

            key = (location_id, type_id, scan_date)
            grouped_amounts[key] = grouped_amounts.get(key, 0.0) + amount

        return [
            {
                "location_id": location_id,
                "type_id": type_id,
                "demand_day": amount,
                "source": "adam4eve",
                "date": scan_date,
            }
            for (location_id, type_id, scan_date), amount in sorted(grouped_amounts.items())
        ]

    @staticmethod
    def _normalize_market_order_row(row: Mapping[str, object]) -> tuple[int, int, str, float]:
        location_id_value = row.get("location_id")
        type_id_value = row.get("type_id")
        scan_date_value = row.get("scanDate")
        amount_value = row.get("amount")
        if not isinstance(location_id_value, str) or not isinstance(type_id_value, str):
            raise ValueError("Adam4EVE market orders export row is malformed.")
        if not isinstance(scan_date_value, str) or not isinstance(amount_value, str):
            raise ValueError("Adam4EVE market orders export row is malformed.")
        try:
            location_id = int(location_id_value)
            type_id = int(type_id_value)
            scan_date = date.fromisoformat(scan_date_value).isoformat()
            amount = float(amount_value)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Adam4EVE market orders export row is malformed.") from exc

        return location_id, type_id, scan_date, amount
