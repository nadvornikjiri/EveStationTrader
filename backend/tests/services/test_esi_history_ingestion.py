from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.all_models import EsiHistoryDaily, Item, Location, Region, System
from app.services.esi.history_ingestion import EsiRegionalHistoryRecord, EsiRegionalHistoryIngestionService
from app.services.pricing.market_price_periods import MarketPricePeriodService
from app.services.sync.service import SyncService


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


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

    service = SyncService(
        session_factory=lambda: session,
        esi_client=StubEsiClient(),
    )

    response = service.trigger_job("esi_history_sync")
    result = MarketPricePeriodService().upsert_from_history(
        session,
        location_id=location_id,
        type_id=item_ids[0],
        period_days=2,
        warning_threshold=0.05,
    )

    assert response.records_processed == 2
    assert response.target_type == "region"
    assert response.target_id == "10000002"
    assert "Synced ESI history" in (response.message or "")
    assert result.row is not None
    assert result.history_points_used == 2
    assert result.row.current_price == 100.0
    assert result.row.period_avg_price == 105.0
    assert result.row.price_min == 90.0
    assert result.row.price_max == 130.0
    assert result.row.warning_flag is False
