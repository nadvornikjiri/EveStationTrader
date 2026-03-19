from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Iterable

from .config import ESI_BASE_URL
from .models import MarketOrder


class EsiClient:
    def __init__(self, user_agent: str, datasource: str = "tranquility", timeout_seconds: int = 60) -> None:
        self.user_agent = user_agent
        self.datasource = datasource
        self.timeout_seconds = timeout_seconds

    def fetch_region_orders(self, region_id: int) -> list[MarketOrder]:
        query = {
            "datasource": self.datasource,
            "order_type": "all",
            "page": 1,
        }
        first_page, headers = self._get_json(f"/markets/{region_id}/orders/", query)
        total_pages = int(headers.get("X-Pages", "1"))
        rows = list(first_page)

        for page in range(2, total_pages + 1):
            query["page"] = page
            page_rows, _ = self._get_json(f"/markets/{region_id}/orders/", query)
            rows.extend(page_rows)

        return [
            MarketOrder(
                type_id=int(row["type_id"]),
                location_id=int(row["location_id"]),
                is_buy_order=bool(row["is_buy_order"]),
                price=float(row["price"]),
                volume_remain=int(row["volume_remain"]),
                min_volume=int(row["min_volume"]),
                range=str(row["range"]),
            )
            for row in rows
        ]

    def resolve_names(self, ids: Iterable[int]) -> dict[int, str]:
        values = [int(value) for value in ids]
        if not values:
            return {}

        path = f"/universe/names/?datasource={urllib.parse.quote(self.datasource)}"
        resolved: dict[int, str] = {}
        for chunk in _chunked(values, size=1000):
            payload = json.dumps(chunk).encode("utf-8")
            data, _ = self._request_json("POST", path, payload, {"Content-Type": "application/json"})
            resolved.update({int(row["id"]): str(row["name"]) for row in data})
        return resolved

    def _get_json(self, path: str, query: dict[str, Any]) -> tuple[Any, dict[str, str]]:
        encoded = urllib.parse.urlencode(query)
        return self._request_json("GET", f"{path}?{encoded}", None, {})

    def _request_json(
        self,
        method: str,
        path_with_query: str,
        payload: bytes | None,
        extra_headers: dict[str, str],
    ) -> tuple[Any, dict[str, str]]:
        request = urllib.request.Request(
            url=f"{ESI_BASE_URL}{path_with_query}",
            method=method,
            data=payload,
            headers={
                "Accept": "application/json",
                "User-Agent": self.user_agent,
                **extra_headers,
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
            headers = {key: value for key, value in response.headers.items()}
            return data, headers


def _chunked(values: list[int], size: int) -> Iterable[list[int]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]
