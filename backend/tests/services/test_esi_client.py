from __future__ import annotations

from collections.abc import Mapping

import pytest

from app.services.esi import client as esi_client_module
from app.services.esi.client import EsiClient


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class FakeHttpxClient:
    instances: list["FakeHttpxClient"] = []
    payloads: dict[int, object] = {}

    def __init__(self, *, base_url: str, headers: Mapping[str, str], timeout: float) -> None:
        self.base_url = base_url
        self.headers = dict(headers)
        self.timeout = timeout
        self.calls: list[tuple[str, dict[str, int]]] = []
        FakeHttpxClient.instances.append(self)

    def __enter__(self) -> "FakeHttpxClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def get(self, path: str, params: dict[str, int]) -> FakeResponse:
        self.calls.append((path, dict(params)))
        type_id = params["type_id"]
        return FakeResponse(self.payloads[type_id])


def test_fetch_regional_history_requests_each_type_and_normalizes_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeHttpxClient.instances.clear()
    FakeHttpxClient.payloads = {
        34: [
            {
                "date": "2026-03-20",
                "average": 100,
                "highest": 120,
                "lowest": 90,
                "order_count": 25,
                "volume": 1_000,
            }
        ],
        35: [
            {
                "date": "2026-03-19",
                "average": 200.5,
                "highest": 220,
                "lowest": 180,
                "order_count": 15,
                "volume": 500,
            }
        ],
    }
    monkeypatch.setattr(esi_client_module.httpx, "Client", FakeHttpxClient)

    client = EsiClient()
    history = client.fetch_regional_history(10000002, [34, 35])

    assert len(FakeHttpxClient.instances) == 1
    fake_client = FakeHttpxClient.instances[0]
    assert fake_client.base_url == "https://esi.evetech.net/latest"
    assert fake_client.headers["User-Agent"] == client.get_headers()["User-Agent"]
    assert fake_client.headers["X-Compatibility-Date"] == client.get_headers()["X-Compatibility-Date"]
    assert fake_client.calls == [
        ("/markets/10000002/history/", {"type_id": 34}),
        ("/markets/10000002/history/", {"type_id": 35}),
    ]
    assert history == [
        {
            "type_id": 34,
            "date": "2026-03-20",
            "average": 100.0,
            "highest": 120.0,
            "lowest": 90.0,
            "order_count": 25,
            "volume": 1_000,
        },
        {
            "type_id": 35,
            "date": "2026-03-19",
            "average": 200.5,
            "highest": 220.0,
            "lowest": 180.0,
            "order_count": 15,
            "volume": 500,
        },
    ]


def test_fetch_regional_history_returns_empty_list_for_empty_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeHttpxClient.instances.clear()
    FakeHttpxClient.payloads = {34: []}
    monkeypatch.setattr(esi_client_module.httpx, "Client", FakeHttpxClient)

    history = EsiClient().fetch_regional_history(10000002, [34])

    assert history == []


@pytest.mark.parametrize(
    ("payload", "expected_message"),
    [
        ({"history": []}, "must be a list of rows"),
        (
            [
                {
                    "date": "2026-03-20",
                    "average": 100,
                    "highest": 120,
                    "lowest": 90,
                    "order_count": 25,
                }
            ],
            "must include integer 'volume'",
        ),
    ],
)
def test_fetch_regional_history_rejects_malformed_payload(
    monkeypatch: pytest.MonkeyPatch,
    payload: object,
    expected_message: str,
) -> None:
    FakeHttpxClient.instances.clear()
    FakeHttpxClient.payloads = {34: payload}
    monkeypatch.setattr(esi_client_module.httpx, "Client", FakeHttpxClient)

    with pytest.raises(ValueError, match=expected_message):
        EsiClient().fetch_regional_history(10000002, [34])
