from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, replace
from pathlib import Path

from .analysis import AnalysisSettings, find_opportunities, summarize_hub_orders
from .cache import JsonCache
from .config import (
    DEFAULT_CACHE_DIR,
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_DB_PATH,
    DEFAULT_USER_AGENT,
    KNOWN_HUBS,
)
from .db import MarketDatabase
from .esi import EsiClient
from .models import Hub, MarketOrder, Opportunity


class TraderService:
    def __init__(
        self,
        cache_dir: Path | None = None,
        database_path: Path | None = None,
        cache_ttl: int = DEFAULT_CACHE_TTL_SECONDS,
        datasource: str = "tranquility",
        user_agent: str | None = None,
    ) -> None:
        self.cache = JsonCache(cache_dir or DEFAULT_CACHE_DIR, cache_ttl)
        self.database = MarketDatabase(database_path or DEFAULT_DB_PATH)
        self.client = EsiClient(
            user_agent=user_agent or os.getenv("EVE_STATION_TRADER_USER_AGENT", DEFAULT_USER_AGENT),
            datasource=datasource,
        )

    def known_hubs(self) -> list[Hub]:
        return list(KNOWN_HUBS.values())

    def resolve_hub(self, hub_key: str | None, region_id: int | None, location_id: int | None) -> Hub:
        if region_id is not None or location_id is not None:
            if region_id is None or location_id is None:
                raise ValueError("Both region_id and location_id are required for a custom hub.")
            label = hub_key or f"custom-{location_id}"
            return Hub(
                key=label,
                name=f"Custom hub {location_id}",
                region_id=region_id,
                location_id=location_id,
            )

        if not hub_key:
            raise ValueError("A hub key is required when custom ids are not supplied.")

        try:
            return KNOWN_HUBS[hub_key]
        except KeyError as exc:
            raise ValueError(f"Unknown hub key: {hub_key}") from exc

    def scan(
        self,
        *,
        source_hub_key: str | None = None,
        destination_hub_key: str | None = None,
        source_region_id: int | None = None,
        source_location_id: int | None = None,
        destination_region_id: int | None = None,
        destination_location_id: int | None = None,
        strategy: str,
        minimum_profit: float,
        minimum_roi_percent: float,
        sales_tax: float,
        destination_broker_fee: float,
        top_n: int,
        refresh: bool = False,
    ) -> dict[str, object]:
        source_hub = self.resolve_hub(source_hub_key, source_region_id, source_location_id)
        destination_hub = self.resolve_hub(destination_hub_key, destination_region_id, destination_location_id)

        source_orders = self.fetch_region_orders(source_hub.region_id, refresh, prefer_database=True)
        destination_orders = self.fetch_region_orders(destination_hub.region_id, refresh, prefer_database=True)
        source_summary = summarize_hub_orders(source_orders, source_hub)
        destination_summary = summarize_hub_orders(destination_orders, destination_hub)

        settings = AnalysisSettings(
            sales_tax=sales_tax,
            destination_broker_fee=destination_broker_fee,
            minimum_profit=minimum_profit,
            minimum_roi_percent=minimum_roi_percent,
            top_n=top_n,
            strategy=strategy,
        )

        opportunities = find_opportunities(
            source_hub=source_hub,
            destination_hub=destination_hub,
            source_orders=source_summary,
            destination_orders=destination_summary,
            item_names={},
            settings=settings,
        )
        item_names = self.resolve_item_names({item.type_id for item in opportunities}, refresh)
        opportunities = [
            replace(opportunity, item_name=item_names.get(opportunity.type_id, opportunity.item_name))
            for opportunity in opportunities
        ]

        return {
            "source_hub": asdict(source_hub),
            "destination_hub": asdict(destination_hub),
            "strategy": strategy,
            "data_source": self._scan_data_source(source_hub.region_id, destination_hub.region_id, refresh),
            "count": len(opportunities),
            "opportunities": [serialize_opportunity(item) for item in opportunities],
        }

    def fetch_region_orders(
        self,
        region_id: int,
        refresh: bool,
        prefer_database: bool = True,
        persist_to_database: bool = False,
    ) -> list[MarketOrder]:
        if prefer_database and not refresh:
            stored = self.database.get_region_orders(region_id)
            if stored:
                return stored

        cache_key = f"region-orders-{region_id}"
        if not refresh:
            cached = self.cache.load(cache_key)
            if cached is not None:
                orders = [MarketOrder(**row) for row in cached]
                if persist_to_database:
                    self.database.replace_region_orders(region_id, orders, source="cache")
                return orders

        orders = self.client.fetch_region_orders(region_id)
        self.cache.store(cache_key, [asdict(order) for order in orders])
        if persist_to_database or prefer_database:
            self.database.replace_region_orders(region_id, orders, source="esi")
        return orders

    def resolve_item_names(self, type_ids: set[int], refresh: bool) -> dict[int, str]:
        if not type_ids:
            return {}

        if not refresh:
            cached_names = self.database.get_item_names(type_ids)
            if len(cached_names) == len(type_ids):
                return cached_names

        digest = hashlib.sha1(",".join(str(type_id) for type_id in sorted(type_ids)).encode("utf-8")).hexdigest()
        cache_key = f"type-names-{digest}"
        if not refresh:
            cached = self.cache.load(cache_key)
            if cached is not None:
                names = {int(key): str(value) for key, value in cached.items()}
                self.database.upsert_item_names(names)
                return names

        names = self.client.resolve_names(type_ids)
        self.cache.store(cache_key, names)
        self.database.upsert_item_names(names)
        return names

    def _scan_data_source(self, source_region_id: int, destination_region_id: int, refresh: bool) -> str:
        if refresh:
            return "esi"
        if self.database.region_order_count(source_region_id) and self.database.region_order_count(destination_region_id):
            return "database"
        return "esi-cache"


def serialize_opportunity(opportunity: Opportunity) -> dict[str, object]:
    return asdict(opportunity)
