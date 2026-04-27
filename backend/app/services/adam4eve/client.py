import re
from collections.abc import Iterable, Mapping
from csv import DictReader
from dataclasses import dataclass
from datetime import date
from io import StringIO
import logging
from time import perf_counter

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.adam4eve.history_ingestion import AdamStationPriceHistoryRecord
from app.services.sync.bulk_imports import BulkImportService, CachedImportFile

logger = logging.getLogger(__name__)


ADAM4EVE_STATIC_BASE_URL = "https://static.adam4eve.eu"
_MARKET_ORDERS_ROOT_PATH = "/MarketOrdersTrades/"
_MARKET_PRICES_STATION_HISTORY_ROOT_PATH = "/MarketPricesStationHistory/"
_VOLUME_STATION_HISTORY_ROOT_PATH = "/MarketVolumesStationHistory/"
_YEAR_DIRECTORY_RE = re.compile(r"^(\d{4})/$")
_WEEKLY_EXPORT_RE = re.compile(r"^marketOrderTrades_weekly_(\d{4})-(\d+)\.csv$")
_WEEKLY_STATION_PRICE_EXPORT_RE = re.compile(r"^MarketPricesStationHistory_(hub|rest)_weekly_(\d{4})-(\d+)\.csv$")
_WEEKLY_STATION_VOLUME_EXPORT_RE = re.compile(
    r"^MarketVolumesStationHistory_(hub|rest)_weekly_(\d{4}-\d{2})\.csv$"
)


@dataclass(frozen=True)
class AdamMarketOrdersExport:
    path: str
    export_key: str
    covered_through_date: date


@dataclass(frozen=True)
class AdamStationPriceHistoryExport:
    path: str
    export_key: str
    covered_through_date: date


@dataclass(frozen=True)
class AdamStationVolumeHistoryExport:
    file_name: str
    hub_or_rest: str
    week_str: str
    url: str

    @property
    def path(self) -> str:
        return self.url

    @property
    def export_key(self) -> str:
        return f"{self.week_str}-{self.hub_or_rest}"

    @property
    def covered_through_date(self) -> date:
        year_str, week_str = self.week_str.split("-", maxsplit=1)
        return date.fromisocalendar(int(year_str), int(week_str), 7)


class Adam4EveClient:
    def __init__(self, *, import_service: BulkImportService | None = None) -> None:
        self.settings = get_settings()
        self.import_service = import_service or BulkImportService()

    def get_headers(self) -> dict[str, str]:
        return {"User-Agent": self.settings.a4e_user_agent}

    def resolve_latest_market_orders_export(self) -> AdamMarketOrdersExport:
        with httpx.Client(base_url=ADAM4EVE_STATIC_BASE_URL, headers=self.get_headers(), timeout=120.0) as client:
            return self._resolve_latest_market_orders_export(client)

    def resolve_market_orders_exports(
        self,
        *,
        since_date: date | None,
        client: httpx.Client | None = None,
    ) -> list[AdamMarketOrdersExport]:
        if client is not None:
            return self._resolve_market_orders_exports(client, since_date=since_date)
        with httpx.Client(base_url=ADAM4EVE_STATIC_BASE_URL, headers=self.get_headers(), timeout=120.0) as http_client:
            return self._resolve_market_orders_exports(http_client, since_date=since_date)

    def cache_market_orders_export(
        self,
        *,
        export_path: str,
        session: Session | None = None,
    ) -> CachedImportFile:
        with httpx.Client(base_url=ADAM4EVE_STATIC_BASE_URL, headers=self.get_headers(), timeout=120.0) as client:
            return self.import_service.cache_http_file(
                session,
                import_kind="adam4eve_npc_demand",
                file_key=export_path,
                remote_path=export_path,
                client=client,
            )

    def cache_market_orders_exports(
        self,
        *,
        since_date: date | None,
        session: Session | None = None,
    ) -> list[tuple[AdamMarketOrdersExport, CachedImportFile]]:
        with httpx.Client(base_url=ADAM4EVE_STATIC_BASE_URL, headers=self.get_headers(), timeout=120.0) as client:
            exports = self._resolve_market_orders_exports(client, since_date=since_date)
            return [
                (
                    export,
                    self.import_service.cache_http_file(
                        session,
                        import_kind="adam4eve_npc_demand",
                        file_key=export.path,
                        remote_path=export.path,
                        client=client,
                        covered_date=export.covered_through_date,
                    ),
                )
                for export in exports
            ]

    def fetch_regional_price_history(
        self,
        region_id: int,
        type_ids: Iterable[int],
        *,
        location_ids: Iterable[int] | None = None,
        since_date: date | None = None,
        hub_only: bool = False,
        session: Session | None = None,
    ) -> list[AdamStationPriceHistoryRecord]:
        requested_type_ids = set(type_ids)
        if not requested_type_ids:
            return []
        requested_location_ids = set(location_ids or [])
        if not requested_location_ids:
            return []

        with httpx.Client(base_url=ADAM4EVE_STATIC_BASE_URL, headers=self.get_headers(), timeout=120.0) as client:
            exports = self.resolve_station_price_history_exports(client=client, since_date=since_date, hub_only=hub_only)
            history: list[AdamStationPriceHistoryRecord] = []
            for export in exports:
                if session is None:
                    response = client.get(export.path)
                    response.raise_for_status()
                    csv_text = response.text
                else:
                    cached_file = self.import_service.cache_http_file(
                        session,
                        import_kind="adam_market_price_history_daily",
                        file_key=export.path,
                        remote_path=export.path,
                        client=client,
                        covered_date=export.covered_through_date,
                    )
                    csv_text = cached_file.path.read_text(encoding="utf-8")
                history.extend(
                    self._parse_station_price_history_csv(
                        csv_text,
                        region_id=region_id,
                        requested_locations=requested_location_ids,
                        requested_types=requested_type_ids,
                        since_date=since_date,
                    )
                )
            return history

    def resolve_station_price_history_exports(
        self,
        *,
        since_date: date | None,
        hub_only: bool = False,
        client: httpx.Client | None = None,
    ) -> list[AdamStationPriceHistoryExport]:
        if client is not None:
            return self._resolve_station_price_history_exports(client, since_date=since_date, hub_only=hub_only)
        with httpx.Client(base_url=ADAM4EVE_STATIC_BASE_URL, headers=self.get_headers(), timeout=120.0) as http_client:
            return self._resolve_station_price_history_exports(http_client, since_date=since_date, hub_only=hub_only)

    def cache_station_price_history_exports(
        self,
        *,
        since_date: date | None,
        hub_only: bool = False,
        session: Session | None = None,
    ) -> list[tuple[AdamStationPriceHistoryExport, CachedImportFile]]:
        with httpx.Client(base_url=ADAM4EVE_STATIC_BASE_URL, headers=self.get_headers(), timeout=120.0) as client:
            exports = self._resolve_station_price_history_exports(client, since_date=since_date, hub_only=hub_only)
            return [
                (
                    export,
                    self.import_service.cache_http_file(
                        session,
                        import_kind="adam_market_price_history_daily",
                        file_key=export.path,
                        remote_path=export.path,
                        client=client,
                        covered_date=export.covered_through_date,
                    ),
                )
                for export in exports
            ]

    def cache_station_volume_history_exports(
        self,
        *,
        since_date: date | None,
        hub_only: bool = False,
        session: Session | None = None,
    ) -> list[tuple[AdamStationVolumeHistoryExport, CachedImportFile]]:
        with httpx.Client(base_url=ADAM4EVE_STATIC_BASE_URL, headers=self.get_headers(), timeout=120.0) as client:
            exports = self._resolve_station_volume_history_exports(client, since_date=since_date, hub_only=hub_only)
            return [
                (
                    export,
                    self.import_service.cache_http_file(
                        session,
                        import_kind="adam_market_volume_history_daily",
                        file_key=export.url,
                        remote_path=export.url,
                        client=client,
                        covered_date=export.covered_through_date,
                    ),
                )
                for export in exports
            ]

    def _resolve_latest_market_orders_export(self, client: httpx.Client) -> AdamMarketOrdersExport:
        started_at = perf_counter()
        root_response = client.get(_MARKET_ORDERS_ROOT_PATH)
        root_response.raise_for_status()
        year_directories = self._extract_year_directories(root_response.text)
        if not year_directories:
            raise ValueError("Adam4EVE market orders CSV export could not be located.")

        # Only check the latest year (and fall back to the previous year if empty)
        for year in sorted(year_directories, reverse=True):
            year_response = client.get(f"{_MARKET_ORDERS_ROOT_PATH}{year}/")
            year_response.raise_for_status()
            weekly_exports = self._extract_weekly_exports(year, year_response.text)
            if not weekly_exports:
                continue
            latest_week, latest_name = max(weekly_exports)
            export_path = f"{_MARKET_ORDERS_ROOT_PATH}{year}/{latest_name}"
            covered_through_date = date.fromisocalendar(year, latest_week, 7)
            latest_export = AdamMarketOrdersExport(
                path=export_path,
                export_key=f"{year}-{latest_week}",
                covered_through_date=covered_through_date,
            )
            logger.info(
                "adam4eve profile phase=resolve_latest_market_orders_export elapsed_s=%.3f latest_export=%s",
                perf_counter() - started_at,
                latest_export.export_key,
            )
            return latest_export

        raise ValueError("Adam4EVE market orders CSV export could not be located.")

    def _resolve_market_orders_exports(
        self,
        client: httpx.Client,
        *,
        since_date: date | None,
    ) -> list[AdamMarketOrdersExport]:
        """Resolve available market order exports using week numbers from filenames.

        Uses ISO week end-date (Sunday) as covered_through_date instead of
        downloading each CSV to parse scanDate — this avoids downloading
        hundreds of multi-MB files just for date filtering.
        """
        started_at = perf_counter()
        root_response = client.get(_MARKET_ORDERS_ROOT_PATH)
        root_response.raise_for_status()
        year_directories = self._extract_year_directories(root_response.text)
        if not year_directories:
            raise ValueError("Adam4EVE market orders exports could not be located.")

        minimum_year = since_date.year if since_date is not None else min(year_directories)
        exports: list[AdamMarketOrdersExport] = []
        selected_years = sorted(year for year in year_directories if year >= minimum_year)
        for year in selected_years:
            year_response = client.get(f"{_MARKET_ORDERS_ROOT_PATH}{year}/")
            year_response.raise_for_status()
            weekly_exports = self._extract_weekly_exports(year, year_response.text)
            for week, export_name in weekly_exports:
                covered_through_date = date.fromisocalendar(year, week, 7)
                if since_date is not None and covered_through_date <= since_date:
                    continue
                export_path = f"{_MARKET_ORDERS_ROOT_PATH}{year}/{export_name}"
                exports.append(
                    AdamMarketOrdersExport(
                        path=export_path,
                        export_key=f"{year}-{week}",
                        covered_through_date=covered_through_date,
                    )
                )

        logger.info(
            "adam4eve profile phase=resolve_market_orders_exports elapsed_s=%.3f selected_exports=%s",
            perf_counter() - started_at,
            len(exports),
        )
        return sorted(exports, key=lambda export: (export.covered_through_date, export.path))

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
        candidates = Adam4EveClient._extract_weekly_exports(year, html)
        if not candidates:
            return None
        return max(candidates)

    @staticmethod
    def _extract_weekly_exports(year: int, html: str) -> list[tuple[int, str]]:
        candidates: list[tuple[int, str]] = []
        for href in re.findall(r'href="([^"]+)"', html, flags=re.IGNORECASE):
            match = _WEEKLY_EXPORT_RE.fullmatch(href)
            if match is None or int(match.group(1)) != year:
                continue
            candidates.append((int(match.group(2)), href))
        return candidates

    def _resolve_station_price_history_exports(
        self,
        client: httpx.Client,
        *,
        since_date: date | None,
        hub_only: bool = False,
    ) -> list[AdamStationPriceHistoryExport]:
        root_response = client.get(_MARKET_PRICES_STATION_HISTORY_ROOT_PATH)
        root_response.raise_for_status()
        year_directories = self._extract_year_directories(root_response.text)
        if not year_directories:
            raise ValueError("Adam4EVE station price history exports could not be located.")

        exports: list[AdamStationPriceHistoryExport] = []
        minimum_year = since_date.year if since_date is not None else min(year_directories)
        for year in sorted(year for year in year_directories if year >= minimum_year):
            year_response = client.get(f"{_MARKET_PRICES_STATION_HISTORY_ROOT_PATH}{year}/")
            year_response.raise_for_status()
            for href in re.findall(r'href="([^"]+)"', year_response.text, flags=re.IGNORECASE):
                match = _WEEKLY_STATION_PRICE_EXPORT_RE.fullmatch(href)
                if match is None:
                    continue
                hub_or_rest = match.group(1)
                if hub_only and hub_or_rest != "hub":
                    continue
                if int(match.group(2)) != year:
                    continue
                week = int(match.group(3))
                covered_through_date = date.fromisocalendar(year, week, 7)
                if since_date is not None and covered_through_date <= since_date:
                    continue
                exports.append(
                    AdamStationPriceHistoryExport(
                        path=f"{_MARKET_PRICES_STATION_HISTORY_ROOT_PATH}{year}/{href}",
                        export_key=f"{year}-{week}-{hub_or_rest}",
                        covered_through_date=covered_through_date,
                    )
                )

        return sorted(exports, key=lambda export: (export.covered_through_date, export.path))

    def _resolve_station_volume_history_exports(
        self,
        client: httpx.Client,
        *,
        since_date: date | None,
        hub_only: bool = False,
    ) -> list[AdamStationVolumeHistoryExport]:
        root_response = client.get(_VOLUME_STATION_HISTORY_ROOT_PATH)
        root_response.raise_for_status()
        year_directories = self._extract_year_directories(root_response.text)
        if not year_directories:
            raise ValueError("Adam4EVE station volume history exports could not be located.")

        exports: list[AdamStationVolumeHistoryExport] = []
        minimum_year = since_date.year if since_date is not None else min(year_directories)
        for year in sorted(year for year in year_directories if year >= minimum_year):
            year_response = client.get(f"{_VOLUME_STATION_HISTORY_ROOT_PATH}{year}/")
            year_response.raise_for_status()
            for href in re.findall(r'href="([^"]+)"', year_response.text, flags=re.IGNORECASE):
                match = _WEEKLY_STATION_VOLUME_EXPORT_RE.fullmatch(href)
                if match is None:
                    continue
                hub_or_rest_value = match.group(1)
                if hub_only and hub_or_rest_value != "hub":
                    continue
                week_str = match.group(2)
                if int(week_str.split("-", maxsplit=1)[0]) != year:
                    continue
                covered_through_date = date.fromisocalendar(year, int(week_str.split("-", maxsplit=1)[1]), 7)
                if since_date is not None and covered_through_date <= since_date:
                    continue
                exports.append(
                    AdamStationVolumeHistoryExport(
                        file_name=href,
                        hub_or_rest=hub_or_rest_value,
                        week_str=week_str,
                        url=f"{_VOLUME_STATION_HISTORY_ROOT_PATH}{year}/{href}",
                    )
                )

        return sorted(exports, key=lambda export: (export.covered_through_date, export.url))

    def _parse_station_price_history_csv(
        self,
        csv_text: str,
        *,
        region_id: int,
        requested_locations: set[int],
        requested_types: set[int],
        since_date: date | None,
    ) -> list[AdamStationPriceHistoryRecord]:
        if not csv_text.strip():
            return []

        reader = DictReader(StringIO(csv_text), delimiter=";")
        fieldnames = set(reader.fieldnames or [])
        required_columns = {
            "type_id",
            "location_id",
            "region_id",
            "sell_price_low",
            "sell_price_avg",
            "sell_price_high",
        }
        if reader.fieldnames is None or not required_columns.issubset(fieldnames) or not (
            "date" in fieldnames or "price_date" in fieldnames
        ):
            raise ValueError("Adam4EVE station price history export is missing required columns.")

        rows: list[AdamStationPriceHistoryRecord] = []
        for row in reader:
            try:
                normalized = self._normalize_station_price_history_row(row)
            except ValueError:
                continue
            if normalized[0] != region_id:
                continue
            if normalized[1] not in requested_locations:
                continue
            if normalized[2] not in requested_types:
                continue
            normalized_date = date.fromisoformat(normalized[3])
            if since_date is not None and normalized_date <= since_date:
                continue
            rows.append(
                {
                    "location_id": normalized[1],
                    "region_id": normalized[0],
                    "type_id": normalized[2],
                    "date": normalized[3],
                    "buy_price_low": normalized[4],
                    "buy_price_avg": normalized[5],
                    "buy_price_high": normalized[6],
                    "sell_price_low": normalized[7],
                    "sell_price_avg": normalized[8],
                    "sell_price_high": normalized[9],
                }
            )
        return rows

    @staticmethod
    def _normalize_station_price_history_row(
        row: Mapping[str, object],
    ) -> tuple[int, int, int, str, float | None, float | None, float | None, float | None, float | None, float | None]:
        region_id_value = row.get("region_id")
        location_id_value = row.get("location_id")
        type_id_value = row.get("type_id")
        date_value = row.get("date")
        if date_value in (None, ""):
            date_value = row.get("price_date")
        buy_low_value = row.get("buy_price_low")
        buy_avg_value = row.get("buy_price_avg")
        buy_high_value = row.get("buy_price_high")
        sell_low_value = row.get("sell_price_low")
        sell_avg_value = row.get("sell_price_avg")
        sell_high_value = row.get("sell_price_high")
        if not all(
            isinstance(value, str)
            for value in (
                region_id_value,
                location_id_value,
                type_id_value,
                date_value,
            )
        ):
            raise ValueError("Adam4EVE station price history export row is malformed.")
        try:
            region_id = int(str(region_id_value))
            location_id = int(str(location_id_value))
            type_id = int(str(type_id_value))
            normalized_date = date.fromisoformat(str(date_value)).isoformat()
        except (TypeError, ValueError) as exc:
            raise ValueError("Adam4EVE station price history export row is malformed.") from exc

        return (
            region_id,
            location_id,
            type_id,
            normalized_date,
            Adam4EveClient._optional_float(buy_low_value),
            Adam4EveClient._optional_float(buy_avg_value),
            Adam4EveClient._optional_float(buy_high_value),
            Adam4EveClient._optional_float(sell_low_value),
            Adam4EveClient._optional_float(sell_avg_value),
            Adam4EveClient._optional_float(sell_high_value),
        )

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        rendered = str(value).strip()
        if not rendered:
            return None
        return float(rendered)
