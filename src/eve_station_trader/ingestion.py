from __future__ import annotations

from dataclasses import asdict

from .models import Hub
from .service import TraderService


class IngestionService:
    def __init__(self, trader_service: TraderService) -> None:
        self.trader_service = trader_service

    def ingest_hub_region(self, hub: Hub, *, refresh: bool = True) -> dict[str, object]:
        orders = self.trader_service.fetch_region_orders(
            hub.region_id,
            refresh=refresh,
            prefer_database=False,
            persist_to_database=True,
        )
        snapshot = self.trader_service.database.region_snapshot(hub.region_id)
        return {
            "hub": asdict(hub),
            "region_id": hub.region_id,
            "orders_written": len(orders),
            "snapshot": snapshot,
        }

    def ingest_known_hubs(self, *, refresh: bool = True) -> dict[str, object]:
        ingested_regions: set[int] = set()
        results: list[dict[str, object]] = []
        for hub in self.trader_service.known_hubs():
            if hub.region_id in ingested_regions:
                continue
            results.append(self.ingest_hub_region(hub, refresh=refresh))
            ingested_regions.add(hub.region_id)

        return {
            "regions": results,
            "count": len(results),
        }

    def status(self) -> dict[str, object]:
        snapshots = self.trader_service.database.all_region_snapshots()
        region_names = {hub.region_id: hub.name for hub in self.trader_service.known_hubs()}
        return {
            "database_path": str(self.trader_service.database.path),
            "regions": [
                {
                    **snapshot,
                    "region_name": region_names.get(int(snapshot["region_id"]), f"Region {snapshot['region_id']}"),
                }
                for snapshot in snapshots
            ],
        }
