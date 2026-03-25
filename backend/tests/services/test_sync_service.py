import threading
import time
from typing import cast
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.models.all_models import (
    AdamNpcDemandDaily,
    Item,
    AdamNpcDemandSyncState,
    EsiMarketOrder,
    Location,
    MarketDemandResolved,
    MarketPricePeriod,
    OpportunityItem,
    OpportunitySourceSummary,
    Region,
    EsiCharacter,
    Station,
    StructureDemandPeriod,
    StructureOrderDelta,
    StructureSnapshot,
    SyncJobRun,
    System,
    TrackedStructure,
    User,
    WorkerHeartbeat,
)
from app.repositories.seed_data import CURATED_STATIONS, ItemSeed, RegionSeed, StationSeed, SystemSeed
from app.services.characters.service import CharacterService, DiscoveredStructureInput
from app.services.adam4eve.client import AdamMarketOrdersExport
from app.services.adam4eve.ingestion import AdamNpcDemandRecord
from app.services.esi.history_ingestion import EsiRegionalHistoryRecord
from app.services.esi.client import EsiRegionalOrderRecord
from app.services.structures.snapshots import StructureOrderInput, StructureSnapshotService
from app.services.sync.service import StructureSnapshotBatch, SyncService
from tests.db_test_utils import build_test_session, create_test_engine, reset_schema


def build_session() -> Session:
    return build_test_session()


def seed_opportunity_inputs(session: Session) -> tuple[int, int, int]:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    target_system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    source_system = System(system_id=30002187, region_id=region.id, name="Amarr", security_status=0.7)
    session.add_all([target_system, source_system])
    session.flush()

    target = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=target_system.id,
        region_id=region.id,
        name="Jita IV - Moon 4",
    )
    source = Location(
        location_id=60008494,
        location_type="npc_station",
        system_id=source_system.id,
        region_id=region.id,
        name="Amarr VIII",
    )
    item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all([target, source, item])
    session.flush()

    session.add_all(
        [
            MarketPricePeriod(
                location_id=target.id,
                type_id=item.id,
                period_days=14,
                current_price=120.0,
                period_avg_price=150.0,
                price_min=100.0,
                price_max=155.0,
            ),
            MarketPricePeriod(
                location_id=source.id,
                type_id=item.id,
                period_days=14,
                current_price=100.0,
                period_avg_price=98.0,
                price_min=97.0,
                price_max=101.0,
            ),
            MarketDemandResolved(
                location_id=target.id,
                type_id=item.id,
                period_days=14,
                demand_source="adam4eve",
                confidence_score=0.9,
                demand_day=10.0,
            ),
        ]
    )
    session.commit()
    return target.id, source.id, item.id


def seed_fallback_diagnostics(session: Session) -> tuple[int, int, int]:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    system = System(system_id=30000144, region_id=region.id, name="Perimeter", security_status=0.9)
    session.add(system)
    session.flush()

    local_location = Location(
        location_id=1022734985679,
        location_type="structure",
        system_id=system.id,
        region_id=region.id,
        name="Perimeter Market Keepstar",
    )
    fallback_location = Location(
        location_id=1029876543210,
        location_type="structure",
        system_id=system.id,
        region_id=region.id,
        name="Amamake Exchange",
    )
    npc_location = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=system.id,
        region_id=region.id,
        name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    )
    item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all([local_location, fallback_location, npc_location, item])
    session.flush()

    session.add_all(
        [
            TrackedStructure(
                structure_id=local_location.location_id,
                name=local_location.name,
                system_id=system.id,
                region_id=region.id,
                tracking_tier="core",
                poll_interval_minutes=10,
                is_enabled=True,
                confidence_score=0.88,
            ),
            TrackedStructure(
                structure_id=fallback_location.location_id,
                name=fallback_location.name,
                system_id=system.id,
                region_id=region.id,
                tracking_tier="user",
                poll_interval_minutes=30,
                is_enabled=True,
                confidence_score=0.41,
            ),
        ]
    )
    session.add_all(
        [
            StructureDemandPeriod(
                structure_id=local_location.location_id,
                type_id=item.id,
                period_days=14,
                demand_min=8.0,
                demand_max=12.0,
                demand_chosen=10.0,
                coverage_pct=0.82,
                confidence_score=0.88,
            ),
            StructureDemandPeriod(
                structure_id=fallback_location.location_id,
                type_id=item.id,
                period_days=14,
                demand_min=0.0,
                demand_max=0.0,
                demand_chosen=0.0,
                coverage_pct=0.43,
                confidence_score=0.41,
            ),
            MarketDemandResolved(
                location_id=local_location.id,
                type_id=item.id,
                period_days=14,
                demand_source="local_structure",
                confidence_score=0.88,
                demand_day=10.0,
            ),
            MarketDemandResolved(
                location_id=fallback_location.id,
                type_id=item.id,
                period_days=14,
                demand_source="regional_fallback",
                confidence_score=0.41,
                demand_day=0.0,
            ),
            MarketDemandResolved(
                location_id=npc_location.id,
                type_id=item.id,
                period_days=14,
                demand_source="adam4eve",
                confidence_score=1.0,
                demand_day=15.0,
            ),
        ]
    )
    session.commit()
    return local_location.location_id, fallback_location.location_id, npc_location.location_id


class StubStructureSnapshotClient:
    def __init__(self, batches: dict[int, StructureSnapshotBatch]) -> None:
        self.batches = batches

    def fetch_structure_snapshot(self, structure_id: int) -> StructureSnapshotBatch | None:
        return self.batches.get(structure_id)


class StubAdamClient:
    def __init__(
        self,
        rows: list[AdamNpcDemandRecord],
        history_rows_by_region: dict[int, list[EsiRegionalHistoryRecord]] | None = None,
    ) -> None:
        self.rows = rows
        self.history_rows_by_region = history_rows_by_region or {}
        self.history_calls: list[tuple[int, list[int], str | None]] = []
        self.demand_calls: list[tuple[list[int], list[int], str | None]] = []

    def resolve_latest_market_orders_export(self) -> AdamMarketOrdersExport:
        return AdamMarketOrdersExport(
            path="/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv",
            export_key="2026-12",
            covered_through_date=datetime(2026, 3, 22, tzinfo=UTC).date(),
        )

    def fetch_npc_demand(
        self,
        location_ids: list[int],
        type_ids: list[int],
        *,
        export_path: str | None = None,
        synced_through_by_region: dict[int, date] | None = None,
    ) -> list[AdamNpcDemandRecord]:
        del synced_through_by_region
        self.demand_calls.append((list(location_ids), list(type_ids), export_path))
        return [
            row
            for row in self.rows
            if row["location_id"] in location_ids and row["type_id"] in type_ids
        ]

    def fetch_regional_price_history(
        self,
        region_id: int,
        type_ids: list[int],
        *,
        since_date=None,
    ) -> list[EsiRegionalHistoryRecord]:
        normalized_since = since_date.isoformat() if since_date is not None else None
        self.history_calls.append((region_id, list(type_ids), normalized_since))
        return [
            row
            for row in self.history_rows_by_region.get(region_id, [])
            if row["type_id"] in type_ids
        ]


class StubUniverseClient:
    def __init__(
        self,
        *,
        universe_regions: list[RegionSeed] | None = None,
        universe_systems: list[SystemSeed] | None = None,
        universe_items: list[ItemSeed] | None = None,
        regional_orders: dict[int, list[EsiRegionalOrderRecord]] | None = None,
        stations: dict[int, StationSeed] | None = None,
        item_details: dict[int, ItemSeed] | None = None,
    ) -> None:
        self._universe_regions = universe_regions or []
        self._universe_systems = universe_systems or []
        self._universe_items = universe_items or []
        self._regional_orders = regional_orders or {}
        self._stations = stations or {}
        self._item_details = item_details or {item.type_id: item for item in self._universe_items}
        self.regional_order_calls: list[int] = []
        self.item_detail_calls: list[int] = []

    def fetch_universe_item(self, type_id: int) -> ItemSeed:
        self.item_detail_calls.append(type_id)
        return self._item_details[type_id]

    def fetch_station(self, station_id: int) -> StationSeed:
        return self._stations[station_id]

    def fetch_regional_orders(self, region_id: int) -> list[EsiRegionalOrderRecord]:
        self.regional_order_calls.append(region_id)
        return list(self._regional_orders.get(region_id, []))


class StubFoundationClient:
    def __init__(
        self,
        *,
        regions: list[RegionSeed],
        systems: list[SystemSeed],
        items: list[ItemSeed],
    ) -> None:
        from app.repositories.seed_data import StaticFoundationSeedSource

        self.seed_source = StaticFoundationSeedSource(
            regions_data=tuple(regions),
            systems_data=tuple(systems),
            items_data=tuple(items),
            stations_data=(),
            structure_locations_data={},
            tracked_structures_data=(),
            default_user_settings_data={},
        )

    def build_seed_source(self):
        return self.seed_source


class SlowFoundationSeedSource:
    def regions(self) -> list[RegionSeed]:
        return [RegionSeed(region_id=10000002, name="The Forge")]

    def systems(self) -> list[SystemSeed]:
        return [SystemSeed(system_id=30000142, region_id=10000002, name="Jita", security_status=0.9)]

    def stations(self) -> list[StationSeed]:
        return []

    def items(self):
        for offset in range(5_000):
            time.sleep(0.005)
            yield ItemSeed(
                type_id=90000000 + offset,
                name=f"Bulk Item {offset}",
                volume_m3=1.0,
                group_name="Test",
                category_name="Test",
            )

    def structure_locations(self) -> dict[int, object]:
        return {}

    def tracked_structures(self) -> list[object]:
        return []

    def default_user_settings(self) -> dict[str, object]:
        return {}


class SlowFoundationClient:
    def build_seed_source(self):
        return SlowFoundationSeedSource()


def seed_structure_snapshot_sync_inputs(session: Session) -> tuple[int, int]:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    system = System(system_id=30000144, region_id=region.id, name="Perimeter", security_status=0.9)
    session.add(system)
    session.flush()

    structure = Location(
        location_id=1022734985679,
        location_type="structure",
        system_id=system.id,
        region_id=region.id,
        name="Perimeter Market Keepstar",
    )
    item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all([structure, item])
    session.flush()

    session.add(
        TrackedStructure(
            structure_id=structure.location_id,
            name=structure.name,
            system_id=system.id,
            region_id=region.id,
            tracking_tier="core",
            poll_interval_minutes=10,
            is_enabled=True,
            confidence_score=0.88,
        )
    )
    session.commit()

    StructureSnapshotService().persist_snapshot(
        session,
        structure_id=structure.location_id,
        snapshot_time=datetime(2026, 3, 19, 10, 0, tzinfo=UTC),
        orders=[
            StructureOrderInput(order_id=1, type_id=item.id, is_buy_order=False, price=100.0, volume_remain=50),
            StructureOrderInput(order_id=2, type_id=item.id, is_buy_order=True, price=90.0, volume_remain=40),
        ],
    )
    return structure.location_id, item.id


def seed_raw_trade_inputs(session: Session) -> tuple[int, int, int, int]:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    target_system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    source_system = System(system_id=30002187, region_id=region.id, name="Amarr", security_status=0.7)
    session.add_all([target_system, source_system])
    session.flush()

    target = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=target_system.id,
        region_id=region.id,
        name="Jita IV - Moon 4",
    )
    source = Location(
        location_id=60008494,
        location_type="npc_station",
        system_id=source_system.id,
        region_id=region.id,
        name="Amarr VIII",
    )
    item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all([target, source, item])
    session.flush()
    session.add(
        EsiMarketOrder(
            order_id=9_001,
            region_id=region.id,
            location_id=target.id,
            type_id=item.id,
            system_id=target_system.id,
            is_buy_order=False,
            price=120.0,
            volume_total=1_000,
            volume_remain=400,
            min_volume=1,
            order_range="region",
            issued=datetime.now(UTC),
            duration=90,
        )
    )
    session.commit()
    return region.region_id, target.location_id, source.location_id, item.type_id


def seed_character_for_structure_tracking(session: Session) -> int:
    user = User(primary_character_id=None)
    session.add(user)
    session.flush()

    character = EsiCharacter(
        user_id=user.id,
        character_id=90000042,
        character_name="Audit Trader",
        corporation_name="Signal Cartel",
        granted_scopes="esi-assets.read_assets.v1",
        sync_enabled=True,
    )
    session.add(character)
    session.flush()
    user.primary_character_id = character.id
    session.commit()
    return character.character_id


def test_trigger_job_persists_foundation_seed_run_and_list_jobs_returns_newest_first() -> None:
    session = build_session()
    service = SyncService(session_factory=lambda: session)

    first = service.trigger_job("foundation_seed_sync")
    second = service.trigger_job("foundation_seed_sync")
    jobs = service.list_jobs()

    assert first.status == "success"
    assert first.finished_at is not None
    assert first.duration_ms is not None
    assert first.records_processed >= 0
    assert first.message is not None
    assert "Seeded foundation data" in first.message

    assert second.id != first.id
    assert [job.id for job in jobs] == [second.id, first.id]
    assert all(job.status == "success" for job in jobs)


def test_trigger_job_foundation_import_sync_persists_universe_rows() -> None:
    session = build_session()
    service = SyncService(
        session_factory=lambda: session,
        foundation_client=StubFoundationClient(
            regions=[RegionSeed(region_id=10000002, name="The Forge")],
            systems=[
                SystemSeed(system_id=30000142, region_id=10000002, name="Jita", security_status=0.9)
            ],
            items=[
                ItemSeed(
                    type_id=34,
                    name="Tritanium",
                    volume_m3=0.01,
                    group_name="18",
                    category_name=None,
                )
            ],
        ),
    )

    result = service.trigger_job("foundation_import_sync")

    assert result.status == "success"
    assert result.target_type == "universe"
    assert result.target_id == "all"
    assert "Imported universe foundation data" in (result.message or "")
    assert session.scalar(select(Region).where(Region.region_id == 10000002)) is not None
    assert session.scalar(select(System).where(System.system_id == 30000142)) is not None
    assert session.scalar(select(Item).where(Item.type_id == 34)) is not None


def test_cancel_job_marks_long_running_job_as_cancelled() -> None:
    engine = create_test_engine()
    reset_schema(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    result_holder: dict[str, object] = {}

    def run_job() -> None:
        service = SyncService(
            session_factory=session_factory,
            foundation_client=SlowFoundationClient(),
        )
        result_holder["result"] = service.trigger_job("foundation_import_sync")

    worker = threading.Thread(target=run_job)
    worker.start()

    controller = SyncService(
        session_factory=session_factory,
        foundation_client=SlowFoundationClient(),
    )

    job_id: int | None = None
    for _ in range(100):
        jobs = controller.list_jobs()
        if jobs:
            job_id = jobs[0].id
            if jobs[0].status == "running":
                break
        time.sleep(0.01)

    assert job_id is not None
    cancelled = controller.cancel_job(job_id)
    worker.join(timeout=5)

    assert cancelled.status == "cancelling"
    assert worker.is_alive() is False
    final_result = result_holder["result"]
    assert getattr(final_result, "status") == "cancelled"


def test_check_for_cancellation_propagates_database_probe_errors() -> None:
    session = build_session()
    service = SyncService(session_factory=lambda: session)

    class BrokenProbeSession:
        def get(self, model, job_id):
            del model, job_id
            raise OperationalError("SELECT 1", {}, Exception("synthetic database failure"))

        def close(self) -> None:
            return None

    service.session_factory = cast(object, lambda: BrokenProbeSession())  # type: ignore[assignment]

    with pytest.raises(OperationalError):
        service._check_for_cancellation(session, job_id=123)


def test_trigger_job_opportunity_rebuild_persists_rows_and_sync_job() -> None:
    session = build_session()
    target_id, source_id, item_id = seed_opportunity_inputs(session)
    service = SyncService(session_factory=lambda: session)

    result = service.trigger_job("opportunity_rebuild")

    generated_item = session.scalar(
        select(OpportunityItem).where(
            OpportunityItem.target_location_id == target_id,
            OpportunityItem.source_location_id == source_id,
            OpportunityItem.type_id == item_id,
            OpportunityItem.period_days == 14,
        )
    )
    generated_summary = session.scalar(
        select(OpportunitySourceSummary).where(
            OpportunitySourceSummary.target_location_id == target_id,
            OpportunitySourceSummary.source_location_id == source_id,
            OpportunitySourceSummary.period_days == 14,
        )
    )
    job_row = session.scalar(select(SyncJobRun).order_by(SyncJobRun.id.desc()))

    assert generated_item is not None
    assert generated_summary is not None
    assert result.status == "success"
    assert result.records_processed == 1
    assert result.message is not None
    assert "Rebuilt opportunities" in result.message
    assert job_row is not None
    assert job_row.job_type == "opportunity_rebuild"
    assert job_row.records_processed == 1
    assert job_row.status == "success"


def test_get_status_uses_persisted_sync_job_history() -> None:
    session = build_session()
    service = SyncService(session_factory=lambda: session)
    adam_success = datetime(2026, 3, 20, 10, 0, tzinfo=UTC)
    orders_failure = datetime(2026, 3, 20, 11, 0, tzinfo=UTC)
    session.add_all(
        [
            SyncJobRun(
                job_type="adam4eve_sync",
                status="success",
                started_at=adam_success,
                finished_at=adam_success,
                records_processed=3,
            ),
            SyncJobRun(
                job_type="esi_market_orders_sync",
                status="failed",
                started_at=orders_failure,
                finished_at=orders_failure,
                records_processed=0,
                error_details="boom",
            ),
        ]
    )
    session.commit()

    cards = {card.key: card for card in service.get_status()}

    assert cards["adam4eve_sync"].last_successful_sync == adam_success
    assert cards["adam4eve_sync"].recent_error_count == 0
    assert cards["adam4eve_sync"].status == "healthy"
    assert cards["esi_market_orders_sync"].last_successful_sync is None
    assert cards["esi_market_orders_sync"].recent_error_count == 1
    assert cards["esi_market_orders_sync"].status == "degraded"


def test_get_status_exposes_active_job_progress() -> None:
    session = build_session()
    service = SyncService(session_factory=lambda: session)
    started_at = datetime(2026, 3, 23, 14, 0, tzinfo=UTC)
    session.add(
        SyncJobRun(
            job_type="esi_market_orders_sync",
            status="running",
            started_at=started_at,
            finished_at=None,
            records_processed=60,
            progress_phase="Processing downloaded ESI market orders",
            progress_current=60,
            progress_total=100,
            progress_unit="downloaded records",
            message="Processed 60 / 100 downloaded ESI market orders.",
        )
    )
    session.commit()

    cards = {card.key: card for card in service.get_status()}

    assert cards["esi_market_orders_sync"].status == "running"
    assert cards["esi_market_orders_sync"].progress_phase == "Processing downloaded ESI market orders"
    assert cards["esi_market_orders_sync"].progress_current == 60
    assert cards["esi_market_orders_sync"].progress_total == 100
    assert cards["esi_market_orders_sync"].progress_unit == "downloaded records"
    assert cards["esi_market_orders_sync"].active_message == "Processed 60 / 100 downloaded ESI market orders."


def test_list_jobs_finalizes_stale_cancelling_jobs() -> None:
    session = build_session()
    service = SyncService(session_factory=lambda: session)
    started_at = datetime.now(UTC) - timedelta(minutes=10)
    session.add(
        SyncJobRun(
            job_type="esi_market_orders_sync",
            status="cancelling",
            started_at=started_at,
            finished_at=None,
            records_processed=0,
            message="Cancelling esi_market_orders_sync.",
        )
    )
    session.commit()

    jobs = service.list_jobs()
    refreshed_job = session.scalar(select(SyncJobRun).order_by(SyncJobRun.id.desc()))

    assert jobs[0].status == "cancelled"
    assert jobs[0].finished_at is not None
    assert jobs[0].message is not None
    assert "stale cancellation" in jobs[0].message.lower()
    assert refreshed_job is not None
    assert refreshed_job.status == "cancelled"


def test_finalize_stale_cancelling_jobs_propagates_database_errors() -> None:
    session = build_session()
    service = SyncService(session_factory=lambda: session)

    class BrokenCleanupSession:
        def scalars(self, *args, **kwargs):
            del args, kwargs
            raise OperationalError("SELECT 1", {}, Exception("synthetic database failure"))

    with pytest.raises(OperationalError):
        service._finalize_stale_cancelling_jobs(cast(Session, BrokenCleanupSession()))


def test_get_status_returns_stable_defaults_when_no_history_exists() -> None:
    session = build_session()
    service = SyncService(session_factory=lambda: session)

    cards = {card.key: card for card in service.get_status()}

    assert cards["adam4eve_sync"].last_successful_sync is None
    assert cards["adam4eve_sync"].recent_error_count == 0
    assert cards["adam4eve_sync"].status == "idle"
    assert cards["opportunity_rebuild"].last_successful_sync is None
    assert cards["opportunity_rebuild"].recent_error_count == 0
    assert cards["opportunity_rebuild"].status == "idle"


def test_get_status_propagates_database_errors() -> None:
    service = SyncService(session_factory=lambda: build_session())

    class BrokenStatusSession:
        def scalars(self, *args, **kwargs):
            del args, kwargs
            raise OperationalError("SELECT 1", {}, Exception("synthetic database failure"))

        def scalar(self, *args, **kwargs):
            del args, kwargs
            raise OperationalError("SELECT 1", {}, Exception("synthetic database failure"))

        def close(self) -> None:
            return None

    service.session_factory = cast(object, lambda: BrokenStatusSession())  # type: ignore[assignment]

    with pytest.raises(OperationalError):
        service.get_status()


def test_get_status_uses_persisted_worker_heartbeat_when_fresh() -> None:
    session = build_session()
    service = SyncService(session_factory=lambda: session)
    heartbeat_at = datetime.now(UTC)
    session.add(
        WorkerHeartbeat(
            source="worker",
            recorded_at=heartbeat_at,
            status="healthy",
        )
    )
    session.commit()

    cards = {card.key: card for card in service.get_status()}

    assert cards["worker"].status == "healthy"
    assert cards["worker"].last_successful_sync == heartbeat_at
    assert cards["worker"].recent_error_count == 0


def test_get_status_marks_worker_heartbeat_as_degraded_when_stale() -> None:
    session = build_session()
    service = SyncService(session_factory=lambda: session)
    heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
    session.add(
        WorkerHeartbeat(
            source="worker",
            recorded_at=heartbeat_at,
            status="healthy",
        )
    )
    session.commit()

    cards = {card.key: card for card in service.get_status()}

    assert cards["worker"].status == "degraded"
    assert cards["worker"].last_successful_sync == heartbeat_at
    assert cards["worker"].recent_error_count == 0


def test_get_status_returns_idle_worker_card_when_no_heartbeat_exists() -> None:
    session = build_session()
    service = SyncService(session_factory=lambda: session)

    cards = {card.key: card for card in service.get_status()}

    assert cards["worker"].status == "idle"
    assert cards["worker"].last_successful_sync is None
    assert cards["worker"].recent_error_count == 0


def test_list_jobs_propagates_database_errors() -> None:
    service = SyncService(session_factory=lambda: build_session())

    class BrokenJobsSession:
        def scalars(self, *args, **kwargs):
            del args, kwargs
            raise OperationalError("SELECT 1", {}, Exception("synthetic database failure"))

        def close(self) -> None:
            return None

    service.session_factory = cast(object, lambda: BrokenJobsSession())  # type: ignore[assignment]

    with pytest.raises(OperationalError):
        service.list_jobs()


def test_get_fallback_status_uses_persisted_structure_demand_rows() -> None:
    session = build_session()
    seed_fallback_diagnostics(session)
    service = SyncService(session_factory=lambda: session)

    diagnostics = service.get_fallback_status()

    assert [row.structure_id for row in diagnostics] == [1022734985679, 1029876543210]
    assert diagnostics[0].structure_name == "Perimeter Market Keepstar"
    assert diagnostics[0].demand_source == "local_structure"
    assert diagnostics[0].confidence_score == 0.88
    assert diagnostics[0].coverage_pct == 0.82
    assert diagnostics[1].structure_name == "Amamake Exchange"
    assert diagnostics[1].demand_source == "regional_fallback"
    assert diagnostics[1].confidence_score == 0.41
    assert diagnostics[1].coverage_pct == 0.43


def test_get_fallback_status_excludes_npc_locations_and_is_stable_when_no_rows_exist() -> None:
    session = build_session()
    seed_fallback_diagnostics(session)
    service = SyncService(session_factory=lambda: session)

    first = service.get_fallback_status()
    second = service.get_fallback_status()

    assert all(row.structure_id != 60003760 for row in first)
    assert first == second


def test_get_fallback_status_returns_empty_list_when_no_structure_demand_rows_exist() -> None:
    session = build_session()
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()
    system = System(system_id=30000144, region_id=region.id, name="Perimeter", security_status=0.9)
    session.add(system)
    session.flush()
    session.add(
        TrackedStructure(
            structure_id=1022734985679,
            name="Perimeter Market Keepstar",
            system_id=system.id,
            region_id=region.id,
            tracking_tier="core",
            poll_interval_minutes=10,
            is_enabled=True,
        )
    )
    session.commit()

    service = SyncService(session_factory=lambda: session)

    assert service.get_fallback_status() == []


def test_get_fallback_status_propagates_database_errors() -> None:
    service = SyncService(session_factory=lambda: build_session())

    class BrokenFallbackSession:
        def scalars(self, *args, **kwargs):
            del args, kwargs
            raise OperationalError("SELECT 1", {}, Exception("synthetic database failure"))

        def close(self) -> None:
            return None

    service.session_factory = cast(object, lambda: BrokenFallbackSession())  # type: ignore[assignment]

    with pytest.raises(OperationalError):
        service.get_fallback_status()


def test_trigger_job_structure_snapshot_sync_persists_snapshot_delta_and_demand_rows() -> None:
    session = build_session()
    structure_id, item_id = seed_structure_snapshot_sync_inputs(session)
    service = SyncService(
        session_factory=lambda: session,
        structure_snapshot_client=StubStructureSnapshotClient(
            {
                structure_id: StructureSnapshotBatch(
                    structure_id=structure_id,
                    snapshot_time=datetime(2026, 3, 20, 10, 0, tzinfo=UTC),
                    orders=[
                        StructureOrderInput(
                            order_id=1,
                            type_id=item_id,
                            is_buy_order=False,
                            price=100.0,
                            volume_remain=20,
                        ),
                        StructureOrderInput(
                            order_id=2,
                            type_id=item_id,
                            is_buy_order=True,
                            price=90.0,
                            volume_remain=15,
                        ),
                    ],
                )
            }
        ),
    )

    result = service.trigger_job("structure_snapshot_sync")

    snapshots = session.scalars(
        select(StructureSnapshot).where(StructureSnapshot.structure_id == structure_id)
    ).all()
    deltas = session.scalars(
        select(StructureOrderDelta).where(StructureOrderDelta.structure_id == structure_id)
    ).all()
    demand_period = session.scalar(
        select(StructureDemandPeriod).where(
            StructureDemandPeriod.structure_id == structure_id,
            StructureDemandPeriod.type_id == item_id,
            StructureDemandPeriod.period_days == 14,
        )
    )

    assert result.status == "success"
    assert result.records_processed == 5
    assert result.target_type == "structures"
    assert result.target_id == "1"
    assert "Synced structure snapshots" in (result.message or "")
    assert len(snapshots) == 2
    assert len(deltas) == 2
    assert demand_period is not None
    assert demand_period.demand_min == pytest.approx(55 / 14)
    assert demand_period.demand_max == pytest.approx(55 / 14)
    assert demand_period.demand_chosen == pytest.approx(55 / 14)

    rerun = service.trigger_job("structure_snapshot_sync")
    rerun_snapshots = session.scalars(
        select(StructureSnapshot).where(StructureSnapshot.structure_id == structure_id)
    ).all()
    rerun_deltas = session.scalars(
        select(StructureOrderDelta).where(StructureOrderDelta.structure_id == structure_id)
    ).all()
    rerun_demand_period = session.scalar(
        select(StructureDemandPeriod).where(
            StructureDemandPeriod.structure_id == structure_id,
            StructureDemandPeriod.type_id == item_id,
            StructureDemandPeriod.period_days == 14,
        )
    )

    assert rerun.records_processed == 0
    assert rerun.status == "success"
    assert len(rerun_snapshots) == 2
    assert len(rerun_deltas) == 2
    assert rerun_demand_period is not None
    assert rerun_demand_period.demand_chosen == pytest.approx(55 / 14)


def test_trigger_job_structure_snapshot_sync_uses_character_tracked_structure_rows() -> None:
    session = build_session()
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    session.add(system)
    session.flush()

    item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add(item)
    session.flush()

    character_id = seed_character_for_structure_tracking(session)
    CharacterService(session_factory=lambda: session).discover_character_accessible_structures(
        character_id,
        [
            DiscoveredStructureInput(
                structure_id=1022734985680,
                structure_name="Jita Freeport",
                system_name="Jita",
                region_name="The Forge",
                tracking_enabled=True,
                polling_tier="user",
                confidence_score=0.42,
            )
        ],
    )

    StructureSnapshotService().persist_snapshot(
        session,
        structure_id=1022734985680,
        snapshot_time=datetime(2026, 3, 19, 10, 0, tzinfo=UTC),
        orders=[
            StructureOrderInput(order_id=1, type_id=item.id, is_buy_order=False, price=100.0, volume_remain=50),
        ],
    )

    service = SyncService(
        session_factory=lambda: session,
        structure_snapshot_client=StubStructureSnapshotClient(
            {
                1022734985680: StructureSnapshotBatch(
                    structure_id=1022734985680,
                    snapshot_time=datetime(2026, 3, 20, 10, 0, tzinfo=UTC),
                    orders=[
                        StructureOrderInput(
                            order_id=1,
                            type_id=item.id,
                            is_buy_order=False,
                            price=100.0,
                            volume_remain=20,
                        )
                    ],
                )
            }
        ),
    )

    result = service.trigger_job("structure_snapshot_sync")

    assert result.status == "success"
    assert result.target_type == "structures"
    assert result.target_id == "1"
    assert result.records_processed == 4


def test_trigger_job_character_sync_processes_all_enabled_characters() -> None:
    session = build_session()
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    session.add_all(
        [
            System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9),
            System(system_id=30000144, region_id=region.id, name="Perimeter", security_status=0.9),
        ]
    )
    session.flush()

    user = User(primary_character_id=None)
    session.add(user)
    session.flush()
    session.add_all(
        [
            EsiCharacter(
                user_id=user.id,
                character_id=90000042,
                character_name="Audit Trader",
                corporation_name="Signal Cartel",
                granted_scopes="esi-assets.read_assets.v1",
                sync_enabled=True,
            ),
            EsiCharacter(
                user_id=user.id,
                character_id=90000077,
                character_name="Alt Hauler",
                corporation_name="PushX",
                granted_scopes="esi-assets.read_assets.v1",
                sync_enabled=True,
            ),
        ]
    )
    session.commit()

    service = SyncService(session_factory=lambda: session)

    result = service.trigger_job("character_sync")

    assert result.status == "success"
    assert result.target_type == "characters"
    assert result.target_id == "2"
    assert result.records_processed == 6
    assert "Synced characters" in (result.message or "")


def test_raw_sync_jobs_refresh_derived_trade_rows_and_rebuild_opportunities() -> None:
    session = build_session()
    region_id, target_location_id, source_location_id, type_id = seed_raw_trade_inputs(session)
    service = SyncService(
        session_factory=lambda: session,
        adam_client=StubAdamClient(
            [
                {
                    "location_id": target_location_id,
                    "type_id": type_id,
                    "demand_day": 12.0,
                    "date": "2026-03-20",
                    "source": "adam4eve",
                }
            ],
            history_rows_by_region={
                region_id: [
                    {
                        "type_id": type_id,
                        "date": "2026-03-20",
                        "average": 120.0,
                        "highest": 130.0,
                        "lowest": 110.0,
                        "order_count": 0,
                        "volume": 0,
                    },
                    {
                        "type_id": type_id,
                        "date": "2026-03-19",
                        "average": 118.0,
                        "highest": 128.0,
                        "lowest": 108.0,
                        "order_count": 0,
                        "volume": 0,
                    },
                ]
            }
        ),
    )

    adam_result = service.trigger_job("adam4eve_sync")

    demand_rows = session.scalars(select(MarketDemandResolved)).all()
    price_rows = session.scalars(select(MarketPricePeriod)).all()
    opportunity_item = session.scalar(
        select(OpportunityItem).where(
            OpportunityItem.period_days == 14,
        )
    )
    opportunity_summary = session.scalar(
        select(OpportunitySourceSummary).where(
            OpportunitySourceSummary.period_days == 14,
        )
    )

    assert adam_result.status == "success"
    assert any(row.location_id > 0 and row.type_id > 0 for row in demand_rows)
    assert any(row.location_id > 0 and row.type_id > 0 for row in price_rows)
    assert opportunity_item is not None
    assert opportunity_summary is not None


def test_adam4eve_sync_skips_demand_download_when_latest_export_is_already_synced() -> None:
    session = build_session()
    region_id, target_location_id, source_location_id, type_id = seed_raw_trade_inputs(session)
    session.add(
        AdamNpcDemandSyncState(
            region_id=1,
            export_key="2026-12",
            synced_through_date=datetime(2026, 3, 22, tzinfo=UTC).date(),
            last_checked_at=datetime.now(UTC),
        )
    )
    session.commit()

    adam_client = StubAdamClient(
        [
            {
                "location_id": target_location_id,
                "type_id": type_id,
                "demand_day": 12.0,
                "date": "2026-03-20",
                "source": "adam4eve",
            }
        ],
        history_rows_by_region={
            region_id: [
                {
                    "type_id": type_id,
                    "date": "2026-03-20",
                    "average": 120.0,
                    "highest": 130.0,
                    "lowest": 110.0,
                    "order_count": 0,
                    "volume": 0,
                }
            ]
        },
    )
    service = SyncService(
        session_factory=lambda: session,
        adam_client=adam_client,
    )

    result = service.trigger_job("adam4eve_sync")
    demand_rows = session.scalars(select(AdamNpcDemandDaily)).all()

    assert result.status == "success"
    assert adam_client.demand_calls == []
    assert demand_rows == []


def test_adam4eve_sync_passes_external_region_ids_for_demand_watermarks() -> None:
    session = build_session()
    region_id, target_location_id, _source_location_id, type_id = seed_raw_trade_inputs(session)
    session.add(
        AdamNpcDemandDaily(
            location_id=1,
            type_id=1,
            date=datetime(2026, 3, 20, tzinfo=UTC).date(),
            demand_day=5.0,
            source_label="adam4eve",
            raw_payload={},
        )
    )
    session.commit()

    captured_watermarks: dict[int, date] = {}

    class CapturingAdamClient(StubAdamClient):
        def fetch_npc_demand(
            self,
            location_ids: list[int],
            type_ids: list[int],
            *,
            export_path: str | None = None,
            synced_through_by_region: dict[int, date] | None = None,
        ) -> list[AdamNpcDemandRecord]:
            del location_ids, type_ids, export_path
            captured_watermarks.update(synced_through_by_region or {})
            return []

    service = SyncService(
        session_factory=lambda: session,
        adam_client=CapturingAdamClient(
            [
                {
                    "location_id": target_location_id,
                    "type_id": type_id,
                    "demand_day": 12.0,
                    "date": "2026-03-24",
                    "source": "adam4eve",
                }
            ],
            history_rows_by_region={region_id: []},
        ),
    )

    result = service.trigger_job("adam4eve_sync")

    assert result.status == "success"
    assert captured_watermarks == {10000002: date(2026, 3, 20)}


def test_trigger_job_esi_market_orders_sync_persists_orders_without_fetching_missing_items() -> None:
    session = build_session()
    curated_station = CURATED_STATIONS[0]

    session.add(Region(region_id=curated_station.region_id, name="The Forge"))
    session.flush()
    session.add(
        System(system_id=curated_station.system_id, region_id=1, name="Jita", security_status=0.9)
    )
    session.flush()
    session.add(
        Location(
            location_id=curated_station.station_id,
            location_type="npc_station",
            system_id=1,
            region_id=1,
            name=curated_station.name,
        )
    )
    session.add(Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material"))
    session.commit()

    universe_client = StubUniverseClient(
        regional_orders={
            curated_station.region_id: [
                {
                    "order_id": 9001,
                    "type_id": 34,
                    "location_id": curated_station.station_id,
                    "system_id": curated_station.system_id,
                    "is_buy_order": False,
                    "price": 4.12,
                    "volume_total": 1000,
                    "volume_remain": 400,
                    "min_volume": 1,
                    "range": "region",
                    "issued": "2026-03-23T09:00:00+00:00",
                    "duration": 90,
                }
            ]
        },
        stations={
            curated_station.station_id: StationSeed(
                station_id=curated_station.station_id,
                system_id=curated_station.system_id,
                region_id=curated_station.region_id,
                name=curated_station.name,
            )
        },
    )
    service = SyncService(session_factory=lambda: session, esi_client=universe_client)

    result = service.trigger_job("esi_market_orders_sync")

    order_row = session.scalar(select(EsiMarketOrder).where(EsiMarketOrder.order_id == 9001))
    station_row = session.scalar(select(Station).where(Station.station_id == curated_station.station_id))
    location_row = session.scalar(select(Location).where(Location.location_id == curated_station.station_id))
    item_row = session.scalar(select(Item).where(Item.type_id == 34))

    assert result.status == "success"
    assert result.records_processed == 1
    assert result.target_type == "regions"
    assert result.target_id == "1"
    assert "Synced ESI market orders" in (result.message or "")
    assert universe_client.item_detail_calls == []
    assert order_row is not None
    assert location_row is not None
    assert item_row is not None
    assert station_row is None


def test_esi_market_orders_sync_skips_orders_for_missing_foundation_items() -> None:
    session = build_session()
    curated_station = CURATED_STATIONS[0]

    session.add(Region(region_id=curated_station.region_id, name="The Forge"))
    session.flush()
    session.add(System(system_id=curated_station.system_id, region_id=1, name="Jita", security_status=0.9))
    session.flush()
    session.add(
        Location(
            location_id=curated_station.station_id,
            location_type="npc_station",
            system_id=1,
            region_id=1,
            name=curated_station.name,
        )
    )
    session.commit()

    universe_client = StubUniverseClient(
        regional_orders={
            curated_station.region_id: [
                {
                    "order_id": 9001,
                    "type_id": 28503,
                    "location_id": curated_station.station_id,
                    "system_id": curated_station.system_id,
                    "is_buy_order": False,
                    "price": 1_000_000.0,
                    "volume_total": 1,
                    "volume_remain": 1,
                    "min_volume": 1,
                    "range": "region",
                    "issued": "2026-03-23T09:00:00+00:00",
                    "duration": 90,
                }
            ]
        },
        stations={
            curated_station.station_id: StationSeed(
                station_id=curated_station.station_id,
                system_id=curated_station.system_id,
                region_id=curated_station.region_id,
                name=curated_station.name,
            )
        },
    )
    service = SyncService(session_factory=lambda: session, esi_client=universe_client)

    result = service.trigger_job("esi_market_orders_sync")

    assert result.status == "success"
    assert result.records_processed == 1
    assert "1 skipped because item foundation data was missing" in (result.message or "")
    assert universe_client.item_detail_calls == []
    assert session.scalar(select(EsiMarketOrder).where(EsiMarketOrder.order_id == 9001)) is None


def test_esi_market_orders_sync_skips_structure_location_ids() -> None:
    session = build_session()
    curated_station = CURATED_STATIONS[0]

    session.add(Region(region_id=curated_station.region_id, name="The Forge"))
    session.flush()
    session.add(System(system_id=curated_station.system_id, region_id=1, name="Jita", security_status=0.9))
    session.flush()
    session.add(Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material"))
    session.commit()

    universe_client = StubUniverseClient(
        regional_orders={
            curated_station.region_id: [
                {
                    "order_id": 9001,
                    "type_id": 34,
                    "location_id": 1033368129183,
                    "system_id": curated_station.system_id,
                    "is_buy_order": False,
                    "price": 4.12,
                    "volume_total": 1000,
                    "volume_remain": 400,
                    "min_volume": 1,
                    "range": "region",
                    "issued": "2026-03-23T09:00:00+00:00",
                    "duration": 90,
                }
            ]
        },
        stations={},
    )
    service = SyncService(session_factory=lambda: session, esi_client=universe_client)

    result = service.trigger_job("esi_market_orders_sync")

    assert result.status == "success"
    assert result.records_processed == 1
    assert "1 skipped because the location was not an NPC station" in (result.message or "")
    assert session.scalar(select(EsiMarketOrder).where(EsiMarketOrder.order_id == 9001)) is None


def test_esi_market_orders_sync_scopes_to_all_imported_regions() -> None:
    session = build_session()
    curated_station = CURATED_STATIONS[0]

    target_region = Region(region_id=curated_station.region_id, name="Curated Region")
    other_region = Region(region_id=10000099, name="Other Region")
    session.add_all([target_region, other_region])
    session.flush()

    target_system = System(
        system_id=curated_station.system_id,
        region_id=target_region.id,
        name="Curated System",
        security_status=0.9,
    )
    other_system = System(system_id=30009999, region_id=other_region.id, name="Other System", security_status=0.5)
    session.add_all([target_system, other_system])
    session.flush()

    target_location = Location(
        location_id=curated_station.station_id,
        location_type="npc_station",
        system_id=target_system.id,
        region_id=target_region.id,
        name=curated_station.name,
    )
    other_location = Location(
        location_id=60009999,
        location_type="npc_station",
        system_id=other_system.id,
        region_id=other_region.id,
        name="Other Station",
    )
    session.add_all([target_location, other_location])
    session.add_all(
        [
            Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material"),
            Item(type_id=35, name="Pyerite", volume_m3=0.01, group_name="Mineral", category_name="Material"),
        ]
    )
    session.commit()

    universe_client = StubUniverseClient(
        regional_orders={
            curated_station.region_id: [
                {
                    "order_id": 9001,
                    "type_id": 34,
                    "location_id": curated_station.station_id,
                    "system_id": curated_station.system_id,
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
            10000099: [
                {
                    "order_id": 9002,
                    "type_id": 35,
                    "location_id": 60009999,
                    "system_id": 30009999,
                    "is_buy_order": False,
                    "price": 8.15,
                    "volume_total": 500,
                    "volume_remain": 200,
                    "min_volume": 1,
                    "range": "region",
                    "issued": "2026-03-23T10:00:00+00:00",
                    "duration": 90,
                }
            ],
        },
        stations={
            curated_station.station_id: StationSeed(
                station_id=curated_station.station_id,
                system_id=curated_station.system_id,
                region_id=curated_station.region_id,
                name=curated_station.name,
            ),
            60009999: StationSeed(station_id=60009999, system_id=30009999, region_id=10000099, name="Other Station"),
        },
    )
    service = SyncService(session_factory=lambda: session, esi_client=universe_client)

    result = service.trigger_job("esi_market_orders_sync")
    orders = session.scalars(select(EsiMarketOrder).order_by(EsiMarketOrder.order_id.asc())).all()

    assert result.status == "success"
    assert result.target_type == "regions"
    assert result.target_id == "2"
    assert universe_client.regional_order_calls == [curated_station.region_id, 10000099]
    assert [row.order_id for row in orders] == [9001, 9002]


def test_trigger_job_esi_market_orders_sync_deletes_stale_orders_on_rerun() -> None:
    session = build_session()
    curated_station = CURATED_STATIONS[0]

    region = Region(region_id=curated_station.region_id, name="Curated Region")
    session.add(region)
    session.flush()

    system = System(
        system_id=curated_station.system_id,
        region_id=region.id,
        name="Curated System",
        security_status=0.9,
    )
    session.add(system)
    session.flush()

    location = Location(
        location_id=curated_station.station_id,
        location_type="npc_station",
        system_id=system.id,
        region_id=region.id,
        name=curated_station.name,
    )
    item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all([location, item])
    session.flush()
    session.add(
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
            issued=datetime.now(UTC),
            duration=90,
        )
    )
    session.commit()

    rerun_service = SyncService(
        session_factory=lambda: session,
        esi_client=StubUniverseClient(
            regional_orders={curated_station.region_id: []},
            stations={
                curated_station.station_id: StationSeed(
                    station_id=curated_station.station_id,
                    system_id=curated_station.system_id,
                    region_id=curated_station.region_id,
                    name=curated_station.name,
                )
            },
            item_details={
                34: ItemSeed(
                    type_id=34,
                    name="Tritanium",
                    volume_m3=0.01,
                    group_name="18",
                    category_name=None,
                )
            },
        ),
    )

    rerun_result = rerun_service.trigger_job("esi_market_orders_sync")
    remaining_orders = session.scalars(select(EsiMarketOrder)).all()

    assert rerun_result.status == "success"
    assert rerun_result.records_processed == 0
    assert remaining_orders == []
