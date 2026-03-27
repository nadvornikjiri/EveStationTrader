import re
from collections.abc import Iterable, Mapping
from csv import DictReader
from dataclasses import dataclass
from datetime import date
from io import StringIO

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.adam4eve.ingestion import AdamNpcDemandRecord
from app.services.esi.history_ingestion import EsiRegionalHistoryRecord
from app.services.sync.bulk_imports import BulkImportService


ADAM4EVE_STATIC_BASE_URL = "https://static.adam4eve.eu"
_MARKET_ORDERS_ROOT_PATH = "/MarketOrdersTrades/"
_MARKET_PRICES_REGION_HISTORY_ROOT_PATH = "/MarketPricesRegionHistory/"
_YEAR_DIRECTORY_RE = re.compile(r"^(\d{4})/$")
_WEEKLY_EXPORT_RE = re.compile(r"^marketOrderTrades_weekly_(\d{4})-(\d+)\.csv$")
_DAILY_REGION_PRICE_EXPORT_RE = re.compile(r"^marketPrice_(\d+)_daily_(\d{4}-\d{2}-\d{2})\.csv$")


@dataclass(frozen=True)
class AdamMarketOrdersExport:
    path: str
    export_key: str
    covered_through_date: date


class Adam4EveClient:
    def __init__(self, *, import_service: BulkImportService | None = None) -> None:
        self.settings = get_settings()
        self.import_service = import_service or BulkImportService()

    def get_headers(self) -> dict[str, str]:
        return {"User-Agent": self.settings.a4e_user_agent}

    def resolve_latest_market_orders_export(self) -> AdamMarketOrdersExport:
        with httpx.Client(base_url=ADAM4EVE_STATIC_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            return self._resolve_latest_market_orders_export(client)

    def fetch_npc_demand(
        self,
        location_ids: Iterable[int],
        type_ids: Iterable[int],
        *,
        export_path: str | None = None,
        synced_through_by_region: Mapping[int, date] | None = None,
        session: Session | None = None,
    ) -> list[AdamNpcDemandRecord]:
        requested_locations = tuple(dict.fromkeys(location_ids))
        requested_types = tuple(dict.fromkeys(type_ids))
        if not requested_locations or not requested_types:
            return []

        with httpx.Client(base_url=ADAM4EVE_STATIC_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            resolved_export_path = export_path or self._resolve_latest_market_orders_export(client).path
            cached_file = self.import_service.cache_http_file(
                session,
                import_kind="adam4eve_npc_demand",
                file_key=resolved_export_path,
                remote_path=resolved_export_path,
                client=client,
            )
            return self._parse_market_orders_csv(
                cached_file.path.read_text(encoding="utf-8"),
                requested_locations=set(requested_locations),
                requested_types=set(requested_types),
                synced_through_by_region=synced_through_by_region or {},
            )

    def fetch_regional_price_history(
        self,
        region_id: int,
        type_ids: Iterable[int],
        *,
        since_date: date | None = None,
        session: Session | None = None,
    ) -> list[EsiRegionalHistoryRecord]:
        requested_type_ids = set(type_ids)
        if not requested_type_ids:
            return []

        with httpx.Client(base_url=ADAM4EVE_STATIC_BASE_URL, headers=self.get_headers(), timeout=30.0) as client:
            export_paths = self._resolve_region_price_history_exports(client, region_id=region_id, since_date=since_date)
            history: list[EsiRegionalHistoryRecord] = []
            for export_path in export_paths:
                export_date = self._extract_region_price_export_date(export_path)
                cached_file = self.import_service.cache_http_file(
                    session,
                    import_kind="esi_history_daily",
                    file_key=export_path,
                    remote_path=export_path,
                    client=client,
                    covered_date=export_date,
                )
                history.extend(
                    self._parse_region_price_history_csv(
                        cached_file.path.read_text(encoding="utf-8"),
                        region_id=region_id,
                        requested_types=requested_type_ids,
                    )
                )
            return history

    def _resolve_latest_market_orders_export(self, client: httpx.Client) -> AdamMarketOrdersExport:
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
                week = latest_export[0]
                export_name = latest_export[1]
                return AdamMarketOrdersExport(
                    path=f"{_MARKET_ORDERS_ROOT_PATH}{year}/{export_name}",
                    export_key=f"{year}-{week}",
                    covered_through_date=date.fromisocalendar(year, week, 7),
                )

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
    def _extract_latest_weekly_export(year: int, html: str) -> tuple[int, str] | None:
        candidates: list[tuple[int, str]] = []
        for href in re.findall(r'href="([^"]+)"', html, flags=re.IGNORECASE):
            match = _WEEKLY_EXPORT_RE.fullmatch(href)
            if match is None or int(match.group(1)) != year:
                continue
            candidates.append((int(match.group(2)), href))

        if not candidates:
            return None
        return max(candidates)

    def _resolve_region_price_history_exports(
        self,
        client: httpx.Client,
        *,
        region_id: int,
        since_date: date | None,
    ) -> list[str]:
        root_response = client.get(_MARKET_PRICES_REGION_HISTORY_ROOT_PATH)
        root_response.raise_for_status()
        year_directories = self._extract_year_directories(root_response.text)
        if not year_directories:
            raise ValueError("Adam4EVE regional price history exports could not be located.")

        export_paths: list[tuple[date, str]] = []
        minimum_year = since_date.year if since_date is not None else min(year_directories)
        for year in sorted(year for year in year_directories if year >= minimum_year):
            year_response = client.get(f"{_MARKET_PRICES_REGION_HISTORY_ROOT_PATH}{year}/")
            year_response.raise_for_status()
            for href in re.findall(r'href="([^"]+)"', year_response.text, flags=re.IGNORECASE):
                match = _DAILY_REGION_PRICE_EXPORT_RE.fullmatch(href)
                if match is None:
                    continue
                if int(match.group(1)) != region_id:
                    continue
                export_date = date.fromisoformat(match.group(2))
                if since_date is not None and export_date <= since_date:
                    continue
                export_paths.append((export_date, f"{_MARKET_PRICES_REGION_HISTORY_ROOT_PATH}{year}/{href}"))

        return [path for _, path in sorted(export_paths)]

    @staticmethod
    def _extract_region_price_export_date(export_path: str) -> date | None:
        export_name = export_path.rsplit("/", 1)[-1]
        match = _DAILY_REGION_PRICE_EXPORT_RE.fullmatch(export_name)
        if match is None:
            return None
        return date.fromisoformat(match.group(2))

    def _parse_market_orders_csv(
        self,
        csv_text: str,
        *,
        requested_locations: set[int],
        requested_types: set[int],
        synced_through_by_region: Mapping[int, date],
    ) -> list[AdamNpcDemandRecord]:
        if not csv_text.strip():
            return []

        reader = DictReader(StringIO(csv_text), delimiter=";")
        required_columns = {"location_id", "type_id", "scanDate", "amount"}
        if reader.fieldnames is None or not required_columns.issubset(set(reader.fieldnames)):
            raise ValueError("Adam4EVE market orders export is missing required columns.")

        grouped_amounts: dict[tuple[int, int, str], float] = {}
        for row in reader:
            location_id, region_id, type_id, scan_date, amount = self._normalize_market_order_row(row)
            if location_id not in requested_locations:
                continue
            if type_id not in requested_types:
                continue
            synced_through_date = synced_through_by_region.get(region_id)
            if synced_through_date is not None and date.fromisoformat(scan_date) <= synced_through_date:
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

    def _parse_region_price_history_csv(
        self,
        csv_text: str,
        *,
        region_id: int,
        requested_types: set[int],
    ) -> list[EsiRegionalHistoryRecord]:
        if not csv_text.strip():
            return []

        reader = DictReader(StringIO(csv_text), delimiter=";")
        required_columns = {
            "type_id",
            "region_id",
            "date",
            "sell_price_low",
            "sell_price_avg",
            "sell_price_high",
        }
        if reader.fieldnames is None or not required_columns.issubset(set(reader.fieldnames)):
            raise ValueError("Adam4EVE regional price history export is missing required columns.")

        rows: list[EsiRegionalHistoryRecord] = []
        for row in reader:
            normalized = self._normalize_region_price_history_row(row)
            if normalized[0] != region_id:
                continue
            if normalized[1] not in requested_types:
                continue
            rows.append(
                {
                    "type_id": normalized[1],
                    "date": normalized[2],
                    "average": normalized[3],
                    "highest": normalized[4],
                    "lowest": normalized[5],
                    "order_count": 0,
                    "volume": 0,
                }
            )
        return rows

    @staticmethod
    def _normalize_market_order_row(row: Mapping[str, object]) -> tuple[int, int, int, str, float]:
        location_id_value = row.get("location_id")
        region_id_value = row.get("region_id")
        type_id_value = row.get("type_id")
        scan_date_value = row.get("scanDate")
        amount_value = row.get("amount")
        if not isinstance(location_id_value, str) or not isinstance(region_id_value, str) or not isinstance(type_id_value, str):
            raise ValueError("Adam4EVE market orders export row is malformed.")
        if not isinstance(scan_date_value, str) or not isinstance(amount_value, str):
            raise ValueError("Adam4EVE market orders export row is malformed.")
        try:
            location_id = int(location_id_value)
            region_id = int(region_id_value)
            type_id = int(type_id_value)
            scan_date = date.fromisoformat(scan_date_value).isoformat()
            amount = float(amount_value)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Adam4EVE market orders export row is malformed.") from exc

        return location_id, region_id, type_id, scan_date, amount

    @staticmethod
    def _normalize_region_price_history_row(row: Mapping[str, object]) -> tuple[int, int, str, float, float, float]:
        region_id_value = row.get("region_id")
        type_id_value = row.get("type_id")
        date_value = row.get("date")
        sell_low_value = row.get("sell_price_low")
        sell_avg_value = row.get("sell_price_avg")
        sell_high_value = row.get("sell_price_high")
        if not all(
            isinstance(value, str)
            for value in (
                region_id_value,
                type_id_value,
                date_value,
                sell_low_value,
                sell_avg_value,
                sell_high_value,
            )
        ):
            raise ValueError("Adam4EVE regional price history export row is malformed.")
        try:
            region_id = int(str(region_id_value))
            type_id = int(str(type_id_value))
            normalized_date = date.fromisoformat(str(date_value)).isoformat()
            sell_low = float(str(sell_low_value))
            sell_avg = float(str(sell_avg_value))
            sell_high = float(str(sell_high_value))
        except (TypeError, ValueError) as exc:
            raise ValueError("Adam4EVE regional price history export row is malformed.") from exc

        return region_id, type_id, normalized_date, sell_avg, sell_high, sell_low
