from __future__ import annotations

from collections.abc import Mapping

import httpx
import pytest

from app.services.esi import client as esi_client_module
from app.services.esi.client import EsiClient


class FakeResponse:
    def __init__(
        self,
        payload: object,
        *,
        headers: Mapping[str, str] | None = None,
        status_code: int = 200,
    ) -> None:
        self.payload = payload
        self.headers = httpx.Headers(dict(headers or {}))
        self.status_code = status_code
        self.request = httpx.Request("GET", "https://esi.evetech.net/latest/test")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("request failed", request=self.request, response=self)  # type: ignore[arg-type]
        return None

    def json(self) -> object:
        return self.payload


class FakeHttpxClient:
    instances: list["FakeHttpxClient"] = []
    responses: dict[tuple[str, tuple[tuple[str, int | str], ...]], FakeResponse] = {}

    def __init__(self, *, base_url: str, headers: Mapping[str, str], timeout: float) -> None:
        self.base_url = base_url
        self.headers = dict(headers)
        self.timeout = timeout
        self.calls: list[tuple[str, dict[str, int | str]]] = []
        FakeHttpxClient.instances.append(self)

    def __enter__(self) -> "FakeHttpxClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def get(self, path: str, params: dict[str, int | str] | None = None) -> FakeResponse:
        normalized_params = dict(params or {})
        self.calls.append((path, normalized_params))
        key = (path, tuple(sorted(normalized_params.items())))
        return self.responses[key]

    def request(
        self,
        method: str,
        url: str,
        params: dict[str, int | str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> FakeResponse:
        normalized_params = dict(params or {})
        self.calls.append((url, normalized_params))
        key = (url, tuple(sorted(normalized_params.items())))
        return self.responses[key]


def test_fetch_universe_data_requests_paginated_types_and_normalizes_seed_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeHttpxClient.instances.clear()
    FakeHttpxClient.responses = {
        ("/universe/regions/", ()): FakeResponse([10000002]),
        ("/universe/regions/10000002/", ()): FakeResponse({"name": "The Forge"}),
        ("/universe/systems/", ()): FakeResponse([30000142]),
        ("/universe/systems/30000142/", ()): FakeResponse(
            {"name": "Jita", "security_status": 0.9, "constellation_id": 20000020}
        ),
        ("/universe/constellations/20000020/", ()): FakeResponse({"region_id": 10000002}),
        ("/universe/types/", (("page", 1),)): FakeResponse([34], headers={"X-Pages": "1"}),
        ("/universe/types/34/", ()): FakeResponse({"name": "Tritanium", "volume": 0.01, "group_id": 18}),
    }
    monkeypatch.setattr(esi_client_module.httpx, "Client", FakeHttpxClient)

    client = EsiClient()
    regions = client.fetch_universe_regions()
    systems = client.fetch_universe_systems()
    items = client.fetch_universe_items()

    assert regions == [esi_client_module.RegionSeed(region_id=10000002, name="The Forge")]
    assert systems == [
        esi_client_module.SystemSeed(
            system_id=30000142,
            region_id=10000002,
            name="Jita",
            security_status=0.9,
        )
    ]
    assert items == [
        esi_client_module.ItemSeed(
            type_id=34,
            name="Tritanium",
            volume_m3=0.01,
            group_name="18",
            category_name=None,
        )
    ]


def test_fetch_regional_orders_requests_all_pages_and_normalizes_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeHttpxClient.instances.clear()
    FakeHttpxClient.responses = {
        ("/markets/10000002/orders/", (("order_type", "all"), ("page", 1))): FakeResponse(
            [
                {
                    "order_id": 9001,
                    "type_id": 34,
                    "location_id": 60003760,
                    "system_id": 30000142,
                    "is_buy_order": False,
                    "price": 4.12,
                    "volume_total": 1000,
                    "volume_remain": 400,
                    "min_volume": 1,
                    "range": "region",
                    "issued": "2026-03-23T09:00:00Z",
                    "duration": 90,
                }
            ],
            headers={"X-Pages": "2"},
        ),
        ("/markets/10000002/orders/", (("order_type", "all"), ("page", 2))): FakeResponse(
            [
                {
                    "order_id": 9002,
                    "type_id": 35,
                    "location_id": 60003760,
                    "system_id": 30000142,
                    "is_buy_order": True,
                    "price": 8.15,
                    "volume_total": 500,
                    "volume_remain": 200,
                    "min_volume": 5,
                    "range": "station",
                    "issued": "2026-03-23T10:00:00Z",
                    "duration": 30,
                }
            ]
        ),
    }
    monkeypatch.setattr(esi_client_module.httpx, "Client", FakeHttpxClient)

    rows = EsiClient().fetch_regional_orders(10000002)

    assert rows == [
        {
            "order_id": 9001,
            "type_id": 34,
            "location_id": 60003760,
            "system_id": 30000142,
            "is_buy_order": False,
            "price": 4.12,
            "volume_total": 1000,
            "volume_remain": 400,
            "min_volume": 1,
            "range": "region",
            "issued": "2026-03-23T09:00:00+00:00",
            "duration": 90,
        },
        {
            "order_id": 9002,
            "type_id": 35,
            "location_id": 60003760,
            "system_id": 30000142,
            "is_buy_order": True,
            "price": 8.15,
            "volume_total": 500,
            "volume_remain": 200,
            "min_volume": 5,
            "range": "station",
            "issued": "2026-03-23T10:00:00+00:00",
            "duration": 30,
        },
    ]


@pytest.mark.parametrize(
    ("method_name", "responses", "expected_message"),
    [
        (
            "fetch_universe_regions",
            {
                ("/universe/regions/", ()): FakeResponse({"regions": []}),
            },
            "region ids response must be a list of integers",
        ),
        (
            "fetch_regional_orders",
            {
                ("/markets/10000002/orders/", (("order_type", "all"), ("page", 1))): FakeResponse({"orders": []}),
            },
            "regional orders response must be a list of rows",
        ),
    ],
)
def test_esi_client_rejects_malformed_payloads(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    responses: dict[tuple[str, tuple[tuple[str, int | str], ...]], FakeResponse],
    expected_message: str,
) -> None:
    FakeHttpxClient.instances.clear()
    FakeHttpxClient.responses = responses
    monkeypatch.setattr(esi_client_module.httpx, "Client", FakeHttpxClient)

    client = EsiClient()

    with pytest.raises(ValueError, match=expected_message):
        if method_name == "fetch_universe_regions":
            client.fetch_universe_regions()
        else:
            client.fetch_regional_orders(10000002)


def test_rate_limit_state_tracks_headers() -> None:
    from app.services.esi.client import EsiRateLimitState

    state = EsiRateLimitState()
    assert state.error_limit_remain == 100
    assert state.total_requests == 0

    state.update_from_headers(httpx.Headers({"X-ESI-Error-Limit-Remain": "42", "X-ESI-Error-Limit-Reset": "30"}))
    assert state.error_limit_remain == 42
    assert state.error_limit_reset == 30
    assert state.total_requests == 1
    assert not state.should_backoff()

    state.update_from_headers(httpx.Headers({"X-ESI-Error-Limit-Remain": "10", "X-ESI-Error-Limit-Reset": "55"}))
    assert state.error_limit_remain == 10
    assert state.should_backoff()
    assert state.backoff_seconds() == 55.0
    assert state.total_requests == 2


def test_esi_client_updates_rate_limit_state_on_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeHttpxClient.instances.clear()
    FakeHttpxClient.responses = {
        ("/universe/regions/", ()): FakeResponse(
            [10000002],
            headers={"X-ESI-Error-Limit-Remain": "80", "X-ESI-Error-Limit-Reset": "45"},
        ),
        ("/universe/regions/10000002/", ()): FakeResponse(
            {"name": "The Forge"},
            headers={"X-ESI-Error-Limit-Remain": "79", "X-ESI-Error-Limit-Reset": "44"},
        ),
    }
    monkeypatch.setattr(esi_client_module.httpx, "Client", FakeHttpxClient)

    # Reset shared state
    EsiClient.rate_limit_state = esi_client_module.EsiRateLimitState()
    client = EsiClient()
    client.fetch_universe_regions()

    state = EsiClient.get_rate_limit_state()
    assert state.total_requests == 2
    assert state.error_limit_remain == 79
    assert state.error_limit_reset == 44

    state_dict = state.to_dict()
    assert state_dict["total_requests"] == 2
    assert state_dict["error_limit_remain"] == 79
