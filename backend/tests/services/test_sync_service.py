from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.all_models import (
    Item,
    Location,
    MarketDemandResolved,
    MarketPricePeriod,
    OpportunityItem,
    OpportunitySourceSummary,
    Region,
    SyncJobRun,
    System,
)
from app.services.sync.service import SyncService


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


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
                risk_pct=0.25,
                warning_flag=False,
            ),
            MarketPricePeriod(
                location_id=source.id,
                type_id=item.id,
                period_days=14,
                current_price=100.0,
                period_avg_price=98.0,
                price_min=97.0,
                price_max=101.0,
                risk_pct=-0.02,
                warning_flag=False,
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
    esi_failure = datetime(2026, 3, 20, 11, 0, tzinfo=UTC)
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
                job_type="esi_history_sync",
                status="failed",
                started_at=esi_failure,
                finished_at=esi_failure,
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
    assert cards["esi_history_sync"].last_successful_sync is None
    assert cards["esi_history_sync"].recent_error_count == 1
    assert cards["esi_history_sync"].status == "degraded"


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
