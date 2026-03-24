from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import signal
from threading import Event, Lock, current_thread, main_thread
from typing import Callable, Protocol, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.sync import FallbackDiagnostic, SyncJobRunResponse, SyncStatusCard
from app.db.session import SessionLocal
from app.models.all_models import (
    EsiCharacter,
    EsiMarketOrder,
    Item,
    Location,
    MarketDemandResolved,
    MarketPricePeriod,
    Region,
    StructureDemandPeriod,
    StructureOrderDelta,
    StructureSnapshot,
    SyncJobRun,
    TrackedStructure,
    WorkerHeartbeat,
)
from app.repositories.seed_data import FoundationSeedSource, StationSeed
from app.services.adam4eve.client import Adam4EveClient
from app.services.adam4eve.ingestion import AdamNpcDemandIngestionService, AdamNpcDemandRecord
from app.services.demand.market_demand import MarketDemandResolutionService
from app.services.esi.client import EsiClient, EsiRegionalOrderRecord
from app.services.esi.history_ingestion import EsiRegionalHistoryIngestionService, EsiRegionalHistoryRecord
from app.services.esi.orders_ingestion import EsiRegionalOrderIngestionService
from app.services.opportunities.generation import OpportunityGenerationService
from app.services.pricing.market_price_periods import MarketPricePeriodService
from app.services.settings_service import SettingsService
from app.services.structures.demand_periods import StructureDemandPeriodService
from app.services.structures.snapshots import StructureOrderInput, StructureSnapshotService
from app.services.sync.foundation_data import FoundationDataService
from app.services.sync.foundation_import import CcpSdeClient, FoundationImportService


class HistoryCapableEsiClient(Protocol):
    def fetch_regional_history(self, region_id: int, type_ids: list[int]) -> list[EsiRegionalHistoryRecord]: ...


class FoundationImportCapableClient(Protocol):
    def build_seed_source(self) -> FoundationSeedSource: ...


class UniverseCapableEsiClient(Protocol):
    def fetch_station(self, station_id: int) -> StationSeed: ...

    def fetch_regional_orders(self, region_id: int) -> list[object]: ...


class AdamDemandCapableClient(Protocol):
    def fetch_npc_demand(self, location_ids: list[int], type_ids: list[int]) -> list[AdamNpcDemandRecord]: ...


@dataclass(frozen=True)
class StructureSnapshotBatch:
    structure_id: int
    snapshot_time: datetime
    orders: list[StructureOrderInput]


class StructureSnapshotCapableClient(Protocol):
    def fetch_structure_snapshot(self, structure_id: int) -> StructureSnapshotBatch | None: ...


class JobCancelledError(RuntimeError):
    pass


_PROCESS_CANCELLATION_EVENT = Event()
_SIGNAL_HANDLER_LOCK = Lock()
_SIGNAL_HANDLERS_REGISTERED = False


def register_cancellation_signal_handlers() -> None:
    global _SIGNAL_HANDLERS_REGISTERED

    if current_thread() is not main_thread():
        return

    with _SIGNAL_HANDLER_LOCK:
        if _SIGNAL_HANDLERS_REGISTERED:
            return

        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handler = signal.getsignal(signum)

            def _handler(sig: int, frame: object, *, previous: object = previous_handler) -> None:
                _PROCESS_CANCELLATION_EVENT.set()
                if callable(previous):
                    previous(sig, frame)

            signal.signal(signum, _handler)

        _SIGNAL_HANDLERS_REGISTERED = True


class SyncService:
    SUPPORTED_PERIOD_DAYS: tuple[int, ...] = (3, 7, 14, 30)
    STALE_CANCELLING_JOB_MINUTES = 2
    STATUS_CARD_DEFINITIONS: tuple[tuple[str, str], ...] = (
        ("foundation_import_sync", "Foundation universe sync"),
        ("adam4eve_sync", "Adam4EVE sync"),
        ("esi_history_sync", "ESI region sync"),
        ("esi_market_orders_sync", "ESI market orders sync"),
        ("structure_snapshot_sync", "Structure snapshot sync"),
        ("character_sync", "Character sync"),
        ("opportunity_rebuild", "Opportunity rebuild"),
    )
    WORKER_HEARTBEAT_STALE_MINUTES = 15
    DEBUG_REGION_LIMIT = 1

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        adam_client: AdamDemandCapableClient | None = None,
        esi_client: HistoryCapableEsiClient | None = None,
        foundation_client: FoundationImportCapableClient | None = None,
        structure_snapshot_client: StructureSnapshotCapableClient | None = None,
    ) -> None:
        register_cancellation_signal_handlers()
        self.session_factory = session_factory
        self.adam_client = adam_client or Adam4EveClient()
        self.esi_client = esi_client or EsiClient()
        self.foundation_client = foundation_client or CcpSdeClient()
        self.structure_snapshot_client = structure_snapshot_client

    @staticmethod
    def _ensure_utc(timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)

    def get_status(self) -> list[SyncStatusCard]:
        def load_status() -> list[SyncStatusCard]:
            session = self.session_factory()
            try:
                self._finalize_stale_cancelling_jobs(session)
                cards: list[SyncStatusCard] = []
                for job_type, label in self.STATUS_CARD_DEFINITIONS:
                    job_rows = session.scalars(
                        select(SyncJobRun)
                        .where(SyncJobRun.job_type == job_type)
                        .order_by(SyncJobRun.started_at.desc(), SyncJobRun.id.desc())
                    ).all()
                    successful_rows = [row for row in job_rows if row.status == "success"]
                    failed_rows = [row for row in job_rows if row.status == "failed"]
                    active_rows = [row for row in job_rows if row.status in {"running", "cancelling"}]
                    last_successful_sync = (
                        self._ensure_utc(successful_rows[0].finished_at)
                        if successful_rows and successful_rows[0].finished_at is not None
                        else None
                    )
                    status = "idle"
                    if active_rows:
                        status = "running"
                    elif job_rows:
                        status = "degraded" if failed_rows else "healthy"

                    cards.append(
                        SyncStatusCard(
                            key=job_type,
                            label=label,
                            status=status,
                            last_successful_sync=last_successful_sync,
                            next_scheduled_sync=None,
                            recent_error_count=len(failed_rows),
                            active_message=active_rows[0].message if active_rows else None,
                            progress_phase=active_rows[0].progress_phase if active_rows else None,
                            progress_current=active_rows[0].progress_current if active_rows else None,
                            progress_total=active_rows[0].progress_total if active_rows else None,
                            progress_unit=active_rows[0].progress_unit if active_rows else None,
                        )
                    )

                heartbeat = session.scalar(
                    select(WorkerHeartbeat).order_by(WorkerHeartbeat.recorded_at.desc(), WorkerHeartbeat.id.desc())
                )
                cards.append(self._build_worker_status_card(heartbeat))
                return cards
            finally:
                session.close()

        return load_status()

    def _build_worker_status_card(self, heartbeat: WorkerHeartbeat | None) -> SyncStatusCard:
        if heartbeat is None:
            return SyncStatusCard(
                key="worker",
                label="Worker health",
                status="idle",
                last_successful_sync=None,
                next_scheduled_sync=None,
                recent_error_count=0,
                active_message=None,
                progress_phase=None,
                progress_current=None,
                progress_total=None,
                progress_unit=None,
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
            active_message=None,
            progress_phase=None,
            progress_current=None,
            progress_total=None,
            progress_unit=None,
        )

    def list_jobs(self) -> list[SyncJobRunResponse]:
        def load_jobs() -> list[SyncJobRunResponse]:
            session = self.session_factory()
            try:
                self._finalize_stale_cancelling_jobs(session)
                rows = session.scalars(
                    select(SyncJobRun).order_by(SyncJobRun.started_at.desc(), SyncJobRun.id.desc())
                ).all()
                return [self._to_job_response(row) for row in rows]
            finally:
                session.close()

        return load_jobs()

    def trigger_job(self, job_type: str) -> SyncJobRunResponse:
        now = datetime.now(UTC)
        session = self.session_factory()
        try:
            self._finalize_stale_cancelling_jobs(session)
            job_run = SyncJobRun(
                job_type=job_type,
                status="running",
                triggered_by="manual",
                started_at=now,
                records_processed=0,
                target_type="manual",
                target_id=None,
                progress_phase="Queued",
                progress_current=None,
                progress_total=None,
                progress_unit=None,
                message=f"Running {job_type}.",
            )
            session.add(job_run)
            session.flush()
            session.commit()

            records_processed = 0
            target_type = "manual"
            target_id: str | None = None
            try:
                records_processed, target_type, target_id, message = self._run_job(
                    session,
                    job_type=job_type,
                    job_id=job_run.id,
                )
            except JobCancelledError as exc:
                session.rollback()
                persisted_job = session.get(SyncJobRun, job_run.id)
                if persisted_job is None:
                    raise
                finished_at = datetime.now(UTC)
                persisted_job.status = "cancelled"
                persisted_job.finished_at = finished_at
                persisted_job.duration_ms = max(int((finished_at - now).total_seconds() * 1000), 0)
                persisted_job.records_processed = records_processed
                persisted_job.target_type = target_type
                persisted_job.target_id = target_id
                if persisted_job.progress_total is not None and persisted_job.progress_current is None:
                    persisted_job.progress_current = 0
                persisted_job.message = str(exc)
                session.commit()
                return self._to_job_response(persisted_job)
            except Exception as exc:
                session.rollback()
                persisted_job = session.get(SyncJobRun, job_run.id)
                if persisted_job is None:
                    raise
                finished_at = datetime.now(UTC)
                persisted_job.status = "failed"
                persisted_job.finished_at = finished_at
                persisted_job.duration_ms = max(int((finished_at - now).total_seconds() * 1000), 0)
                persisted_job.records_processed = records_processed
                persisted_job.target_type = target_type
                persisted_job.target_id = target_id
                if persisted_job.progress_total is not None and persisted_job.progress_current is None:
                    persisted_job.progress_current = 0
                persisted_job.message = f"Failed {job_type}."
                persisted_job.error_details = str(exc)
                session.commit()
                return self._to_job_response(persisted_job)

            persisted_job = session.get(SyncJobRun, job_run.id)
            if persisted_job is None:
                raise LookupError(f"Sync job {job_run.id} disappeared during execution.")
            finished_at = datetime.now(UTC)
            persisted_job.status = "success"
            persisted_job.finished_at = finished_at
            persisted_job.duration_ms = max(int((finished_at - now).total_seconds() * 1000), 0)
            persisted_job.records_processed = records_processed
            persisted_job.target_type = target_type
            persisted_job.target_id = target_id
            if persisted_job.progress_total is not None:
                persisted_job.progress_current = persisted_job.progress_total
            persisted_job.progress_phase = "Completed"
            persisted_job.message = message
            persisted_job.error_details = None
            session.commit()
            return self._to_job_response(persisted_job)
        finally:
            session.close()

    def cancel_job(self, job_id: int) -> SyncJobRunResponse:
        session = self.session_factory()
        try:
            self._finalize_stale_cancelling_jobs(session)
            job_run = session.get(SyncJobRun, job_id)
            if job_run is None:
                raise LookupError(f"Sync job {job_id} was not found.")
            if job_run.finished_at is not None or job_run.status in {"success", "failed", "cancelled"}:
                return self._to_job_response(job_run)

            def mark_cancelling() -> None:
                refreshed_job = session.get(SyncJobRun, job_id)
                if refreshed_job is None:
                    raise LookupError(f"Sync job {job_id} was not found.")
                refreshed_job.status = "cancelling"
                refreshed_job.message = f"Cancelling {refreshed_job.job_type}."

            mark_cancelling()
            session.commit()
            return self._to_job_response(job_run)
        finally:
            session.close()

    def _run_job(self, session: Session, *, job_type: str, job_id: int) -> tuple[int, str, str | None, str]:
        records_processed = 0
        target_type = "manual"
        target_id: str | None = None
        message = f"Queued {job_type}."
        debug_enabled = SettingsService().get_settings().debug_enabled

        if job_type == "foundation_seed_sync":
            foundation_result = FoundationDataService().bootstrap(
                session,
                cancellation_check=lambda: self._check_for_cancellation(session, job_id),
            )
            records_processed = foundation_result.records_processed
            message = f"Seeded foundation data ({records_processed} records processed)."
        elif job_type == "foundation_import_sync":
            foundation_import = FoundationImportService().import_from_seed_source(
                session,
                seed_source=self.foundation_client.build_seed_source(),
                cancellation_check=lambda: self._check_for_cancellation(session, job_id),
            )
            records_processed = foundation_import.records_processed
            target_type = "universe"
            target_id = "all"
            message = f"Imported universe foundation data ({records_processed} records processed)."
        elif job_type == "adam4eve_sync":
            npc_locations = session.scalars(
                select(Location)
                .where(Location.location_type == "npc_station")
                .order_by(Location.location_id.asc())
            ).all()
            if debug_enabled:
                debug_region_ids = {region.id for region in self._all_regions(session, debug_enabled=True)}
                npc_locations = [location for location in npc_locations if location.region_id in debug_region_ids]
            items = session.scalars(select(Item).order_by(Item.type_id.asc())).all()
            if not npc_locations or not items:
                message = "Skipped Adam4EVE sync because reference data is missing."
            else:
                self._check_for_cancellation(session, job_id)
                adam_demand_rows = self.adam_client.fetch_npc_demand(
                    [location.location_id for location in npc_locations],
                    [item.type_id for item in items],
                )
                demand_result = AdamNpcDemandIngestionService().ingest_npc_demand(
                    session,
                    records=adam_demand_rows,
                )
                derived_count = self._refresh_market_demand_for_locations(
                    session,
                    location_ids=[location.id for location in npc_locations],
                    type_ids=[item.id for item in items],
                    cancellation_check=lambda: self._check_for_cancellation(session, job_id),
                )
                generated_count, scope_count = self._rebuild_opportunities(
                    session,
                    cancellation_check=lambda: self._check_for_cancellation(session, job_id),
                )
                records_processed = demand_result.records_processed + derived_count + generated_count
                target_type = "locations"
                target_id = str(len(npc_locations))
                message = (
                    "Synced Adam4EVE NPC demand "
                    f"({demand_result.created} created, {demand_result.updated} updated, "
                    f"{derived_count} resolved demand rows, {generated_count} opportunity items across {scope_count} scopes)."
                )
        elif job_type == "esi_history_sync":
            regions = self._all_regions(session, debug_enabled=debug_enabled)
            items = self._history_sync_items(session, region_ids=[region.id for region in regions])
            if not regions or not items:
                message = (
                    "Skipped ESI history sync because no eligible market scope is available yet. "
                    "Sync NPC orders first for the imported regions."
                )
            else:
                downloaded_history_batches: list[tuple[Region, list[EsiRegionalHistoryRecord]]] = []
                total_history_processed = 0
                total_created = 0
                total_updated = 0
                price_count = 0
                self._update_job_progress(
                    session,
                    job_id,
                    progress_phase="Downloading ESI history batches",
                    progress_current=0,
                    progress_total=len(regions),
                    progress_unit="regions",
                    message=f"Downloading ESI history for 0 / {len(regions)} regions.",
                )
                for region_index, region in enumerate(regions, start=1):
                    self._check_for_cancellation(session, job_id)
                    history_rows = self.esi_client.fetch_regional_history(
                        region.region_id,
                        [item.type_id for item in items],
                    )
                    downloaded_history_batches.append((region, history_rows))
                    self._update_job_progress(
                        session,
                        job_id,
                        progress_phase="Downloading ESI history batches",
                        progress_current=region_index,
                        progress_total=len(regions),
                        progress_unit="regions",
                        message=f"Downloaded ESI history for {region_index} / {len(regions)} regions.",
                    )
                total_downloaded_records = sum(len(rows) for _, rows in downloaded_history_batches)
                self._update_job_progress(
                    session,
                    job_id,
                    progress_phase="Processing downloaded ESI history records",
                    progress_current=0,
                    progress_total=total_downloaded_records,
                    progress_unit="downloaded records",
                    message=f"Processing 0 / {total_downloaded_records} downloaded ESI history records.",
                )
                processed_downloaded_records = 0
                for region, history_rows in downloaded_history_batches:
                    self._check_for_cancellation(session, job_id)
                    history_result = EsiRegionalHistoryIngestionService().ingest_region_history(
                        session,
                        eve_region_id=region.region_id,
                        records=history_rows,
                    )
                    total_history_processed += history_result.records_processed
                    total_created += history_result.created
                    total_updated += history_result.updated
                    processed_downloaded_records += history_result.records_processed
                    price_count += self._refresh_market_prices_for_region(
                        session,
                        region_id=region.id,
                        type_ids=[item.id for item in items],
                        cancellation_check=lambda: self._check_for_cancellation(session, job_id),
                    )
                    self._update_job_progress(
                        session,
                        job_id,
                        progress_phase="Processing downloaded ESI history records",
                        progress_current=processed_downloaded_records,
                        progress_total=total_downloaded_records,
                        progress_unit="downloaded records",
                        message=(
                            f"Processed {processed_downloaded_records} / {total_downloaded_records} "
                            "downloaded ESI history records."
                        ),
                    )
                generated_count, scope_count = self._rebuild_opportunities(
                    session,
                    cancellation_check=lambda: self._check_for_cancellation(session, job_id),
                )
                records_processed = total_history_processed + price_count + generated_count
                target_type = "regions"
                target_id = str(len(regions))
                message = (
                    "Synced ESI history "
                    f"({total_created} created, {total_updated} updated across {len(regions)} regions, "
                    f"{price_count} price periods, {generated_count} opportunity items across {scope_count} scopes)."
                )
        elif job_type == "esi_market_orders_sync":
            universe_client = cast(UniverseCapableEsiClient, self.esi_client)
            regions = self._all_regions(session, debug_enabled=debug_enabled)
            if not regions:
                message = "Skipped ESI market orders sync because imported regions are missing."
            else:
                ingestion_service = EsiRegionalOrderIngestionService()
                downloaded_order_batches: list[tuple[Region, list[EsiRegionalOrderRecord]]] = []
                total_processed = 0
                total_created = 0
                total_updated = 0
                total_deleted = 0
                total_stations_created = 0
                total_skipped_missing_items = 0
                total_skipped_non_npc_locations = 0
                self._update_job_progress(
                    session,
                    job_id,
                    progress_phase="Downloading ESI market order batches",
                    progress_current=0,
                    progress_total=len(regions),
                    progress_unit="regions",
                    message=f"Downloading ESI market orders for 0 / {len(regions)} regions.",
                )
                for region_index, region in enumerate(regions, start=1):
                    self._check_for_cancellation(session, job_id)
                    order_rows = cast(list[EsiRegionalOrderRecord], universe_client.fetch_regional_orders(region.region_id))
                    downloaded_order_batches.append((region, order_rows))
                    self._update_job_progress(
                        session,
                        job_id,
                        progress_phase="Downloading ESI market order batches",
                        progress_current=region_index,
                        progress_total=len(regions),
                        progress_unit="regions",
                        message=f"Downloaded ESI market orders for {region_index} / {len(regions)} regions.",
                    )
                total_downloaded_orders = sum(len(rows) for _, rows in downloaded_order_batches)
                self._update_job_progress(
                    session,
                    job_id,
                    progress_phase="Processing downloaded ESI market orders",
                    progress_current=0,
                    progress_total=total_downloaded_orders,
                    progress_unit="downloaded records",
                    message=f"Processing 0 / {total_downloaded_orders} downloaded ESI market orders.",
                )
                for region, order_rows in downloaded_order_batches:
                    self._check_for_cancellation(session, job_id)
                    result = ingestion_service.ingest_region_orders(
                        session,
                        eve_region_id=region.region_id,
                        records=order_rows,
                        universe_client=universe_client,
                        cancellation_check=lambda: self._check_for_cancellation(session, job_id),
                    )
                    total_processed += result.records_processed
                    total_created += result.created
                    total_updated += result.updated
                    total_deleted += result.deleted
                    total_stations_created += result.stations_created
                    total_skipped_missing_items += result.skipped_missing_items
                    total_skipped_non_npc_locations += result.skipped_non_npc_locations
                    self._update_job_progress(
                        session,
                        job_id,
                        progress_phase="Processing downloaded ESI market orders",
                        progress_current=total_processed,
                        progress_total=total_downloaded_orders,
                        progress_unit="downloaded records",
                        message=f"Processed {total_processed} / {total_downloaded_orders} downloaded ESI market orders.",
                    )

                records_processed = total_processed
                target_type = "regions"
                target_id = str(len(regions))
                message = (
                    "Synced ESI market orders "
                    f"({total_processed} active orders, {total_created} created, {total_updated} updated, "
                    f"{total_deleted} deleted, {total_stations_created} stations discovered, "
                    f"{total_skipped_missing_items} skipped because item foundation data was missing, "
                    f"{total_skipped_non_npc_locations} skipped because the location was not an NPC station across {len(regions)} regions)."
                )
        elif job_type == "character_sync":
            character_ids = list(
                session.scalars(
                    select(EsiCharacter.character_id)
                    .where(EsiCharacter.sync_enabled.is_(True))
                    .order_by(EsiCharacter.character_id.asc())
                ).all()
            )
            if not character_ids:
                message = "Skipped character sync because no enabled characters are connected."
            else:
                from app.services.characters.service import CharacterService

                character_service = CharacterService(session_factory=self.session_factory)
                synced_count = 0
                discovered_count = 0
                for character_id in character_ids:
                    self._check_for_cancellation(session, job_id)
                    discovered_structures = character_service.sync_character(character_id)
                    synced_count += 1
                    discovered_count += len(discovered_structures)

                records_processed = discovered_count
                target_type = "characters"
                target_id = str(synced_count)
                message = (
                    "Synced characters "
                    f"({synced_count} characters, {discovered_count} accessible structures refreshed)."
                )
        elif job_type == "opportunity_rebuild":
            generated_count, scope_count = self._rebuild_opportunities(
                session,
                cancellation_check=lambda: self._check_for_cancellation(session, job_id),
            )
            if generated_count == 0 and scope_count == 0:
                message = "Skipped opportunity rebuild because computed demand rows are missing."
            else:
                records_processed = generated_count
                target_type = "targets"
                target_id = str(scope_count)
                message = f"Rebuilt opportunities ({generated_count} item rows across {scope_count} target scopes)."
        elif job_type == "structure_snapshot_sync":
            structure_sync_result = self._sync_structure_snapshots(
                session,
                cancellation_check=lambda: self._check_for_cancellation(session, job_id),
            )
            location_ids = list(
                session.scalars(
                    select(Location.id).where(Location.location_id.in_(structure_sync_result.structure_ids))
                ).all()
            )
            demand_count = self._refresh_market_demand_for_locations(
                session,
                location_ids=location_ids,
                type_ids=list(structure_sync_result.type_ids),
                period_days_options=(14,),
                cancellation_check=lambda: self._check_for_cancellation(session, job_id),
            )
            generated_count, scope_count = self._rebuild_opportunities(
                session,
                period_days_options=(14,),
                cancellation_check=lambda: self._check_for_cancellation(session, job_id),
            )
            records_processed = structure_sync_result.records_processed + demand_count + generated_count
            target_type = "structures"
            target_id = str(structure_sync_result.structure_count)
            message = (
                "Synced structure snapshots "
                f"({structure_sync_result.snapshot_count} snapshots, "
                f"{structure_sync_result.delta_count} deltas, "
                f"{structure_sync_result.demand_period_count} demand periods, "
                f"{demand_count} resolved demand rows, {generated_count} opportunity items across {scope_count} scopes)."
            )

        return records_processed, target_type, target_id, message

    def _sync_structure_snapshots(
        self,
        session: Session,
        *,
        cancellation_check: Callable[[], None] | None = None,
    ) -> "StructureSnapshotSyncResult":
        if self.structure_snapshot_client is None:
            return StructureSnapshotSyncResult(0, 0, 0, 0, (), (), 0)

        tracked_structures = session.scalars(
            select(TrackedStructure)
            .join(Location, Location.location_id == TrackedStructure.structure_id)
            .where(TrackedStructure.is_enabled.is_(True), Location.location_type == "structure")
            .order_by(TrackedStructure.structure_id.asc())
        ).all()
        if not tracked_structures:
            return StructureSnapshotSyncResult(0, 0, 0, 0, (), (), 0)

        snapshot_service = StructureSnapshotService()
        demand_service = StructureDemandPeriodService()
        snapshot_count = 0
        delta_count = 0
        demand_period_count = 0
        structure_count = 0
        touched_type_ids: set[int] = set()

        for tracked_structure in tracked_structures:
            if cancellation_check is not None:
                cancellation_check()
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
            touched_type_ids.update(type_ids)
            for type_id in type_ids:
                if cancellation_check is not None:
                    cancellation_check()
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
            structure_ids=tuple(
                tracked_structure.structure_id
                for tracked_structure in tracked_structures
                if tracked_structure.structure_id is not None
            ),
            type_ids=tuple(sorted(touched_type_ids)),
            records_processed=snapshot_count + delta_count + demand_period_count,
        )

    def _refresh_market_prices_for_region(
        self,
        session: Session,
        *,
        region_id: int,
        type_ids: list[int],
        cancellation_check: Callable[[], None] | None = None,
    ) -> int:
        if not type_ids:
            return 0

        location_ids = session.scalars(select(Location.id).where(Location.region_id == region_id)).all()
        if not location_ids:
            return 0

        service = MarketPricePeriodService()
        refreshed_count = 0
        for period_days in self.SUPPORTED_PERIOD_DAYS:
            for location_id in location_ids:
                for type_id in type_ids:
                    if cancellation_check is not None:
                        cancellation_check()
                    result = service.upsert_from_history(
                        session,
                        location_id=location_id,
                        type_id=type_id,
                        period_days=period_days,
                    )
                    if result.row is not None:
                        refreshed_count += 1
        return refreshed_count

    def _refresh_market_demand_for_locations(
        self,
        session: Session,
        *,
        location_ids: list[int],
        type_ids: list[int],
        period_days_options: tuple[int, ...] | None = None,
        cancellation_check: Callable[[], None] | None = None,
    ) -> int:
        if not location_ids or not type_ids:
            return 0

        service = MarketDemandResolutionService()
        refreshed_count = 0
        for period_days in period_days_options or self.SUPPORTED_PERIOD_DAYS:
            for location_id in location_ids:
                for type_id in type_ids:
                    if cancellation_check is not None:
                        cancellation_check()
                    result = service.upsert_for_location(
                        session,
                        location_id=location_id,
                        type_id=type_id,
                        period_days=period_days,
                    )
                    if result.row is not None:
                        refreshed_count += 1
        return refreshed_count

    def _rebuild_opportunities(
        self,
        session: Session,
        period_days_options: tuple[int, ...] | None = None,
        cancellation_check: Callable[[], None] | None = None,
    ) -> tuple[int, int]:
        rebuild_demand_rows: list[MarketDemandResolved] = list(
            session.scalars(
                select(MarketDemandResolved).order_by(
                    MarketDemandResolved.location_id.asc(),
                    MarketDemandResolved.period_days.asc(),
                    MarketDemandResolved.type_id.asc(),
                )
            ).all()
        )
        if period_days_options is not None:
            rebuild_demand_rows = [row for row in rebuild_demand_rows if row.period_days in period_days_options]
        if not rebuild_demand_rows:
            return (0, 0)

        scope_count = 0
        generated_count = 0
        grouped_demands: dict[tuple[int, int], list[MarketDemandResolved]] = {}
        for row in rebuild_demand_rows:
            grouped_demands.setdefault((row.location_id, row.period_days), []).append(row)

        for (target_location_id, period_days), rows in grouped_demands.items():
            if cancellation_check is not None:
                cancellation_check()
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

        return (generated_count, scope_count)

    def _all_regions(self, session: Session, *, debug_enabled: bool = False) -> list[Region]:
        regions = list(
            session.scalars(
                select(Region).order_by(Region.region_id.asc())
            ).all()
        )
        if debug_enabled:
            return regions[: self.DEBUG_REGION_LIMIT]
        return regions

    def _history_sync_items(self, session: Session, *, region_ids: list[int]) -> list[Item]:
        if not region_ids:
            return []

        item_ids = set(
            session.scalars(
                select(EsiMarketOrder.type_id).where(EsiMarketOrder.region_id.in_(region_ids)).distinct()
            ).all()
        )
        target_location_ids = list(
            session.scalars(
                select(Location.id).where(Location.location_type == "npc_station")
            ).all()
        )
        if target_location_ids:
            item_ids.update(
                session.scalars(
                    select(MarketDemandResolved.type_id)
                    .where(MarketDemandResolved.location_id.in_(target_location_ids))
                    .distinct()
                ).all()
            )
        if not item_ids:
            return []

        return list(
            session.scalars(select(Item).where(Item.id.in_(item_ids)).order_by(Item.type_id.asc())).all()
        )

    def _check_for_cancellation(self, session: Session, job_id: int) -> None:
        if _PROCESS_CANCELLATION_EVENT.is_set():
            self._mark_job_cancelling(session, job_id, "Cancelling due to process shutdown signal.")
            raise JobCancelledError("Cancelled due to process shutdown signal.")

        probe_session = self.session_factory()
        try:
            job_run = probe_session.get(SyncJobRun, job_id)
            if job_run is not None and job_run.status in {"cancelling", "cancelled"}:
                raise JobCancelledError(job_run.message or f"Cancelled {job_run.job_type}.")
        finally:
            if probe_session is not session:
                probe_session.close()

    def _mark_job_cancelling(self, session: Session, job_id: int, message: str) -> None:
        job_run = session.get(SyncJobRun, job_id)
        if job_run is None or job_run.finished_at is not None:
            return
        def mark_cancelling() -> None:
            refreshed_job = session.get(SyncJobRun, job_id)
            if refreshed_job is None or refreshed_job.finished_at is not None:
                return
            refreshed_job.status = "cancelling"
            refreshed_job.message = message

        mark_cancelling()
        session.commit()

    def _update_job_progress(
        self,
        session: Session,
        job_id: int,
        *,
        progress_phase: str | None,
        progress_current: int | None,
        progress_total: int | None,
        progress_unit: str | None,
        message: str | None,
    ) -> None:
        def apply_progress() -> None:
            job_run = session.get(SyncJobRun, job_id)
            if job_run is None or job_run.finished_at is not None:
                return
            job_run.progress_phase = progress_phase
            job_run.progress_current = progress_current
            job_run.progress_total = progress_total
            job_run.progress_unit = progress_unit
            job_run.message = message

        apply_progress()
        session.commit()

    def _to_job_response(self, job_run: SyncJobRun) -> SyncJobRunResponse:
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
            progress_phase=job_run.progress_phase,
            progress_current=job_run.progress_current,
            progress_total=job_run.progress_total,
            progress_unit=job_run.progress_unit,
            message=job_run.message,
            error_details=job_run.error_details,
        )

    def _finalize_stale_cancelling_jobs(self, session: Session) -> None:
        stale_before = datetime.now(UTC) - timedelta(minutes=self.STALE_CANCELLING_JOB_MINUTES)
        stale_jobs = list(
            session.scalars(
                select(SyncJobRun)
                .where(
                    SyncJobRun.status == "cancelling",
                    SyncJobRun.finished_at.is_(None),
                    SyncJobRun.started_at <= stale_before,
                )
                .order_by(SyncJobRun.started_at.asc(), SyncJobRun.id.asc())
            ).all()
        )
        if not stale_jobs:
            return

        finished_at = datetime.now(UTC)
        for job_run in stale_jobs:
            job_run.status = "cancelled"
            job_run.finished_at = finished_at
            job_run.duration_ms = max(int((finished_at - self._ensure_utc(job_run.started_at)).total_seconds() * 1000), 0)
            job_run.message = job_run.message or f"Cancelled {job_run.job_type}."
            if "stale" not in (job_run.message or "").lower():
                job_run.message = f"{job_run.message} Finalized stale cancellation request."

        session.commit()

    def get_fallback_status(self) -> list[FallbackDiagnostic]:
        def load_diagnostics() -> list[FallbackDiagnostic]:
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
                        select(Location.id).where(
                            Location.location_id.in_([row.structure_id for row in tracked_structures])
                        )
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
                    location = session.scalar(select(Location).where(Location.location_id == tracked_structure.structure_id))
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

        return load_diagnostics()


@dataclass(frozen=True)
class StructureSnapshotSyncResult:
    structure_count: int
    snapshot_count: int
    delta_count: int
    demand_period_count: int
    structure_ids: tuple[int, ...]
    type_ids: tuple[int, ...]
    records_processed: int
