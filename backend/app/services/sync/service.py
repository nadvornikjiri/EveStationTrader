from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.api.schemas.sync import FallbackDiagnostic, SyncJobRunResponse, SyncStatusCard
from app.services.adam4eve.client import Adam4EveClient
from app.services.adam4eve.ingestion import AdamNpcDemandIngestionService, AdamNpcDemandRecord
from app.models.all_models import (
    Item,
    Location,
    MarketDemandResolved,
    MarketPricePeriod,
    Region,
    StructureOrderDelta,
    StructureSnapshot,
    StructureDemandPeriod,
    SyncJobRun,
    TrackedStructure,
    WorkerHeartbeat,
)
from app.services.esi.client import EsiClient
from app.services.esi.history_ingestion import (
    EsiRegionalHistoryIngestionService,
    EsiRegionalHistoryRecord,
)
from app.services.opportunities.generation import OpportunityGenerationService
from app.services.structures.demand_periods import StructureDemandPeriodService
from app.services.structures.snapshots import StructureOrderInput, StructureSnapshotService
from app.services.sync.foundation_data import FoundationDataService


class HistoryCapableEsiClient(Protocol):
    def fetch_regional_history(self, region_id: int, type_ids: list[int]) -> list[EsiRegionalHistoryRecord]: ...


class AdamDemandCapableClient(Protocol):
    def fetch_npc_demand(self, location_ids: list[int], type_ids: list[int]) -> list[AdamNpcDemandRecord]: ...


@dataclass(frozen=True)
class StructureSnapshotBatch:
    structure_id: int
    snapshot_time: datetime
    orders: list[StructureOrderInput]


class StructureSnapshotCapableClient(Protocol):
    def fetch_structure_snapshot(self, structure_id: int) -> StructureSnapshotBatch | None: ...


class SyncService:
    STATUS_CARD_DEFINITIONS: tuple[tuple[str, str], ...] = (
        ("adam4eve_sync", "Adam4EVE sync"),
        ("esi_history_sync", "ESI region sync"),
        ("opportunity_rebuild", "Opportunity rebuild"),
    )
    WORKER_HEARTBEAT_STALE_MINUTES = 15

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        adam_client: AdamDemandCapableClient | None = None,
        esi_client: HistoryCapableEsiClient | None = None,
        structure_snapshot_client: StructureSnapshotCapableClient | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.adam_client = adam_client or Adam4EveClient()
        self.esi_client = esi_client or EsiClient()
        self.structure_snapshot_client = structure_snapshot_client

    @staticmethod
    def _ensure_utc(timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)

    def get_status(self) -> list[SyncStatusCard]:
        session = self.session_factory()
        try:
            cards: list[SyncStatusCard] = []
            for job_type, label in self.STATUS_CARD_DEFINITIONS:
                job_rows = session.scalars(
                    select(SyncJobRun)
                    .where(SyncJobRun.job_type == job_type)
                    .order_by(SyncJobRun.started_at.desc(), SyncJobRun.id.desc())
                ).all()
                successful_rows = [row for row in job_rows if row.status == "success"]
                failed_rows = [row for row in job_rows if row.status == "failed"]
                last_successful_sync = (
                    self._ensure_utc(successful_rows[0].finished_at)
                    if successful_rows and successful_rows[0].finished_at is not None
                    else None
                )
                status = "idle"
                if job_rows:
                    status = "degraded" if failed_rows else "healthy"

                cards.append(
                    SyncStatusCard(
                        key=job_type,
                        label=label,
                        status=status,
                        last_successful_sync=last_successful_sync,
                        next_scheduled_sync=None,
                        recent_error_count=len(failed_rows),
                    )
                )

            heartbeat = session.scalar(
                select(WorkerHeartbeat).order_by(WorkerHeartbeat.recorded_at.desc(), WorkerHeartbeat.id.desc())
            )
            cards.append(self._build_worker_status_card(heartbeat))
            return cards
        finally:
            session.close()

    def _build_worker_status_card(self, heartbeat: WorkerHeartbeat | None) -> SyncStatusCard:
        if heartbeat is None:
            return SyncStatusCard(
                key="worker",
                label="Worker health",
                status="idle",
                last_successful_sync=None,
                next_scheduled_sync=None,
                recent_error_count=0,
            )

        heartbeat_time = self._ensure_utc(heartbeat.recorded_at)
        age_minutes = (datetime.now(UTC) - heartbeat_time).total_seconds() / 60
        status = "healthy" if age_minutes <= self.WORKER_HEARTBEAT_STALE_MINUTES else "degraded"
        return SyncStatusCard(
            key="worker",
            label="Worker health",
            status=status,
            last_successful_sync=heartbeat_time,
            next_scheduled_sync=None,
            recent_error_count=0,
        )

    def list_jobs(self) -> list[SyncJobRunResponse]:
        session = self.session_factory()
        try:
            rows = session.scalars(
                select(SyncJobRun).order_by(SyncJobRun.started_at.desc(), SyncJobRun.id.desc())
            ).all()
            return [
                SyncJobRunResponse(
                    id=row.id,
                    started_at=row.started_at,
                    finished_at=row.finished_at,
                    job_type=row.job_type,
                    status=row.status,
                    duration_ms=row.duration_ms,
                    records_processed=row.records_processed,
                    target_type=row.target_type,
                    target_id=row.target_id,
                    message=row.message,
                    error_details=row.error_details,
                )
                for row in rows
            ]
        finally:
            session.close()

    def trigger_job(self, job_type: str) -> SyncJobRunResponse:
        now = datetime.now(UTC)
        message = f"Queued {job_type}."
        records_processed = 0
        target_type = "manual"
        target_id: str | None = None
        session = self.session_factory()
        try:
            job_run = SyncJobRun(
                job_type=job_type,
                status="pending",
                triggered_by="manual",
                started_at=now,
                records_processed=0,
                target_type=target_type,
                target_id=target_id,
                message=message,
            )
            session.add(job_run)
            session.flush()

            if job_type == "foundation_seed_sync":
                foundation_result = FoundationDataService().bootstrap(session)
                records_processed = foundation_result.records_processed
                message = f"Seeded foundation data ({records_processed} records processed)."
            elif job_type == "adam4eve_sync":
                npc_locations = session.scalars(
                    select(Location)
                    .where(Location.location_type == "npc_station")
                    .order_by(Location.location_id.asc())
                    .limit(3)
                ).all()
                items = session.scalars(select(Item).order_by(Item.type_id.asc()).limit(3)).all()
                if not npc_locations or not items:
                    message = "Skipped Adam4EVE sync because reference data is missing."
                else:
                    adam_demand_rows = self.adam_client.fetch_npc_demand(
                        [location.location_id for location in npc_locations],
                        [item.type_id for item in items],
                    )
                    demand_result = AdamNpcDemandIngestionService().ingest_npc_demand(
                        session,
                        records=adam_demand_rows,
                    )
                    records_processed = demand_result.records_processed
                    target_type = "locations"
                    target_id = str(len(npc_locations))
                    message = (
                        "Synced Adam4EVE NPC demand "
                        f"({demand_result.created} created, {demand_result.updated} updated)."
                    )
            elif job_type == "esi_history_sync":
                region = session.scalar(select(Region).order_by(Region.region_id.asc()))
                items = session.scalars(select(Item).order_by(Item.type_id.asc()).limit(3)).all()
                if region is None or not items:
                    message = "Skipped ESI history sync because reference data is missing."
                else:
                    history_rows = self.esi_client.fetch_regional_history(
                        region.region_id,
                        [item.type_id for item in items],
                    )
                    history_result = EsiRegionalHistoryIngestionService().ingest_region_history(
                        session,
                        eve_region_id=region.region_id,
                        records=history_rows,
                    )
                    records_processed = history_result.records_processed
                    target_type = "region"
                    target_id = str(region.region_id)
                    message = (
                        f"Synced ESI history for region {region.region_id} "
                        f"({history_result.created} created, {history_result.updated} updated)."
                    )
            elif job_type == "opportunity_rebuild":
                rebuild_demand_rows: list[MarketDemandResolved] = list(
                    session.scalars(
                    select(MarketDemandResolved).order_by(
                        MarketDemandResolved.location_id.asc(),
                        MarketDemandResolved.period_days.asc(),
                        MarketDemandResolved.type_id.asc(),
                    )
                    ).all()
                )
                if not rebuild_demand_rows:
                    message = "Skipped opportunity rebuild because computed demand rows are missing."
                else:
                    scope_count = 0
                    generated_count = 0
                    grouped_demands: dict[tuple[int, int], list[MarketDemandResolved]] = {}
                    for row in rebuild_demand_rows:
                        grouped_demands.setdefault((row.location_id, row.period_days), []).append(row)

                    for (target_location_id, period_days), rows in grouped_demands.items():
                        type_ids = [row.type_id for row in rows]
                        source_location_ids: list[int] = list(
                            session.scalars(
                                select(MarketPricePeriod.location_id)
                                .where(
                                    MarketPricePeriod.period_days == period_days,
                                    MarketPricePeriod.type_id.in_(type_ids),
                                    MarketPricePeriod.location_id != target_location_id,
                                )
                                .distinct()
                            ).all()
                        )
                        if not source_location_ids:
                            continue

                        result = OpportunityGenerationService().generate_for_target(
                            session,
                            target_location_id=target_location_id,
                            source_location_ids=source_location_ids,
                            type_ids=type_ids,
                            period_days=period_days,
                        )
                        scope_count += 1
                        generated_count += result.item_count

                    records_processed = generated_count
                    target_type = "targets"
                    target_id = str(scope_count)
                    message = (
                        "Rebuilt opportunities "
                        f"({generated_count} item rows across {scope_count} target scopes)."
                    )
            elif job_type == "structure_snapshot_sync":
                structure_sync_result = self._sync_structure_snapshots(session)
                records_processed = structure_sync_result.records_processed
                target_type = "structures"
                target_id = str(structure_sync_result.structure_count)
                message = (
                    "Synced structure snapshots "
                    f"({structure_sync_result.snapshot_count} snapshots, "
                    f"{structure_sync_result.delta_count} deltas, "
                    f"{structure_sync_result.demand_period_count} demand periods)."
                )

            finished_at = datetime.now(UTC)
            duration_ms = max(int((finished_at - now).total_seconds() * 1000), 0)
            job_run.status = "success"
            job_run.finished_at = finished_at
            job_run.duration_ms = duration_ms
            job_run.records_processed = records_processed
            job_run.target_type = target_type
            job_run.target_id = target_id
            job_run.message = message
            session.commit()

            return SyncJobRunResponse(
                id=job_run.id,
                started_at=job_run.started_at,
                finished_at=job_run.finished_at,
                job_type=job_run.job_type,
                status=job_run.status,
                duration_ms=job_run.duration_ms,
                records_processed=job_run.records_processed,
                target_type=job_run.target_type,
                target_id=job_run.target_id,
                message=job_run.message,
                error_details=job_run.error_details,
            )
        finally:
            session.close()

    def _sync_structure_snapshots(self, session: Session) -> "StructureSnapshotSyncResult":
        if self.structure_snapshot_client is None:
            return StructureSnapshotSyncResult(0, 0, 0, 0, 0)

        tracked_structures = session.scalars(
            select(TrackedStructure)
            .join(Location, Location.location_id == TrackedStructure.structure_id)
            .where(TrackedStructure.is_enabled.is_(True), Location.location_type == "structure")
            .order_by(TrackedStructure.structure_id.asc())
        ).all()
        if not tracked_structures:
            return StructureSnapshotSyncResult(0, 0, 0, 0, 0)

        snapshot_service = StructureSnapshotService()
        demand_service = StructureDemandPeriodService()
        snapshot_count = 0
        delta_count = 0
        demand_period_count = 0
        structure_count = 0

        for tracked_structure in tracked_structures:
            batch = self.structure_snapshot_client.fetch_structure_snapshot(tracked_structure.structure_id)
            if batch is None or not batch.orders:
                continue
            if batch.structure_id != tracked_structure.structure_id:
                raise ValueError("structure snapshot batch structure_id did not match tracked structure")

            normalized_snapshot_time = self._ensure_utc(batch.snapshot_time)
            existing_snapshot = session.scalar(
                select(StructureSnapshot).where(
                    StructureSnapshot.structure_id == tracked_structure.structure_id,
                    StructureSnapshot.snapshot_time == normalized_snapshot_time,
                )
            )
            if existing_snapshot is not None:
                continue

            structure_count += 1
            snapshot_result = snapshot_service.persist_snapshot(
                session,
                structure_id=tracked_structure.structure_id,
                snapshot_time=normalized_snapshot_time,
                orders=batch.orders,
            )
            snapshot_count += 1

            current_snapshot = session.get(StructureSnapshot, snapshot_result.snapshot_id)
            previous_snapshot = session.scalar(
                select(StructureSnapshot)
                .where(
                    StructureSnapshot.structure_id == tracked_structure.structure_id,
                    StructureSnapshot.snapshot_time < normalized_snapshot_time,
                )
                .order_by(StructureSnapshot.snapshot_time.desc(), StructureSnapshot.id.desc())
            )
            if current_snapshot is None or previous_snapshot is None:
                continue

            delta_result = snapshot_service.persist_deltas_for_snapshots(
                session,
                structure_id=tracked_structure.structure_id,
                previous_snapshot_id=previous_snapshot.id,
                current_snapshot_id=current_snapshot.id,
            )
            delta_count += delta_result.delta_count
            if delta_result.delta_count == 0:
                continue

            type_ids = session.scalars(
                select(StructureOrderDelta.type_id)
                .where(
                    StructureOrderDelta.structure_id == tracked_structure.structure_id,
                    StructureOrderDelta.to_snapshot_time == normalized_snapshot_time,
                )
                .distinct()
            ).all()
            for type_id in type_ids:
                demand_service.upsert_period(
                    session,
                    structure_id=tracked_structure.structure_id,
                    type_id=type_id,
                    period_days=14,
                    as_of=normalized_snapshot_time,
                )
                demand_period_count += 1

        return StructureSnapshotSyncResult(
            structure_count=structure_count,
            snapshot_count=snapshot_count,
            delta_count=delta_count,
            demand_period_count=demand_period_count,
            records_processed=snapshot_count + delta_count + demand_period_count,
        )


    def get_fallback_status(self) -> list[FallbackDiagnostic]:
        session = self.session_factory()
        try:
            tracked_structures = session.scalars(
                select(TrackedStructure)
                .join(Location, Location.location_id == TrackedStructure.structure_id)
                .where(Location.location_type == "structure")
                .order_by(TrackedStructure.structure_id.asc())
            ).all()
            if not tracked_structures:
                return []

            tracked_location_ids = [
                location_id
                for location_id in session.scalars(
                    select(Location.id).where(Location.location_id.in_([row.structure_id for row in tracked_structures]))
                ).all()
            ]
            demand_rows = session.scalars(
                select(MarketDemandResolved)
                .where(MarketDemandResolved.location_id.in_(tracked_location_ids))
                .order_by(
                    MarketDemandResolved.location_id.asc(),
                    MarketDemandResolved.computed_at.desc(),
                    MarketDemandResolved.id.desc(),
                )
            ).all()

            latest_demand_by_location_id: dict[int, MarketDemandResolved] = {}
            for demand_row in demand_rows:
                latest_demand_by_location_id.setdefault(demand_row.location_id, demand_row)

            diagnostics: list[FallbackDiagnostic] = []
            for tracked_structure in tracked_structures:
                location = session.scalar(
                    select(Location).where(Location.location_id == tracked_structure.structure_id)
                )
                if location is None:
                    continue

                fallback_demand_row = latest_demand_by_location_id.get(location.id)
                if fallback_demand_row is None:
                    continue

                coverage_pct = 0.0
                structure_period = session.scalar(
                    select(StructureDemandPeriod).where(
                        StructureDemandPeriod.structure_id == tracked_structure.structure_id,
                        StructureDemandPeriod.type_id == fallback_demand_row.type_id,
                        StructureDemandPeriod.period_days == fallback_demand_row.period_days,
                    )
                )
                if structure_period is not None:
                    coverage_pct = structure_period.coverage_pct

                diagnostics.append(
                    FallbackDiagnostic(
                        structure_name=tracked_structure.name,
                        structure_id=tracked_structure.structure_id,
                        demand_source=fallback_demand_row.demand_source,
                        confidence_score=fallback_demand_row.confidence_score,
                        coverage_pct=coverage_pct,
                    )
                )

            return diagnostics
        finally:
            session.close()


@dataclass(frozen=True)
class StructureSnapshotSyncResult:
    structure_count: int
    snapshot_count: int
    delta_count: int
    demand_period_count: int
    records_processed: int
