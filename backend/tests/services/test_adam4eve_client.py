from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import pytest

from app.services.adam4eve.client import ADAM4EVE_STATIC_BASE_URL, Adam4EveClient


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


def test_fetch_npc_demand_requests_latest_export_and_aggregates_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeHttpxClient.instances.clear()
    RESPONSES.clear()
    RESPONSES.update(
        {
            "/MarketOrdersTrades/": '<a href="2025/">2025/</a><a href="2026/">2026/</a>',
            "/MarketOrdersTrades/2026/": '<a href="marketOrderTrades_weekly_2026-1.csv">week 1</a>'
            '<a href="marketOrderTrades_weekly_2026-12.csv">week 12</a>',
            "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv": (
                "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
                "60003760;10000002;34;1;0;2026-03-20;10;5.0;5.0;5.0;1;50\n"
                "60003760;10000002;34;0;0;2026-03-20;5;6.0;6.0;6.0;1;30\n"
                "60008494;10000043;35;0;0;2026-03-20;2;9.0;9.0;9.0;1;18\n"
                "60000000;10000043;35;0;0;2026-03-20;99;1.0;1.0;1.0;1;99\n"
            ),
        }
    )
    monkeypatch.setattr("app.services.adam4eve.client.httpx.Client", FakeHttpxClient)

    rows = Adam4EveClient().fetch_npc_demand([60003760, 60008494], [34, 35])

    assert rows == [
        {
            "location_id": 60003760,
            "type_id": 34,
            "demand_day": 15.0,
            "source": "adam4eve",
            "date": "2026-03-20",
        },
        {
            "location_id": 60008494,
            "type_id": 35,
            "demand_day": 2.0,
            "source": "adam4eve",
            "date": "2026-03-20",
        },
    ]
    assert len(FakeHttpxClient.instances) == 1
    fake_client = FakeHttpxClient.instances[0]
    assert fake_client.base_url == ADAM4EVE_STATIC_BASE_URL
    assert fake_client.headers["User-Agent"] == Adam4EveClient().get_headers()["User-Agent"]
    assert fake_client.calls == [
        "/MarketOrdersTrades/",
        "/MarketOrdersTrades/2026/",
        "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv",
    ]


def test_resolve_latest_market_orders_export_returns_week_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeHttpxClient.instances.clear()
    RESPONSES.clear()
    RESPONSES.update(
        {
            "/MarketOrdersTrades/": '<a href="2025/">2025/</a><a href="2026/">2026/</a>',
            "/MarketOrdersTrades/2026/": '<a href="marketOrderTrades_weekly_2026-11.csv">week 11</a>'
            '<a href="marketOrderTrades_weekly_2026-12.csv">week 12</a>',
        }
    )
    monkeypatch.setattr("app.services.adam4eve.client.httpx.Client", FakeHttpxClient)

    export = Adam4EveClient().resolve_latest_market_orders_export()

    assert export.path == "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv"
    assert export.export_key == "2026-12"
    assert export.covered_through_date.isoformat() == "2026-03-22"


def test_fetch_npc_demand_returns_empty_for_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeHttpxClient.instances.clear()
    RESPONSES.clear()
    RESPONSES.update(
        {
            "/MarketOrdersTrades/": '<a href="2026/">2026/</a>',
            "/MarketOrdersTrades/2026/": '<a href="marketOrderTrades_weekly_2026-12.csv">week 12</a>',
            "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv": "",
        }
    )
    monkeypatch.setattr("app.services.adam4eve.client.httpx.Client", FakeHttpxClient)

    rows = Adam4EveClient().fetch_npc_demand([60003760], [34])

    assert rows == []


def test_fetch_npc_demand_skips_rows_at_or_before_region_watermark(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeHttpxClient.instances.clear()
    RESPONSES.clear()
    RESPONSES.update(
        {
            "/MarketOrdersTrades/": '<a href="2026/">2026/</a>',
            "/MarketOrdersTrades/2026/": '<a href="marketOrderTrades_weekly_2026-12.csv">week 12</a>',
            "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv": (
                "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
                "60003760;10000002;34;1;0;2026-03-22;10;5.0;5.0;5.0;1;50\n"
                "60003760;10000002;34;1;0;2026-03-23;12;5.0;5.0;5.0;1;60\n"
            ),
        }
    )
    monkeypatch.setattr("app.services.adam4eve.client.httpx.Client", FakeHttpxClient)

    rows = Adam4EveClient().fetch_npc_demand(
        [60003760],
        [34],
        synced_through_by_region={10000002: date(2026, 3, 22)},
    )

    assert rows == [
        {
            "location_id": 60003760,
            "type_id": 34,
            "demand_day": 12.0,
            "source": "adam4eve",
            "date": "2026-03-23",
        }
    ]


def test_fetch_regional_price_history_requests_only_missing_daily_region_exports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeHttpxClient.instances.clear()
    RESPONSES.clear()
    RESPONSES.update(
        {
            "/MarketPricesRegionHistory/": '<a href="2025/">2025/</a><a href="2026/">2026/</a>',
            "/MarketPricesRegionHistory/2026/": (
                '<a href="marketPrice_10000002_daily_2026-03-19.csv">old</a>'
                '<a href="marketPrice_10000002_daily_2026-03-20.csv">skip</a>'
                '<a href="marketPrice_10000002_daily_2026-03-21.csv">take</a>'
                '<a href="marketPrice_10000043_daily_2026-03-21.csv">other region</a>'
            ),
            "/MarketPricesRegionHistory/2026/marketPrice_10000002_daily_2026-03-21.csv": (
                "type_id;region_id;date;buy_price_low;buy_price_avg;buy_price_high;sell_price_low;"
                "sell_price_avg;sell_price_high\n"
                "34;10000002;2026-03-21;4.1;4.2;4.3;5.1;5.2;5.3\n"
                "35;10000002;2026-03-21;7.1;7.2;7.3;8.1;8.2;8.3\n"
            ),
        }
    )
    monkeypatch.setattr("app.services.adam4eve.client.httpx.Client", FakeHttpxClient)

    rows = Adam4EveClient().fetch_regional_price_history(10000002, [34], since_date=date(2026, 3, 20))

    assert rows == [
        {
            "type_id": 34,
            "date": "2026-03-21",
            "average": 5.2,
            "highest": 5.3,
            "lowest": 5.1,
            "order_count": 0,
            "volume": 0,
        }
    ]
    assert FakeHttpxClient.instances[0].calls == [
        "/MarketPricesRegionHistory/",
        "/MarketPricesRegionHistory/2026/",
        "/MarketPricesRegionHistory/2026/marketPrice_10000002_daily_2026-03-21.csv",
    ]


def test_fetch_regional_price_history_rejects_malformed_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeHttpxClient.instances.clear()
    RESPONSES.clear()
    RESPONSES.update(
        {
            "/MarketPricesRegionHistory/": '<a href="2026/">2026/</a>',
            "/MarketPricesRegionHistory/2026/": '<a href="marketPrice_10000002_daily_2026-03-21.csv">take</a>',
            "/MarketPricesRegionHistory/2026/marketPrice_10000002_daily_2026-03-21.csv": (
                "type_id;region_id;date;sell_price_low;sell_price_high\n"
                "34;10000002;2026-03-21;5.1;5.3\n"
            ),
        }
    )
    monkeypatch.setattr("app.services.adam4eve.client.httpx.Client", FakeHttpxClient)

    with pytest.raises(ValueError, match="missing required columns"):
        Adam4EveClient().fetch_regional_price_history(10000002, [34], since_date=None)


@pytest.mark.parametrize(
    ("csv_text", "expected_message"),
    [
        (
            "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;high;low;avg;orderNum;iskValue\n"
            "60003760;10000002;34;1;0;2026-03-20;5.0;5.0;5.0;1;50\n",
            "missing required columns",
        ),
        (
            "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
            "60003760;10000002;34;1;0;not-a-date;10;5.0;5.0;5.0;1;50\n",
            "market orders export row is malformed",
        ),
    ],
)
def test_fetch_npc_demand_rejects_malformed_responses(
    monkeypatch: pytest.MonkeyPatch,
    csv_text: str,
    expected_message: str,
) -> None:
    FakeHttpxClient.instances.clear()
    RESPONSES.clear()
    RESPONSES.update(
        {
            "/MarketOrdersTrades/": '<a href="2026/">2026/</a>',
            "/MarketOrdersTrades/2026/": '<a href="marketOrderTrades_weekly_2026-12.csv">week 12</a>',
            "/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv": csv_text,
        }
    )
    monkeypatch.setattr("app.services.adam4eve.client.httpx.Client", FakeHttpxClient)

    with pytest.raises(ValueError, match=expected_message):
        Adam4EveClient().fetch_npc_demand([60003760], [34])
