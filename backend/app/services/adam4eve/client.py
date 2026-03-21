from collections.abc import Iterable
from datetime import UTC, datetime

from app.services.adam4eve.ingestion import AdamNpcDemandRecord


class Adam4EveClient:
    def fetch_npc_demand(self, location_ids: Iterable[int], type_ids: Iterable[int]) -> list[AdamNpcDemandRecord]:
        # TODO: Replace with real Adam4EVE integration during ingestion phase.
        today = datetime.now(UTC).date().isoformat()
        return [
            {
                "location_id": location_id,
                "type_id": type_id,
                "demand_day": 12.0,
                "source": "adam4eve",
                "date": today,
            }
            for location_id in location_ids
            for type_id in type_ids
        ]
