from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import EsiHistoryDaily, EsiMarketOrder, Item, Location, MarketPricePeriod, Region, System
from app.services.esi.history_ingestion import EsiRegionalHistoryRecord, EsiRegionalHistoryIngestionService
from app.services.sync.service import SyncService
from tests.db_test_utils import build_test_session


def build_session() -> Session:
    return build_test_session()


def seed_region_location_and_items(session: Session) -> tuple[int, list[int], int]:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    session.add(system)
    session.flush()

    location = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=system.id,
        region_id=region.id,
        name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    )
    items = [
        Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material"),
        Item(type_id=35, name="Pyerite", volume_m3=0.01, group_name="Mineral", category_name="Material"),
    ]
    session.add(location)
    session.add_all(items)
    session.commit()
    return location.id, [item.id for item in items], region.id


def test_ingest_region_history_persists_internal_rows() -> None:
    session = build_session()
    _location_id, item_ids, region_id = seed_region_location_and_items(session)

    result = EsiRegionalHistoryIngestionService().ingest_region_history(
        session,
        eve_region_id=10000002,
        records=[
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
                "date": "2026-03-20",
                "average": 200.0,
                "highest": 220.0,
                "lowest": 180.0,
                "order_count": 15,
                "volume": 500,
            },
        ],
    )

    rows = session.scalars(select(EsiHistoryDaily).order_by(EsiHistoryDaily.type_id.asc())).all()

    assert result.region_id == region_id
    assert result.records_processed == 2
    assert result.created == 2
    assert result.updated == 0
    assert len(rows) == 2
    assert rows[0].type_id == item_ids[0]
    assert rows[0].date == date(2026, 3, 20)
    assert rows[0].average == 100.0
    assert rows[0].volume == 1_000
    assert rows[1].type_id == item_ids[1]
    assert rows[1].average == 200.0


def test_ingest_region_history_is_idempotent_and_updates_existing_row() -> None:
    session = build_session()
    seed_region_location_and_items(session)
    service = EsiRegionalHistoryIngestionService()

    first = service.ingest_region_history(
        session,
        eve_region_id=10000002,
        records=[
            {
                "type_id": 34,
                "date": "2026-03-20",
                "average": 100.0,
                "highest": 120.0,
                "lowest": 90.0,
                "order_count": 25,
                "volume": 1_000,
            }
        ],
    )
    second = service.ingest_region_history(
        session,
        eve_region_id=10000002,
        records=[
            {
                "type_id": 34,
                "date": "2026-03-20",
                "average": 105.0,
                "highest": 125.0,
                "lowest": 95.0,
                "order_count": 30,
                "volume": 1_200,
            }
        ],
    )

    rows = session.scalars(select(EsiHistoryDaily)).all()

    assert first.created == 1
    assert first.updated == 0
    assert second.created == 0
    assert second.updated == 1
    assert len(rows) == 1
    assert rows[0].average == 105.0
    assert rows[0].highest == 125.0
    assert rows[0].lowest == 95.0
    assert rows[0].order_count == 30
    assert rows[0].volume == 1_200


class StubEsiClient:
    def fetch_regional_history(self, region_id: int, type_ids: list[int]) -> list[EsiRegionalHistoryRecord]:
        del region_id
        return [
            {
                "type_id": type_ids[0],
                "date": "2026-03-20",
                "average": 100.0,
                "highest": 120.0,
                "lowest": 90.0,
                "order_count": 25,
                "volume": 1_000,
            },
            {
                "type_id": type_ids[0],
                "date": "2026-03-19",
                "average": 110.0,
                "highest": 130.0,
                "lowest": 95.0,
                "order_count": 20,
                "volume": 900,
            },
        ]


def test_sync_service_esi_history_sync_feeds_market_price_period_computation() -> None:
    session = build_session()
    location_id, item_ids, _region_id = seed_region_location_and_items(session)
    location = session.scalar(select(Location).where(Location.id == location_id))
    assert location is not None
    session.add(
        EsiMarketOrder(
            order_id=9001,
            region_id=location.region_id,
            location_id=location.id,
            type_id=item_ids[0],
            system_id=location.system_id,
            is_buy_order=False,
            price=4.12,
            volume_total=1000,
            volume_remain=400,
            min_volume=1,
            order_range="region",
            issued=datetime.now(UTC),
            duration=90,
        )
    )
    session.commit()

    service = SyncService(
        session_factory=lambda: session,
        esi_client=StubEsiClient(),
    )

    response = service.trigger_job("esi_history_sync")
    result = session.scalar(
        select(MarketPricePeriod).where(
            MarketPricePeriod.location_id == location_id,
            MarketPricePeriod.type_id == item_ids[0],
            MarketPricePeriod.period_days == 3,
        )
    )

    assert response.records_processed == 6
    assert response.target_type == "regions"
    assert response.target_id == "1"
    assert "Synced ESI history" in (response.message or "")
    assert "price periods" in (response.message or "")
    assert result is not None
    assert result.current_price == 100.0
    assert result.period_avg_price == 105.0
    assert result.price_min == 90.0
    assert result.price_max == 130.0
    assert result.warning_flag is False
