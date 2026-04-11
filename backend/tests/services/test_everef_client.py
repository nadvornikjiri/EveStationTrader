from __future__ import annotations

import bz2
from datetime import date

import pytest

from app.services.everef import client as everef_client


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload
        self.raise_for_status_called = False

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True

    def json(self) -> object:
        return self._payload


class FakeStreamResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self.raise_for_status_called = False

    def __enter__(self) -> "FakeStreamResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc_type, exc, tb

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True

    def iter_bytes(self):
        yield from self._chunks


def test_fetch_totals_json_returns_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "2026-04-10": {"size": 123, "hash": "abc"},
        "2026-04-09": {"size": 456, "hash": "def"},
    }

    def fake_get(url: str, *, timeout: float, follow_redirects: bool) -> FakeResponse:
        assert url == everef_client.TOTALS_URL
        assert timeout == 120.0
        assert follow_redirects is True
        return FakeResponse(payload)

    monkeypatch.setattr(everef_client.httpx, "get", fake_get)

    assert everef_client.fetch_totals_json() == payload


def test_get_available_dates_returns_previous_days(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDate(date):
        @classmethod
        def today(cls) -> "FakeDate":
            return cls(2026, 4, 11)

    monkeypatch.setattr(everef_client, "date", FakeDate)

    assert everef_client.get_available_dates(3) == [
        FakeDate(2026, 4, 8),
        FakeDate(2026, 4, 9),
        FakeDate(2026, 4, 10),
    ]


def test_download_history_file_decompresses_bz2_to_csv(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    csv_body = (
        "average,date,highest,lowest,order_count,volume,http_last_modified,region_id,type_id\n"
        "10.5,2026-04-10,11.0,9.5,7,999,2026-04-11T00:00:00Z,1,34\n"
    ).encode("utf-8")
    compressed = bz2.compress(csv_body)
    seen: list[tuple[str, float, bool]] = []

    def fake_stream(method: str, url: str, *, timeout: float, follow_redirects: bool) -> FakeStreamResponse:
        assert method == "GET"
        seen.append((url, timeout, follow_redirects))
        return FakeStreamResponse([compressed[:12], compressed[12:]])

    monkeypatch.setattr(everef_client.httpx, "stream", fake_stream)

    csv_path = everef_client.download_history_file(date(2026, 4, 10), tmp_path)

    assert seen == [
        ("https://data.everef.net/market-history/2026/market-history-2026-04-10.csv.bz2", 120.0, True)
    ]
    assert csv_path == tmp_path / "market-history-2026-04-10.csv"
    assert csv_path.read_text(encoding="utf-8") == csv_body.decode("utf-8")
    assert (tmp_path / "market-history-2026-04-10.csv.bz2").read_bytes() == compressed

