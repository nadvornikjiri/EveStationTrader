from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import pytest

from app.services.adam4eve.client import ADAM4EVE_STATIC_BASE_URL, Adam4EveClient
from app.services.sync.bulk_imports import BulkImportService


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text
        self.raise_for_status_called = False

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True


class FakeHttpxClient:
    instances: list["FakeHttpxClient"] = []

    def __init__(self, *, base_url: str, headers: Mapping[str, str], timeout: float) -> None:
        self.base_url = base_url
        self.headers = dict(headers)
        self.timeout = timeout
        self.calls: list[str] = []
        FakeHttpxClient.instances.append(self)

    def __enter__(self) -> "FakeHttpxClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc_type, exc, tb

    def get(self, path: str) -> FakeResponse:
        self.calls.append(path)
        return FakeResponse(RESPONSES[path])


RESPONSES: dict[str, str] = {}


def test_cache_market_orders_export_requests_latest_export_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    FakeHttpxClient.instances.clear()
    RESPONSES.clear()
    RESPONSES.update(
        {
            "/MarketOrdersTrades/": '<a href="2025/">2025/</a><a href="2026/">2026/</a>',
            "/MarketOrdersTrades/2025/": "",
            "/MarketOrdersTrades/2026/": '<a href="marketOrderTrades_weekly_2026-1.csv">week 1</a>'
            '<a href="marketOrderTrades_weekly_2026-12.csv">week 12</a>',
            "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-1.csv": (
                "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
                "60003760;10000002;34;1;0;2026-01-04;10;5.0;5.0;5.0;1;50\n"
            ),
            "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv": (
                "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
                "60003760;10000002;34;1;0;2026-03-20;10;5.0;5.0;5.0;1;50\n"
                "60003760;10000002;34;0;0;2026-03-20;5;6.0;6.0;6.0;1;30\n"
                "60008494;10000043;35;0;0;2026-03-20;2;9.0;9.0;9.0;1;18\n"
            ),
        }
    )
    monkeypatch.setattr("app.services.adam4eve.client.httpx.Client", FakeHttpxClient)

    export = Adam4EveClient(import_service=BulkImportService(cache_root=tmp_path)).resolve_latest_market_orders_export()
    cached = Adam4EveClient(import_service=BulkImportService(cache_root=tmp_path)).cache_market_orders_export(
        export_path=export.path
    )

    assert export.path == "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv"
    assert cached.path.read_text(encoding="utf-8").startswith("location_id;region_id;type_id;is_buy_order;")
    assert FakeHttpxClient.instances
    assert FakeHttpxClient.instances[0].base_url == ADAM4EVE_STATIC_BASE_URL
    assert FakeHttpxClient.instances[0].headers["User-Agent"] == Adam4EveClient().get_headers()["User-Agent"]
    assert FakeHttpxClient.instances[0].calls == [
        "/MarketOrdersTrades/",
        "/MarketOrdersTrades/2025/",
        "/MarketOrdersTrades/2026/",
        "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-1.csv",
        "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv",
    ]


def test_resolve_latest_market_orders_export_returns_week_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    FakeHttpxClient.instances.clear()
    RESPONSES.clear()
    RESPONSES.update(
        {
            "/MarketOrdersTrades/": '<a href="2025/">2025/</a><a href="2026/">2026/</a>',
            "/MarketOrdersTrades/2025/": "",
            "/MarketOrdersTrades/2026/": '<a href="marketOrderTrades_weekly_2026-11.csv">week 11</a>'
            '<a href="marketOrderTrades_weekly_2026-12.csv">week 12</a>',
            "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-11.csv": (
                "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
                "60003760;10000002;34;1;0;2026-03-14;10;5.0;5.0;5.0;1;50\n"
            ),
            "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv": (
                "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
                "60003760;10000002;34;1;0;2026-03-20;10;5.0;5.0;5.0;1;50\n"
                "60003760;10000002;34;1;0;2026-03-21;12;5.0;5.0;5.0;1;60\n"
            ),
        }
    )
    monkeypatch.setattr("app.services.adam4eve.client.httpx.Client", FakeHttpxClient)

    export = Adam4EveClient(import_service=BulkImportService(cache_root=tmp_path)).resolve_latest_market_orders_export()

    assert export.path == "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv"
    assert export.export_key == "2026-12"
    assert export.covered_through_date.isoformat() == "2026-03-21"


def test_resolve_market_orders_exports_returns_all_exports_after_since_date(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    FakeHttpxClient.instances.clear()
    RESPONSES.clear()
    RESPONSES.update(
        {
            "/MarketOrdersTrades/": '<a href="2025/">2025/</a><a href="2026/">2026/</a>',
            "/MarketOrdersTrades/2025/": '<a href="marketOrderTrades_weekly_2025-52.csv">week 52</a>',
            "/MarketOrdersTrades/2026/": (
                '<a href="marketOrderTrades_weekly_2026-11.csv">week 11</a>'
                '<a href="marketOrderTrades_weekly_2026-12.csv">week 12</a>'
            ),
            "/MarketOrdersTrades/2025/marketOrderTrades_weekly_2025-52.csv": (
                "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
                "60003760;10000002;34;1;0;2025-12-28;10;5.0;5.0;5.0;1;50\n"
            ),
            "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-11.csv": (
                "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
                "60003760;10000002;34;1;0;2026-03-15;10;5.0;5.0;5.0;1;50\n"
            ),
            "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv": (
                "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
                "60003760;10000002;34;1;0;2026-03-21;12;5.0;5.0;5.0;1;60\n"
            ),
        }
    )
    monkeypatch.setattr("app.services.adam4eve.client.httpx.Client", FakeHttpxClient)

    exports = Adam4EveClient(import_service=BulkImportService(cache_root=tmp_path)).resolve_market_orders_exports(
        since_date=date(2026, 3, 14)
    )

    assert [(export.export_key, export.covered_through_date.isoformat()) for export in exports] == [
        ("2026-11", "2026-03-15"),
        ("2026-12", "2026-03-21"),
    ]


def test_fetch_regional_price_history_requests_station_history_exports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeHttpxClient.instances.clear()
    RESPONSES.clear()
    RESPONSES.update(
        {
            "/MarketPricesStationHistory/": '<a href="2025/">2025/</a><a href="2026/">2026/</a>',
            "/MarketPricesStationHistory/2026/": (
                '<a href="MarketPricesStationHistory_hub_weekly_2026-11.csv">week 11</a>'
                '<a href="MarketPricesStationHistory_rest_weekly_2026-12.csv">week 12</a>'
            ),
            "/MarketPricesStationHistory/2026/MarketPricesStationHistory_hub_weekly_2026-11.csv": (
                "type_id;location_id;region_id;date;buy_price_low;buy_price_avg;buy_price_high;sell_price_low;"
                "sell_price_avg;sell_price_high\n"
                "34;60003760;10000002;2026-03-20;4.1;4.2;4.3;5.1;5.2;5.3\n"
                "34;60008494;10000002;2026-03-20;4.0;4.1;4.2;5.0;5.1;5.2\n"
            ),
            "/MarketPricesStationHistory/2026/MarketPricesStationHistory_rest_weekly_2026-12.csv": (
                "type_id;location_id;region_id;date;buy_price_low;buy_price_avg;buy_price_high;sell_price_low;"
                "sell_price_avg;sell_price_high\n"
                "34;60003760;10000002;2026-03-21;4.1;4.2;4.3;5.1;5.2;5.3\n"
                "35;60003760;10000002;2026-03-21;7.1;7.2;7.3;8.1;8.2;8.3\n"
                "34;60003760;10000043;2026-03-21;4.1;4.2;4.3;9.1;9.2;9.3\n"
            ),
        }
    )
    monkeypatch.setattr("app.services.adam4eve.client.httpx.Client", FakeHttpxClient)

    rows = Adam4EveClient().fetch_regional_price_history(
        10000002,
        [34],
        location_ids=[60003760],
        since_date=date(2026, 3, 20),
    )

    assert rows == [
        {
            "location_id": 60003760,
            "region_id": 10000002,
            "type_id": 34,
            "date": "2026-03-21",
            "buy_price_low": 4.1,
            "buy_price_avg": 4.2,
            "buy_price_high": 4.3,
            "sell_price_low": 5.1,
            "sell_price_avg": 5.2,
            "sell_price_high": 5.3,
        }
    ]
    assert FakeHttpxClient.instances[0].calls == [
        "/MarketPricesStationHistory/",
        "/MarketPricesStationHistory/2026/",
        "/MarketPricesStationHistory/2026/MarketPricesStationHistory_rest_weekly_2026-12.csv",
    ]


def test_fetch_regional_price_history_rejects_malformed_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeHttpxClient.instances.clear()
    RESPONSES.clear()
    RESPONSES.update(
        {
            "/MarketPricesStationHistory/": '<a href="2026/">2026/</a>',
            "/MarketPricesStationHistory/2026/": (
                '<a href="MarketPricesStationHistory_hub_weekly_2026-12.csv">take</a>'
            ),
            "/MarketPricesStationHistory/2026/MarketPricesStationHistory_hub_weekly_2026-12.csv": (
                "type_id;location_id;region_id;date;sell_price_low;sell_price_high\n"
                "34;60003760;10000002;2026-03-21;5.1;5.3\n"
            ),
        }
    )
    monkeypatch.setattr("app.services.adam4eve.client.httpx.Client", FakeHttpxClient)

    with pytest.raises(ValueError, match="missing required columns"):
        Adam4EveClient().fetch_regional_price_history(10000002, [34], location_ids=[60003760], since_date=None)


def test_fetch_regional_price_history_skips_rows_with_blank_price_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeHttpxClient.instances.clear()
    RESPONSES.clear()
    RESPONSES.update(
        {
            "/MarketPricesStationHistory/": '<a href="2026/">2026/</a>',
            "/MarketPricesStationHistory/2026/": (
                '<a href="MarketPricesStationHistory_hub_weekly_2026-12.csv">take</a>'
            ),
            "/MarketPricesStationHistory/2026/MarketPricesStationHistory_hub_weekly_2026-12.csv": (
                "type_id;location_id;region_id;date;buy_price_low;buy_price_avg;buy_price_high;sell_price_low;"
                "sell_price_avg;sell_price_high\n"
                "34;60003760;10000002;2026-03-21;4.1;4.2;4.3;;; \n"
                "35;60003760;10000002;2026-03-21;7.1;7.2;7.3;8.1;8.2;8.3\n"
            ),
        }
    )
    monkeypatch.setattr("app.services.adam4eve.client.httpx.Client", FakeHttpxClient)

    rows = Adam4EveClient().fetch_regional_price_history(10000002, [34, 35], location_ids=[60003760], since_date=None)

    assert rows == [
        {
            "location_id": 60003760,
            "region_id": 10000002,
            "type_id": 34,
            "date": "2026-03-21",
            "buy_price_low": 4.1,
            "buy_price_avg": 4.2,
            "buy_price_high": 4.3,
            "sell_price_low": None,
            "sell_price_avg": None,
            "sell_price_high": None,
        },
        {
            "location_id": 60003760,
            "region_id": 10000002,
            "type_id": 35,
            "date": "2026-03-21",
            "buy_price_low": 7.1,
            "buy_price_avg": 7.2,
            "buy_price_high": 7.3,
            "sell_price_low": 8.1,
            "sell_price_avg": 8.2,
            "sell_price_high": 8.3,
        }
    ]


