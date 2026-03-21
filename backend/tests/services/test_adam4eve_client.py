from __future__ import annotations

from collections.abc import Mapping

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
