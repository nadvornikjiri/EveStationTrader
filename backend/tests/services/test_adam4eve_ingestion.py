from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import AdamNpcDemandDaily, AdamNpcDemandSyncState, Item, Location, Region, System
from app.services.adam4eve.ingestion import AdamNpcDemandIngestionService, AdamNpcDemandRecord
from app.services.esi.history_ingestion import EsiRegionalHistoryRecord
from app.services.sync.service import SyncService
from tests.db_test_utils import build_test_session


def build_session() -> Session:
    return build_test_session()


def seed_locations_and_items(session: Session) -> tuple[list[int], list[int]]:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    session.add(system)
    session.flush()

    locations = [
        Location(
            location_id=60003760,
            location_type="npc_station",
            system_id=system.id,
            region_id=region.id,
            name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
        ),
        Location(
            location_id=60008494,
            location_type="npc_station",
            system_id=system.id,
            region_id=region.id,
            name="Amarr VIII (Oris) - Emperor Family Academy",
        ),
    ]
    items = [
        Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material"),
        Item(type_id=35, name="Pyerite", volume_m3=0.01, group_name="Mineral", category_name="Material"),
    ]
    session.add_all(locations)
    session.add_all(items)
    session.commit()
    return [location.id for location in locations], [item.id for item in items]


def test_ingest_npc_demand_persists_internal_rows() -> None:
    session = build_session()
    location_ids, item_ids = seed_locations_and_items(session)

    result = AdamNpcDemandIngestionService().ingest_npc_demand(
        session,
        records=[
            {
                "location_id": 60003760,
                "type_id": 34,
                "demand_day": 12.5,
                "source": "adam4eve",
                "date": "2026-03-20",
            },
            {
                "location_id": 60008494,
                "type_id": 35,
                "demand_day": 8.0,
                "source": "adam4eve",
                "date": "2026-03-20",
            },
        ],
    )

    rows = session.scalars(
        select(AdamNpcDemandDaily).order_by(AdamNpcDemandDaily.location_id.asc(), AdamNpcDemandDaily.type_id.asc())
    ).all()

    assert result.records_processed == 2
    assert result.created == 2
    assert result.updated == 0
    assert len(rows) == 2
    assert rows[0].location_id == location_ids[0]
    assert rows[0].type_id == item_ids[0]
    assert rows[0].demand_day == 12.5
    assert rows[1].location_id == location_ids[1]
    assert rows[1].type_id == item_ids[1]
    assert rows[1].demand_day == 8.0


def test_ingest_npc_demand_appends_new_history_rows_without_updating_existing_row() -> None:
    session = build_session()
    seed_locations_and_items(session)
    service = AdamNpcDemandIngestionService()

    first = service.ingest_npc_demand(
        session,
        records=[
            {
                "location_id": 60003760,
                "type_id": 34,
                "demand_day": 12.5,
                "source": "adam4eve",
                "date": "2026-03-20",
            }
        ],
    )
    second = service.ingest_npc_demand(
        session,
        records=[
            {
                "location_id": 60003760,
                "type_id": 34,
                "demand_day": 14.0,
                "source": "adam4eve",
                "date": "2026-03-21",
                "raw_payload": {"custom": True},
            }
        ],
    )

    rows = session.scalars(select(AdamNpcDemandDaily).order_by(AdamNpcDemandDaily.date.asc())).all()

    assert first.created == 1
    assert first.updated == 0
    assert second.created == 1
    assert second.updated == 0
    assert len(rows) == 2
    assert rows[0].date == date(2026, 3, 20)
    assert rows[0].demand_day == 12.5
    assert rows[1].date == date(2026, 3, 21)
    assert rows[1].demand_day == 14.0
    assert rows[1].raw_payload == {"custom": True}


class StubAdamClient:
    def resolve_latest_market_orders_export(self):
        from app.services.adam4eve.client import AdamMarketOrdersExport

        return AdamMarketOrdersExport(
            path="/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv",
            export_key="2026-12",
            covered_through_date=date(2026, 3, 22),
        )

    def fetch_npc_demand(
        self,
        location_ids: list[int],
        type_ids: list[int],
        *,
        export_path: str | None = None,
        synced_through_by_region: dict[int, date] | None = None,
    ) -> list[AdamNpcDemandRecord]:
        del export_path
        del synced_through_by_region
        return [
            {
                "location_id": location_ids[0],
                "type_id": type_ids[0],
                "demand_day": 20.0,
                "source": "adam4eve",
                "date": "2026-03-20",
            },
            {
                "location_id": location_ids[1],
                "type_id": type_ids[1],
                "demand_day": 10.0,
                "source": "adam4eve",
                "date": datetime.now(UTC).date().isoformat(),
            },
        ]

    def fetch_regional_price_history(
        self,
        region_id: int,
        type_ids: list[int],
        *,
        since_date: date | None = None,
    ) -> list[EsiRegionalHistoryRecord]:
        del region_id, type_ids, since_date
        return []


def test_sync_service_adam4eve_sync_persists_npc_demand_rows() -> None:
    session = build_session()
    seed_locations_and_items(session)
    service = SyncService(
        session_factory=lambda: session,
        adam_client=StubAdamClient(),
    )

    response = service.trigger_job("adam4eve_sync")
    rows = session.scalars(select(AdamNpcDemandDaily).order_by(AdamNpcDemandDaily.demand_day.desc())).all()
    sync_states = session.scalars(select(AdamNpcDemandSyncState).order_by(AdamNpcDemandSyncState.region_id.asc())).all()

    assert response.records_processed == 4
    assert response.target_type == "locations"
    assert response.target_id == "2"
    assert "Synced Adam4EVE demand and regional price history" in (response.message or "")
    assert "resolved demand rows" in (response.message or "")
    assert len(rows) == 2
    assert rows[0].demand_day == 20.0
    assert rows[1].demand_day == 10.0
    assert len(sync_states) == 1
    assert sync_states[0].export_key == "2026-12"
    assert sync_states[0].synced_through_date == datetime.now(UTC).date()
