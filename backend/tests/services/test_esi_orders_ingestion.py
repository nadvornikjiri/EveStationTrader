from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import EsiMarketOrder, Item, Location, Region, System
from app.repositories.seed_data import StationSeed
from app.services.esi.orders_ingestion import EsiRegionOrderBatch, EsiRegionalOrderIngestionService
from tests.db_test_utils import build_test_session


def build_session() -> Session:
    return build_test_session()


class StubUniverseClient:
    def __init__(self, stations: dict[int, StationSeed] | None = None) -> None:
        self.stations = stations or {}

    def fetch_station(self, station_id: int) -> StationSeed:
        return self.stations[station_id]


def seed_region_system_item(session: Session) -> tuple[Region, System, Item]:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all([system, item])
    session.flush()
    session.commit()
    return region, system, item


def test_ingest_region_orders_replaces_region_snapshot_via_counts() -> None:
    session = build_session()
    region, system, item = seed_region_system_item(session)
    location = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=system.id,
        region_id=region.id,
        name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    )
    session.add(location)
    session.flush()
    session.add_all(
        [
            EsiMarketOrder(
                order_id=9001,
                region_id=region.id,
                location_id=location.id,
                type_id=item.id,
                system_id=system.id,
                is_buy_order=False,
                price=4.12,
                volume_total=1000,
                volume_remain=400,
                min_volume=1,
                order_range="region",
                issued=datetime(2026, 3, 23, 9, 0, tzinfo=UTC),
                duration=90,
            ),
            EsiMarketOrder(
                order_id=9003,
                region_id=region.id,
                location_id=location.id,
                type_id=item.id,
                system_id=system.id,
                is_buy_order=False,
                price=4.10,
                volume_total=1000,
                volume_remain=200,
                min_volume=1,
                order_range="region",
                issued=datetime(2026, 3, 22, 9, 0, tzinfo=UTC),
                duration=90,
            ),
        ]
    )
    session.commit()

    result = EsiRegionalOrderIngestionService().ingest_region_orders(
        session,
        eve_region_id=10000002,
        records=[
            {
                "order_id": 9001,
                "type_id": 34,
                "location_id": 60003760,
                "system_id": 30000142,
                "is_buy_order": False,
                "price": 4.20,
                "volume_total": 1000,
                "volume_remain": 350,
                "min_volume": 1,
                "range": "region",
                "issued": "2026-03-24T09:00:00+00:00",
                "duration": 90,
            },
            {
                "order_id": 9002,
                "type_id": 34,
                "location_id": 60003760,
                "system_id": 30000142,
                "is_buy_order": True,
                "price": 4.05,
                "volume_total": 800,
                "volume_remain": 800,
                "min_volume": 1,
                "range": "region",
                "issued": "2026-03-24T10:00:00+00:00",
                "duration": 90,
            },
        ],
        universe_client=StubUniverseClient(),
    )

    rows = session.scalars(select(EsiMarketOrder).order_by(EsiMarketOrder.order_id.asc())).all()

    assert result.records_processed == 2
    assert result.created == 1
    assert result.updated == 1
    assert result.deleted == 1
    assert [row.order_id for row in rows] == [9001, 9002]
    assert rows[0].price == 4.20
    assert rows[0].volume_remain == 350


def test_ingest_region_orders_creates_missing_station_location() -> None:
    session = build_session()
    region, system, item = seed_region_system_item(session)

    result = EsiRegionalOrderIngestionService().ingest_region_orders(
        session,
        eve_region_id=10000002,
        records=[
            {
                "order_id": 9001,
                "type_id": item.type_id,
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
            }
        ],
        universe_client=StubUniverseClient(
            stations={
                60003760: StationSeed(
                    station_id=60003760,
                    system_id=system.system_id,
                    region_id=region.region_id,
                    name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
                )
            }
        ),
    )

    location = session.scalar(select(Location).where(Location.location_id == 60003760))
    order = session.scalar(select(EsiMarketOrder).where(EsiMarketOrder.order_id == 9001))

    assert result.created == 1
    assert result.updated == 0
    assert result.deleted == 0
    assert result.stations_created == 1
    assert location is not None
    assert order is not None


def test_ingest_order_batches_deduplicates_duplicate_order_ids_in_postgres_stage() -> None:
    session = build_session()
    region, system, item = seed_region_system_item(session)
    location = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=system.id,
        region_id=region.id,
        name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    )
    session.add(location)
    session.commit()

    result = EsiRegionalOrderIngestionService().ingest_order_batches(
        session,
        region_batches=[
            EsiRegionOrderBatch(
                region_id=region.id,
                eve_region_id=region.region_id,
                records=[
                    {
                        "order_id": 9001,
                        "type_id": item.type_id,
                        "location_id": location.location_id,
                        "system_id": system.system_id,
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
                        "order_id": 9001,
                        "type_id": item.type_id,
                        "location_id": location.location_id,
                        "system_id": system.system_id,
                        "is_buy_order": False,
                        "price": 4.22,
                        "volume_total": 1000,
                        "volume_remain": 350,
                        "min_volume": 1,
                        "range": "region",
                        "issued": "2026-03-23T10:00:00+00:00",
                        "duration": 90,
                    },
                ],
            )
        ],
        universe_client=StubUniverseClient(),
    )

    rows = session.scalars(select(EsiMarketOrder).where(EsiMarketOrder.order_id == 9001)).all()

    assert result.records_processed == 2
    assert result.created == 1
    assert result.updated == 0
    assert len(rows) == 1
    assert rows[0].price == 4.22
    assert rows[0].volume_remain == 350


def test_ingest_region_orders_keeps_existing_location_when_market_region_differs() -> None:
    session = build_session()
    region, system, item = seed_region_system_item(session)
    special_region = Region(region_id=19000001, name="Special Region")
    session.add(special_region)
    session.flush()
    location = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=system.id,
        region_id=region.id,
        name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    )
    session.add(location)
    session.commit()

    result = EsiRegionalOrderIngestionService().ingest_order_batches(
        session,
        region_batches=[
            EsiRegionOrderBatch(
                region_id=special_region.id,
                eve_region_id=special_region.region_id,
                records=[
                    {
                        "order_id": 9004,
                        "type_id": item.type_id,
                        "location_id": location.location_id,
                        "system_id": system.system_id,
                        "is_buy_order": False,
                        "price": 4.30,
                        "volume_total": 1000,
                        "volume_remain": 1000,
                        "min_volume": 1,
                        "range": "region",
                        "issued": "2026-03-23T11:00:00+00:00",
                        "duration": 90,
                    }
                ],
            )
        ],
        universe_client=StubUniverseClient(),
    )

    order = session.scalar(select(EsiMarketOrder).where(EsiMarketOrder.order_id == 9004))

    assert result.created == 1
    assert result.skipped_non_npc_locations == 0
    assert order is not None
    assert order.location_id == location.id
    assert order.region_id == special_region.id


def test_ingest_region_orders_creates_placeholder_structure_location_for_public_structure() -> None:
    session = build_session()
    region, system, item = seed_region_system_item(session)
    structure_id = 1_035_603_743_755

    result = EsiRegionalOrderIngestionService().ingest_region_orders(
        session,
        eve_region_id=region.region_id,
        records=[
            {
                "order_id": 9005,
                "type_id": item.type_id,
                "location_id": structure_id,
                "system_id": system.system_id,
                "is_buy_order": False,
                "price": 5.10,
                "volume_total": 50,
                "volume_remain": 50,
                "min_volume": 1,
                "range": "region",
                "issued": "2026-03-23T12:00:00+00:00",
                "duration": 30,
            }
        ],
        universe_client=StubUniverseClient(),
    )

    location = session.scalar(select(Location).where(Location.location_id == structure_id))
    order = session.scalar(select(EsiMarketOrder).where(EsiMarketOrder.order_id == 9005))

    assert result.created == 1
    assert result.skipped_non_npc_locations == 0
    assert location is not None
    assert location.location_type == "structure"
    assert location.system_id == system.id
    assert order is not None
    assert order.location_id == location.id


def test_delete_orders_by_ids_batches_large_parameter_sets() -> None:
    session = build_session()
    region, system, item = seed_region_system_item(session)
    location = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=system.id,
        region_id=region.id,
        name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    )
    session.add(location)
    session.flush()
    session.add_all(
        [
            EsiMarketOrder(
                order_id=order_id,
                region_id=region.id,
                location_id=location.id,
                type_id=item.id,
                system_id=system.id,
                is_buy_order=False,
                price=4.12,
                volume_total=1000,
                volume_remain=400,
                min_volume=1,
                order_range="region",
                issued=datetime(2026, 3, 23, 9, 0, tzinfo=UTC),
                duration=90,
            )
            for order_id in range(10_000, 16_100)
        ]
    )
    session.commit()

    service = EsiRegionalOrderIngestionService()
    service._delete_orders_by_ids(session, order_ids=list(range(10_000, 16_100)))
    session.commit()

    assert session.scalars(select(EsiMarketOrder)).all() == []
