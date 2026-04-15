from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import logging
from pathlib import Path
import resource
import signal
import tempfile

import httpx
from threading import Event, Lock, Thread, current_thread, main_thread
from time import perf_counter
from typing import Any, Callable, Protocol, Sequence, TypeVar, cast

from sqlalchemy import and_, delete, distinct, func, select
from sqlalchemy.orm import Session

from app.api.schemas.sync import (
    ClearSyncDataResponse,
    FallbackDiagnostic,
    SyncJobRunResponse,
    SyncJobStageRunResponse,
    SyncStatusCard,
)
from app.db.session import SessionLocal
from app.models.all_models import (
    AdamMarketPriceHistoryDaily,
    AdamMarketPriceSyncState,
    AdamMarketOrdersTradeRaw,
    AdamNpcDemandSyncState,
    BulkImportCursor,
    BulkImportFile,
    CharacterAccessibleStructure,
    CharacterAsset,
    CharacterOrder,
    EsiCharacter,
    EsiCharacterSyncState,
    EsiHistoryDaily,
    EsiMarketOrder,
    EveRefHistorySyncState,
    Item,
    Location,
    MarketDemandResolved,
    MarketPricePeriod,
    NpcStationDemandPeriod,
    OpportunityItem,
    OpportunitySourceSummary,
    Region,
    Station,
    StructureDemandPeriod,
    StructureOrderDelta,
    StructureSnapshotOrder,
    StructureSnapshot,
    SyncJobStageRun,
    SyncJobRun,
    System,
    TrackedStructure,
    WorkerHeartbeat,
)
from app.repositories.seed_data import FoundationSeedSource, StationSeed
from app.services.adam4eve.client import Adam4EveClient, AdamMarketOrdersExport, AdamStationPriceHistoryExport
from app.services.adam4eve.history_ingestion import (
    AdamStationHistoryWorksetEntry,
    AdamStationPriceHistoryIngestionService,
    AdamStationPriceHistoryRecord,
)
from app.services.adam4eve.ingestion import AdamMarketOrdersIngestionService
from app.services.demand.market_demand import MarketDemandResolutionService
from app.services.everef.client import download_history_file, fetch_totals_json, get_available_dates
from app.services.everef.history_ingestion import EveRefHistoryIngestionService
from app.services.esi.client import EsiClient, EsiRegionalOrderRecord
from app.services.esi.orders_ingestion import EsiRegionOrderBatch, EsiRegionalOrderIngestionService
from app.services.opportunities.generation import OpportunityGenerationService
from app.services.pricing.market_price_periods import MarketPricePeriodService
from app.services.settings_service import SettingsService
from app.services.structures.demand_periods import StructureDemandPeriodService
from app.services.structures.snapshots import StructureOrderInput, StructureSnapshotService
from app.services.sync.bulk_imports import BulkImportService, CachedImportFile
from app.services.sync.foundation_import import CcpSdeClient, FoundationImportService

logger = logging.getLogger(__name__)


class FoundationImportCapableClient(Protocol):
    def build_seed_source(self) -> FoundationSeedSource: ...


class UniverseCapableEsiClient(Protocol):
    def fetch_station(self, station_id: int) -> StationSeed: ...

    def fetch_regional_orders(self, region_id: int) -> list[EsiRegionalOrderRecord]: ...


class AdamDemandCapableClient(Protocol):
    def get_headers(self) -> dict[str, str]: ...

    def resolve_latest_market_orders_export(self) -> AdamMarketOrdersExport: ...

    def resolve_market_orders_exports(
        self,
        *,
        since_date: date | None,
    ) -> list[AdamMarketOrdersExport]: ...

    def cache_market_orders_export(
        self,
        *,
        export_path: str,
        session: Session | None = None,
    ): ...

    def cache_market_orders_exports(
        self,
        *,
        since_date: date | None,
        session: Session | None = None,
    ) -> list[tuple[AdamMarketOrdersExport, CachedImportFile]]: ...

    def fetch_regional_price_history(
        self,
        region_id: int,
        type_ids: list[int],
        *,
        location_ids: list[int],
        since_date: date | None = None,
        session: Session | None = None,
    ) -> list[AdamStationPriceHistoryRecord]: ...

    def resolve_station_price_history_exports(
        self,
        *,
        since_date: date | None,
    ) -> list[AdamStationPriceHistoryExport]: ...

    def cache_station_price_history_exports(
        self,
        *,
        since_date: date | None,
        session: Session | None = None,
    ) -> list[tuple[AdamStationPriceHistoryExport, CachedImportFile]]: ...


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
T = TypeVar("T")


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
    STALE_CANCELLING_JOB_MINUTES = 2
    STATUS_CARD_DEFINITIONS: tuple[tuple[str, str], ...] = (
        ("foundation_import_sync", "Foundation universe sync"),
        ("adam4eve_sync", "Adam4EVE sync"),
        ("esi_market_orders_sync", "ESI market orders sync"),
        ("everef_history_sync", "EVE Ref history sync"),
        ("structure_snapshot_sync", "Structure snapshot sync"),
        ("character_sync", "Character sync"),
        ("opportunity_rebuild", "Opportunity rebuild"),
    )
    WORKER_HEARTBEAT_STALE_MINUTES = 15
    DEBUG_REGION_LIMIT = 1
    MARKET_PRICE_PERIODS: tuple[int, ...] = (3, 7, 14, 30)
    IMPORT_KIND_ADAM_DEMAND = "adam4eve_npc_demand"
    IMPORT_KIND_ADAM_PRICE_HISTORY = "adam_market_price_history_daily"
    IMPORT_SCOPE_GLOBAL = "global"
    ADAM_HISTORY_MAX_LOOKBACK_DAYS = 14
    PRE_REBUILD_ESI_MARKET_ORDER_MAX_AGE_MINUTES = 10
    OPPORTUNITY_REBUILD_MAX_RUNTIME = timedelta(minutes=30)
    PROGRESS_RATE_UPDATE_INTERVAL_SECONDS = 1.0

    @staticmethod
    def _current_rss_mb() -> float | None:
        status_path = Path("/proc/self/status")
        if not status_path.exists():
            return None
        for line in status_path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("VmRSS:"):
                continue
            parts = line.split()
            if len(parts) < 2:
                return None
            try:
                return int(parts[1]) / 1024.0
            except ValueError:
                return None
        return None

    @staticmethod
    def _peak_rss_mb() -> float | None:
        peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if peak_kb <= 0:
            return None
        return peak_kb / 1024.0

    @classmethod
    def _log_profile_checkpoint(cls, label: str, *, started_at: float, **metrics: object) -> None:
        current_rss_mb = cls._current_rss_mb()
        peak_rss_mb = cls._peak_rss_mb()
        extra_metrics = " ".join(f"{key}={value}" for key, value in metrics.items())
        logger.info(
            "adam4eve profile phase=%s elapsed_s=%.3f current_rss_mb=%s peak_rss_mb=%s%s",
            label,
            perf_counter() - started_at,
            f"{current_rss_mb:.1f}" if current_rss_mb is not None else "-",
            f"{peak_rss_mb:.1f}" if peak_rss_mb is not None else "-",
            f" {extra_metrics}" if extra_metrics else "",
        )

    @classmethod
    def _log_job_stage_checkpoint(
        cls,
        job_type: str,
        stage: str,
        *,
        started_at: float,
        **metrics: object,
    ) -> None:
        current_rss_mb = cls._current_rss_mb()
        peak_rss_mb = cls._peak_rss_mb()
        extra_metrics = " ".join(f"{key}={value}" for key, value in metrics.items())
        logger.info(
            "sync timing job_type=%s stage=%s elapsed_s=%.3f current_rss_mb=%s peak_rss_mb=%s%s",
            job_type,
            stage,
            perf_counter() - started_at,
            f"{current_rss_mb:.1f}" if current_rss_mb is not None else "-",
            f"{peak_rss_mb:.1f}" if peak_rss_mb is not None else "-",
            f" {extra_metrics}" if extra_metrics else "",
        )

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        adam_client: AdamDemandCapableClient | None = None,
        esi_client: UniverseCapableEsiClient | None = None,
        foundation_client: FoundationImportCapableClient | None = None,
        structure_snapshot_client: StructureSnapshotCapableClient | None = None,
    ) -> None:
        register_cancellation_signal_handlers()
        self.session_factory = session_factory
        self.adam_client = adam_client or Adam4EveClient()
        self.esi_client = esi_client or EsiClient()
        self.foundation_client = foundation_client or CcpSdeClient()
        self.structure_snapshot_client = structure_snapshot_client
        self.bulk_imports = BulkImportService()

    @staticmethod
    def _ensure_utc(timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)

    @staticmethod
    def _sanitize_stage_metrics(metrics: dict[str, object] | None) -> dict[str, object]:
        if not metrics:
            return {}
        return {key: value for key, value in metrics.items() if value is not None}

    def _job_stage_rows(self, session: Session, job_id: int) -> list[SyncJobStageRun]:
        return list(
            session.scalars(
                select(SyncJobStageRun)
                .where(SyncJobStageRun.job_run_id == job_id)
                .order_by(SyncJobStageRun.started_at.asc(), SyncJobStageRun.id.asc())
            ).all()
        )

    def _stage_response(self, stage_run: SyncJobStageRun) -> SyncJobStageRunResponse:
        return SyncJobStageRunResponse(
            id=stage_run.id,
            stage_key=stage_run.stage_key,
            status=stage_run.status,
            started_at=stage_run.started_at,
            finished_at=stage_run.finished_at,
            duration_ms=stage_run.duration_ms,
            metrics=stage_run.metrics or {},
            error_details=stage_run.error_details,
        )

    def _start_job_stage(
        self,
        session: Session,
        *,
        job_id: int,
        stage_key: str,
        metrics: dict[str, object] | None = None,
    ) -> SyncJobStageRun:
        stage_run = SyncJobStageRun(
            job_run_id=job_id,
            stage_key=stage_key,
            status="running",
            started_at=datetime.now(UTC),
            metrics=self._sanitize_stage_metrics(metrics),
        )
        session.add(stage_run)
        session.flush()
        session.commit()
        return stage_run

    def _finish_job_stage(
        self,
        session: Session,
        *,
        stage_run_id: int,
        status: str,
        stage_started_at: float,
        metrics: dict[str, object] | None = None,
        error_details: str | None = None,
    ) -> None:
        stage_run = session.get(SyncJobStageRun, stage_run_id)
        if stage_run is None or stage_run.finished_at is not None:
            return
        stage_run.status = status
        stage_run.finished_at = datetime.now(UTC)
        stage_run.duration_ms = max(int((perf_counter() - stage_started_at) * 1000), 0)
        if metrics:
            merged_metrics = dict(stage_run.metrics or {})
            merged_metrics.update(self._sanitize_stage_metrics(metrics))
            stage_run.metrics = merged_metrics
        if error_details is not None:
            stage_run.error_details = error_details
        session.commit()

    def _record_completed_job_stage(
        self,
        session: Session,
        *,
        job_id: int,
        stage_key: str,
        stage_started_at: float,
        metrics: dict[str, object] | None = None,
        status: str = "success",
        error_details: str | None = None,
    ) -> None:
        stage_run = self._start_job_stage(session, job_id=job_id, stage_key=stage_key)
        self._finish_job_stage(
            session,
            stage_run_id=stage_run.id,
            status=status,
            stage_started_at=stage_started_at,
            metrics=metrics,
            error_details=error_details,
        )

    def _run_job_stage(
        self,
        session: Session,
        *,
        job_id: int,
        stage_key: str,
        func: Callable[[], T],
        initial_metrics: dict[str, object] | None = None,
        success_metrics: Callable[[T], dict[str, object]] | None = None,
    ) -> T:
        stage_run = self._start_job_stage(session, job_id=job_id, stage_key=stage_key, metrics=initial_metrics)
        stage_started_at = perf_counter()
        try:
            result = func()
        except JobCancelledError as exc:
            session.rollback()
            self._finish_job_stage(
                session,
                stage_run_id=stage_run.id,
                status="cancelled",
                stage_started_at=stage_started_at,
                error_details=str(exc),
            )
            raise
        except Exception as exc:
            session.rollback()
            self._finish_job_stage(
                session,
                stage_run_id=stage_run.id,
                status="failed",
                stage_started_at=stage_started_at,
                error_details=str(exc),
            )
            raise

        self._finish_job_stage(
            session,
            stage_run_id=stage_run.id,
            status="success",
            stage_started_at=stage_started_at,
            metrics=success_metrics(result) if success_metrics is not None else None,
        )
        return result

    @staticmethod
    def _rate_message(
        *,
        verb: str,
        current: int,
        total: int,
        unit: str,
        started_at: float,
    ) -> str:
        elapsed_seconds = max(perf_counter() - started_at, 1e-6)
        rate = current / elapsed_seconds
        return (
            f"{verb} {current} / {total} {unit} "
            f"at {rate:.1f} {unit}/s."
        )

    def _finalize_open_job_stages(self, session: Session, *, job_id: int, status: str, error_details: str | None) -> None:
        open_stages = list(
            session.scalars(
                select(SyncJobStageRun)
                .where(
                    SyncJobStageRun.job_run_id == job_id,
                    SyncJobStageRun.finished_at.is_(None),
                )
                .order_by(SyncJobStageRun.started_at.asc(), SyncJobStageRun.id.asc())
            ).all()
        )
        if not open_stages:
            return
        finished_at = datetime.now(UTC)
        for stage_run in open_stages:
            stage_run.status = status
            stage_run.finished_at = finished_at
            if stage_run.error_details is None:
                stage_run.error_details = error_details
            if stage_run.duration_ms is None:
                stage_run.duration_ms = max(
                    int((finished_at - self._ensure_utc(stage_run.started_at)).total_seconds() * 1000),
                    0,
                )
        session.commit()

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
                cards.append(self._build_esi_rate_limit_card())
                return cards
            finally:
                session.close()

        return load_status()

    @staticmethod
    def _build_esi_rate_limit_card() -> SyncStatusCard:
        from app.services.esi.client import EsiClient

        state = EsiClient.get_rate_limit_state()
        status = "degraded" if state.should_backoff() else "healthy"
        message = (
            f"Remain: {state.error_limit_remain}, "
            f"Reset: {state.error_limit_reset}s, "
            f"Total requests: {state.total_requests}, "
            f"Cached: {state.cached_responses}, "
            f"Error-limited: {state.error_limited_count}"
        )
        return SyncStatusCard(
            key="esi_rate_limit",
            label="ESI rate limit",
            status=status,
            last_successful_sync=state.last_updated,
            next_scheduled_sync=None,
            recent_error_count=state.error_limited_count,
            active_message=message,
            progress_phase=None,
            progress_current=state.error_limit_remain,
            progress_total=100,
            progress_unit="remaining",
        )

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
                return [self._to_job_response(session, row) for row in rows]
            finally:
                session.close()

        return load_jobs()

    def clear_job_data(self, job_type: str) -> ClearSyncDataResponse:
        session = self.session_factory()
        try:
            records_deleted = 0
            if job_type == "foundation_import_sync":
                records_deleted += self._clear_foundation_data(session)
            elif job_type == "adam4eve_sync":
                records_deleted += self._clear_adam4eve_data(session)
            elif job_type == "esi_market_orders_sync":
                records_deleted += self._clear_esi_market_orders_data(session)
            elif job_type == "everef_history_sync":
                records_deleted += self._clear_everef_history_data(session)
            elif job_type == "structure_snapshot_sync":
                records_deleted += self._clear_structure_snapshot_data(session)
            elif job_type == "character_sync":
                records_deleted += self._clear_character_sync_data(session)
            elif job_type == "opportunity_rebuild":
                records_deleted += self._clear_opportunity_data(session)
            else:
                raise LookupError(f"Clear action for sync job type {job_type!r} was not found.")

            session.commit()
            return ClearSyncDataResponse(
                job_type=job_type,
                records_deleted=records_deleted,
                message=f"Cleared {records_deleted} records for {job_type}.",
            )
        finally:
            session.close()

    def trigger_job(self, job_type: str) -> SyncJobRunResponse:
        now = datetime.now(UTC)
        session = self.session_factory()
        try:
            self._finalize_stale_cancelling_jobs(session)
            active_job = self._get_active_job_run(session, job_type=job_type)
            if active_job is not None:
                return self._to_job_response(session, active_job)
            job_run = self._create_job_run(session, job_type=job_type, started_at=now)
            return self._execute_job(session, job_id=job_run.id, job_type=job_type, started_at=now)
        finally:
            session.close()

    def enqueue_job(self, job_type: str) -> SyncJobRunResponse:
        now = datetime.now(UTC)
        session = self.session_factory()
        try:
            self._finalize_stale_cancelling_jobs(session)
            active_job = self._get_active_job_run(session, job_type=job_type)
            if active_job is not None:
                return self._to_job_response(session, active_job)
            job_run = self._create_job_run(session, job_type=job_type, started_at=now)
            response = self._to_job_response(session, job_run)
        finally:
            session.close()

        Thread(
            target=self._run_job_in_background,
            kwargs={"job_id": response.id, "job_type": job_type, "started_at": now},
            daemon=True,
        ).start()
        return response

    def _run_job_in_background(self, *, job_id: int, job_type: str, started_at: datetime) -> None:
        session = self.session_factory()
        try:
            self._execute_job(session, job_id=job_id, job_type=job_type, started_at=started_at)
        finally:
            session.close()

    def _create_job_run(self, session: Session, *, job_type: str, started_at: datetime) -> SyncJobRun:
        job_run = SyncJobRun(
            job_type=job_type,
            status="running",
            triggered_by="manual",
            started_at=started_at,
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
        return job_run

    @staticmethod
    def _get_active_job_run(session: Session, *, job_type: str) -> SyncJobRun | None:
        return session.scalar(
            select(SyncJobRun)
            .where(
                SyncJobRun.job_type == job_type,
                SyncJobRun.finished_at.is_(None),
                SyncJobRun.status.in_(("running", "cancelling")),
            )
            .order_by(SyncJobRun.started_at.desc(), SyncJobRun.id.desc())
            .limit(1)
        )

    def _execute_job(
        self,
        session: Session,
        *,
        job_id: int,
        job_type: str,
        started_at: datetime,
    ) -> SyncJobRunResponse:
        records_processed = 0
        target_type = "manual"
        target_id: str | None = None
        try:
            records_processed, target_type, target_id, message = self._run_job(
                session,
                job_type=job_type,
                job_id=job_id,
            )
        except JobCancelledError as exc:
            session.rollback()
            persisted_job = session.get(SyncJobRun, job_id)
            if persisted_job is None:
                raise
            self._finalize_open_job_stages(session, job_id=job_id, status="cancelled", error_details=str(exc))
            finished_at = datetime.now(UTC)
            persisted_job.status = "cancelled"
            persisted_job.finished_at = finished_at
            persisted_job.duration_ms = max(int((finished_at - started_at).total_seconds() * 1000), 0)
            persisted_job.records_processed = records_processed
            persisted_job.target_type = target_type
            persisted_job.target_id = target_id
            if persisted_job.progress_total is not None and persisted_job.progress_current is None:
                persisted_job.progress_current = 0
            persisted_job.message = str(exc)
            session.commit()
            return self._to_job_response(session, persisted_job)
        except Exception as exc:
            session.rollback()
            persisted_job = session.get(SyncJobRun, job_id)
            if persisted_job is None:
                raise
            self._finalize_open_job_stages(session, job_id=job_id, status="failed", error_details=str(exc))
            finished_at = datetime.now(UTC)
            persisted_job.status = "failed"
            persisted_job.finished_at = finished_at
            persisted_job.duration_ms = max(int((finished_at - started_at).total_seconds() * 1000), 0)
            persisted_job.records_processed = records_processed
            persisted_job.target_type = target_type
            persisted_job.target_id = target_id
            if persisted_job.progress_total is not None and persisted_job.progress_current is None:
                persisted_job.progress_current = 0
            persisted_job.message = f"Failed {job_type}."
            persisted_job.error_details = str(exc)
            session.commit()
            return self._to_job_response(session, persisted_job)

        persisted_job = session.get(SyncJobRun, job_id)
        if persisted_job is None:
            raise LookupError(f"Sync job {job_id} disappeared during execution.")
        self._finalize_open_job_stages(session, job_id=job_id, status="success", error_details=None)
        finished_at = datetime.now(UTC)
        persisted_job.status = "success"
        persisted_job.finished_at = finished_at
        persisted_job.duration_ms = max(int((finished_at - started_at).total_seconds() * 1000), 0)
        persisted_job.records_processed = records_processed
        persisted_job.target_type = target_type
        persisted_job.target_id = target_id
        if persisted_job.progress_total is not None:
            persisted_job.progress_current = persisted_job.progress_total
        persisted_job.progress_phase = "Completed"
        persisted_job.message = message
        persisted_job.error_details = None
        session.commit()
        return self._to_job_response(session, persisted_job)

    def cancel_job(self, job_id: int) -> SyncJobRunResponse:
        session = self.session_factory()
        try:
            self._finalize_stale_cancelling_jobs(session)
            job_run = session.get(SyncJobRun, job_id)
            if job_run is None:
                raise LookupError(f"Sync job {job_id} was not found.")
            if job_run.finished_at is not None or job_run.status in {"success", "failed", "cancelled"}:
                return self._to_job_response(session, job_run)

            def mark_cancelling() -> None:
                refreshed_job = session.get(SyncJobRun, job_id)
                if refreshed_job is None:
                    raise LookupError(f"Sync job {job_id} was not found.")
                refreshed_job.status = "cancelling"
                refreshed_job.message = f"Cancelling {refreshed_job.job_type}."

            mark_cancelling()
            session.commit()
            return self._to_job_response(session, job_run)
        finally:
            session.close()

    @staticmethod
    def _delete_rows(session: Session, statement) -> int:
        result = session.execute(statement)
        rowcount = getattr(result, "rowcount", 0)
        return int(rowcount or 0)

    def _clear_foundation_data(self, session: Session) -> int:
        records_deleted = 0
        records_deleted += self._clear_opportunity_data(session)
        records_deleted += self._clear_structure_snapshot_data(session)
        records_deleted += self._clear_adam4eve_data(session)
        records_deleted += self._clear_esi_market_orders_data(session)
        records_deleted += self._delete_rows(session, delete(TrackedStructure))
        records_deleted += self._delete_rows(session, delete(Location))
        records_deleted += self._delete_rows(session, delete(Station))
        records_deleted += self._delete_rows(session, delete(System))
        records_deleted += self._delete_rows(session, delete(Item))
        records_deleted += self._delete_rows(session, delete(Region))
        return records_deleted

    def _clear_adam4eve_data(self, session: Session) -> int:
        npc_location_ids = select(Location.id).where(Location.location_type == "npc_station")
        records_deleted = 0
        records_deleted += self._clear_opportunity_data(session)
        records_deleted += self._delete_rows(
            session,
            delete(MarketDemandResolved).where(MarketDemandResolved.location_id.in_(npc_location_ids)),
        )
        records_deleted += self._delete_rows(
            session,
            delete(MarketPricePeriod).where(MarketPricePeriod.location_id.in_(npc_location_ids)),
        )
        records_deleted += self._delete_rows(session, delete(AdamMarketOrdersTradeRaw))
        records_deleted += self._delete_rows(session, delete(AdamNpcDemandSyncState))
        records_deleted += self._delete_rows(session, delete(AdamMarketPriceHistoryDaily))
        records_deleted += self._delete_rows(session, delete(AdamMarketPriceSyncState))
        records_deleted += self._delete_rows(
            session,
            delete(BulkImportCursor).where(
                BulkImportCursor.import_kind.in_([self.IMPORT_KIND_ADAM_DEMAND, self.IMPORT_KIND_ADAM_PRICE_HISTORY])
            ),
        )
        records_deleted += self._delete_rows(
            session,
            delete(BulkImportFile).where(
                BulkImportFile.import_kind.in_([self.IMPORT_KIND_ADAM_DEMAND, self.IMPORT_KIND_ADAM_PRICE_HISTORY])
            ),
        )
        return records_deleted

    def _clear_esi_market_orders_data(self, session: Session) -> int:
        records_deleted = 0
        records_deleted += self._clear_opportunity_data(session)
        records_deleted += self._delete_rows(session, delete(EsiMarketOrder))
        return records_deleted

    def _clear_everef_history_data(self, session: Session) -> int:
        records_deleted = 0
        records_deleted += self._clear_opportunity_data(session)
        records_deleted += self._delete_rows(session, delete(EsiHistoryDaily))
        records_deleted += self._delete_rows(session, delete(EveRefHistorySyncState))
        return records_deleted

    def _clear_structure_snapshot_data(self, session: Session) -> int:
        structure_location_ids = select(Location.id).where(Location.location_type == "structure")
        records_deleted = 0
        records_deleted += self._clear_opportunity_data(session)
        records_deleted += self._delete_rows(
            session,
            delete(MarketDemandResolved).where(MarketDemandResolved.location_id.in_(structure_location_ids)),
        )
        records_deleted += self._delete_rows(session, delete(StructureDemandPeriod))
        records_deleted += self._delete_rows(session, delete(StructureOrderDelta))
        records_deleted += self._delete_rows(session, delete(StructureSnapshotOrder))
        records_deleted += self._delete_rows(session, delete(StructureSnapshot))
        return records_deleted

    def _clear_character_sync_data(self, session: Session) -> int:
        records_deleted = 0
        records_deleted += self._clear_opportunity_data(session)
        records_deleted += self._delete_rows(session, delete(CharacterOrder))
        records_deleted += self._delete_rows(session, delete(CharacterAsset))
        records_deleted += self._delete_rows(session, delete(CharacterAccessibleStructure))
        records_deleted += self._delete_rows(session, delete(EsiCharacterSyncState))
        return records_deleted

    def _clear_opportunity_data(self, session: Session) -> int:
        records_deleted = 0
        records_deleted += self._delete_rows(session, delete(OpportunityItem))
        records_deleted += self._delete_rows(session, delete(OpportunitySourceSummary))
        return records_deleted

    def _run_job(self, session: Session, *, job_type: str, job_id: int) -> tuple[int, str, str | None, str]:
        records_processed = 0
        target_type = "manual"
        target_id: str | None = None
        message = f"Queued {job_type}."
        settings = SettingsService().get_settings_for_session(session)
        debug_enabled = settings.debug_enabled
        analysis_period_days = max(settings.default_analysis_period_days, 1)

        if job_type == "foundation_import_sync":
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
                sync_started_at = perf_counter()
                internal_location_id_by_eve_id = {location.location_id: location.id for location in npc_locations}
                internal_item_id_by_type_id = {item.type_id: item.id for item in items}
                self._check_for_cancellation(session, job_id)
                phase_started_at = perf_counter()
                latest_demand_export = self.adam_client.resolve_latest_market_orders_export()
                self._log_profile_checkpoint(
                    "resolve_latest_demand_export",
                    started_at=phase_started_at,
                    export_key=latest_demand_export.export_key,
                )
                demand_since_date = self._adam_demand_sync_since_date(
                    session,
                    lookback_days=min(max(analysis_period_days, 1), self.ADAM_HISTORY_MAX_LOOKBACK_DAYS),
                )
                phase_started_at = perf_counter()
                demand_regions = self._adam_demand_regions(
                    session,
                    locations=npc_locations,
                    latest_export=latest_demand_export,
                    required_since_date=demand_since_date,
                )
                self._log_profile_checkpoint(
                    "resolve_demand_regions",
                    started_at=phase_started_at,
                    region_count=len(demand_regions),
                    since_date=demand_since_date.isoformat() if demand_since_date is not None else "-",
                )
                phase_started_at = perf_counter()
                cached_demand_exports = (
                    self.adam_client.cache_market_orders_exports(
                        since_date=demand_since_date,
                        session=session,
                    )
                    if demand_regions
                    else []
                )
                self._log_profile_checkpoint(
                    "cache_demand_exports",
                    started_at=phase_started_at,
                    export_count=len(cached_demand_exports),
                    downloaded_count=sum(1 for _, cached_file in cached_demand_exports if cached_file.downloaded),
                )
                phase_started_at = perf_counter()
                stage_import_result = AdamMarketOrdersIngestionService().ingest_market_orders_exports(
                    session,
                    csv_file_paths=[cached_file.path for _, cached_file in cached_demand_exports],
                )
                self._log_profile_checkpoint(
                    "ingest_demand_exports",
                    started_at=phase_started_at,
                    records_processed=stage_import_result.records_processed,
                )
                if demand_regions:
                    phase_started_at = perf_counter()
                    demand_refresh_keys = self._adam_demand_refresh_keys(
                        session,
                        locations=[location for location in npc_locations if location.region_id in demand_regions],
                        items=items,
                        internal_location_id_by_eve_id=internal_location_id_by_eve_id,
                        internal_item_id_by_type_id=internal_item_id_by_type_id,
                    )
                    self._record_adam_demand_region_check(
                        session,
                        region_ids=sorted(demand_regions),
                        exports=[export for export, _ in cached_demand_exports] or [latest_demand_export],
                    )
                    self._log_profile_checkpoint(
                        "build_demand_refresh_keys",
                        started_at=phase_started_at,
                        key_count=len(demand_refresh_keys),
                    )
                else:
                    demand_refresh_keys = []
                phase_started_at = perf_counter()
                history_processed, history_created, history_updated, price_count = self._sync_adam_regional_price_history(
                    session,
                    job_id=job_id,
                    regions=self._all_regions(session, debug_enabled=debug_enabled),
                    lookback_days=min(max(analysis_period_days, 1), self.ADAM_HISTORY_MAX_LOOKBACK_DAYS),
                )
                self._log_profile_checkpoint(
                    "sync_station_price_history",
                    started_at=phase_started_at,
                    history_processed=history_processed,
                    history_created=history_created,
                    history_updated=history_updated,
                    price_count=price_count,
                )
                phase_started_at = perf_counter()
                derived_count = self._refresh_market_demand_for_keys(
                    session,
                    demand_keys=demand_refresh_keys,
                    period_days=analysis_period_days,
                    cancellation_check=lambda: self._check_for_cancellation(session, job_id),
                )
                self._log_profile_checkpoint(
                    "refresh_market_demand",
                    started_at=phase_started_at,
                    demand_key_count=len(demand_refresh_keys),
                    derived_count=derived_count,
                )
                phase_started_at = perf_counter()
                generated_count, scope_count = self._rebuild_opportunities(
                    session,
                    job_id=job_id,
                    period_days=analysis_period_days,
                    cancellation_check=lambda: self._check_for_cancellation(session, job_id),
                )
                self._log_profile_checkpoint(
                    "rebuild_opportunities",
                    started_at=phase_started_at,
                    generated_count=generated_count,
                    scope_count=scope_count,
                )
                totals_now = self._adam4eve_sync_totals(session, period_days=analysis_period_days)
                self._log_profile_checkpoint(
                    "adam4eve_sync_total",
                    started_at=sync_started_at,
                    npc_location_count=len(npc_locations),
                    item_count=len(items),
                )
                records_processed = (
                    stage_import_result.records_processed
                    + history_processed
                    + derived_count
                    + price_count
                    + generated_count
                )
                target_type = "locations"
                target_id = str(len(npc_locations))
                message = (
                    "Synced Adam4EVE raw staging and station price history "
                    f"({stage_import_result.records_processed} raw rows staged, "
                    f"{history_created} history rows created this run, {history_updated} history rows updated this run, "
                    f"{derived_count} resolved demand rows refreshed this run, {price_count} price periods refreshed this run, "
                    f"{generated_count} opportunity items generated across {scope_count} scopes this run; "
                    f"totals now: {totals_now['history_rows']} history rows, "
                    f"{totals_now['resolved_demand_rows']} resolved demand rows for {analysis_period_days}d, "
                    f"{totals_now['price_period_rows']} price-period rows, "
                    f"{totals_now['opportunity_item_rows']} opportunity items for {analysis_period_days}d)."
                )
        elif job_type == "esi_market_orders_sync":
            records_processed, target_type, target_id, message = self._sync_esi_market_orders(
                session,
                job_id=job_id,
                debug_enabled=debug_enabled,
                cancellation_check=lambda: self._check_for_cancellation(session, job_id),
            )
        elif job_type == "everef_history_sync":
            records_processed, target_type, target_id, message = self._sync_everef_history(
                session,
                job_id=job_id,
                cancellation_check=lambda: self._check_for_cancellation(session, job_id),
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

                character_service = CharacterService(
                    session_factory=self.session_factory,
                    esi_client=cast(Any, self.esi_client),
                )
                synced_count = 0
                discovered_count = 0
                for character_id in character_ids:
                    self._check_for_cancellation(session, job_id)
                    discovered_structures = character_service.sync_character(character_id)
                    synced_count += 1
                    discovered_count += len(discovered_structures)

                self._clear_opportunity_data(session)

                records_processed = discovered_count
                target_type = "characters"
                target_id = str(synced_count)
                message = (
                    "Synced characters "
                    f"({synced_count} characters, {discovered_count} accessible structures refreshed)."
                )
        elif job_type == "opportunity_rebuild":
            esi_order_sync_message: str | None = None
            rebuild_started_at = perf_counter()
            if self._should_refresh_esi_market_orders_before_rebuild(session):
                stage_started_at = perf_counter()
                _, _, _, esi_order_sync_message = self._run_job_stage(
                    session,
                    job_id=job_id,
                    stage_key="refresh_esi_market_orders",
                    func=lambda: self._sync_esi_market_orders(
                        session,
                        job_id=job_id,
                        debug_enabled=debug_enabled,
                        cancellation_check=lambda: self._check_for_cancellation(session, job_id),
                    ),
                    success_metrics=lambda result: {"records_processed": result[0], "region_count": result[2]},
                )
                self._log_job_stage_checkpoint(
                    "opportunity_rebuild",
                    "refresh_esi_market_orders",
                    started_at=stage_started_at,
                )
            else:
                skipped_started_at = perf_counter()
                self._record_completed_job_stage(
                    session,
                    job_id=job_id,
                    stage_key="refresh_esi_market_orders",
                    stage_started_at=skipped_started_at,
                    status="skipped",
                    metrics={"reason": "fresh_esi_market_orders_sync"},
                )
                self._log_job_stage_checkpoint(
                    "opportunity_rebuild",
                    "refresh_esi_market_orders_skipped",
                    started_at=skipped_started_at,
                )
            stage_started_at = perf_counter()
            generated_count, scope_count = self._run_job_stage(
                session,
                job_id=job_id,
                stage_key="rebuild_scopes",
                func=lambda: self._rebuild_opportunities(
                    session,
                    job_id=job_id,
                    period_days=analysis_period_days,
                    cancellation_check=lambda: self._check_for_cancellation(session, job_id),
                ),
                success_metrics=lambda result: {"generated_count": result[0], "scope_count": result[1]},
            )
            self._log_job_stage_checkpoint(
                "opportunity_rebuild",
                "rebuild_scopes",
                started_at=stage_started_at,
                generated_count=generated_count,
                scope_count=scope_count,
            )
            self._log_job_stage_checkpoint(
                "opportunity_rebuild",
                "total",
                started_at=rebuild_started_at,
                generated_count=generated_count,
                scope_count=scope_count,
            )
            if generated_count == 0 and scope_count == 0:
                message = "Skipped opportunity rebuild because computed demand rows are missing."
            else:
                records_processed = generated_count
                target_type = "targets"
                target_id = str(scope_count)
                message = f"Rebuilt opportunities ({generated_count} item rows across {scope_count} target scopes)."
                if esi_order_sync_message is not None:
                    message = f"{esi_order_sync_message} {message}"
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
                period_days=analysis_period_days,
                cancellation_check=lambda: self._check_for_cancellation(session, job_id),
            )
            generated_count, scope_count = self._rebuild_opportunities(
                session,
                job_id=job_id,
                period_days=analysis_period_days,
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

    def _sync_esi_market_orders(
        self,
        session: Session,
        *,
        job_id: int,
        debug_enabled: bool,
        cancellation_check: Callable[[], None] | None = None,
    ) -> tuple[int, str, str | None, str]:
        universe_client = cast(UniverseCapableEsiClient, self.esi_client)
        sync_started_at = perf_counter()
        settings = SettingsService(session_factory=lambda: session).get_settings_for_session(session)
        target_eve_ids = settings.target_market_location_ids or []
        desired_region_ids: set[int] = set(settings.source_region_ids or [])
        if target_eve_ids:
            desired_region_ids.update(
                region_id
                for region_id in session.scalars(
                    select(Region.region_id)
                    .join(Location, Location.region_id == Region.id)
                    .where(Location.location_id.in_(target_eve_ids))
                ).all()
                if region_id is not None
            )
        regions = self._all_regions(session, debug_enabled=debug_enabled)
        if desired_region_ids:
            regions = [region for region in regions if region.region_id in desired_region_ids]
        if not regions:
            return (0, "manual", None, "Skipped ESI market orders sync because imported regions are missing.")

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
        download_started_at = perf_counter()
        for region_index, region in enumerate(regions, start=1):
            if cancellation_check is not None:
                cancellation_check()
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
        self._log_job_stage_checkpoint(
            "opportunity_rebuild",
            "download_esi_market_order_batches",
            started_at=download_started_at,
            region_count=len(regions),
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
        last_ingest_progress = -1

        def report_ingest_progress(current: int, total: int) -> None:
            nonlocal last_ingest_progress
            if total <= 0:
                return
            # Keep UI updates coarse enough to avoid excessive job-row churn.
            if current < total and current - last_ingest_progress < 10_000:
                return
            if current == last_ingest_progress:
                return
            last_ingest_progress = current
            self._update_job_progress(
                session,
                job_id,
                progress_phase="Processing downloaded ESI market orders",
                progress_current=current,
                progress_total=total,
                progress_unit="downloaded records",
                message=f"Processed {current} / {total} downloaded ESI market orders.",
                isolated=True,
            )
        # Resolve target station internal IDs for delta computation
        target_internal_ids: set[int] = set()
        if target_eve_ids:
            target_internal_ids = set(
                session.scalars(
                    select(Location.id).where(Location.location_id.in_(target_eve_ids))
                ).all()
            )

        if cancellation_check is not None:
            cancellation_check()
        ingest_started_at = perf_counter()
        result = ingestion_service.ingest_order_batches(
            session,
            region_batches=[
                EsiRegionOrderBatch(
                    region_id=region.id,
                    eve_region_id=region.region_id,
                    records=order_rows,
                )
                for region, order_rows in downloaded_order_batches
            ],
            universe_client=universe_client,
            cancellation_check=cancellation_check,
            target_location_ids=target_internal_ids if target_internal_ids else None,
            progress_callback=report_ingest_progress,
        )
        total_processed += result.records_processed
        total_created += result.created
        total_updated += result.updated
        total_deleted += result.deleted
        total_stations_created += result.stations_created
        total_skipped_missing_items += result.skipped_missing_items
        total_skipped_non_npc_locations += result.skipped_non_npc_locations
        self._log_job_stage_checkpoint(
            "opportunity_rebuild",
            "ingest_esi_market_orders",
            started_at=ingest_started_at,
            downloaded_order_count=total_downloaded_orders,
            processed_count=result.records_processed,
            delta_count=result.delta_count,
        )

        # Aggregate deltas into demand periods and cleanup old deltas
        demand_period_count = 0
        if result.delta_count > 0 and target_internal_ids:
            from app.services.npc_stations.demand_periods import NpcStationDemandPeriodService
            from app.services.npc_stations.deltas import NpcStationDeltaService

            analysis_period = max(settings.default_analysis_period_days, 1)
            demand_started_at = perf_counter()
            demand_period_count = NpcStationDemandPeriodService().refresh_for_locations(
                session,
                target_location_ids=list(target_internal_ids),
                period_days=analysis_period,
            )
            NpcStationDeltaService.cleanup_old_deltas(session)
            session.commit()
            self._log_job_stage_checkpoint(
                "opportunity_rebuild",
                "refresh_npc_demand_periods",
                started_at=demand_started_at,
                target_location_count=len(target_internal_ids),
                demand_period_count=demand_period_count,
            )

        rebuild_generated_count, rebuild_scope_count = self._rebuild_opportunities(
            session,
            job_id=job_id,
            period_days=max(settings.default_analysis_period_days, 1),
            cancellation_check=cancellation_check,
            progress_phase_label="Rebuilding item opportunities",
        )

        self._update_job_progress(
            session,
            job_id,
            progress_phase="Rebuilding item opportunities",
            progress_current=rebuild_scope_count,
            progress_total=rebuild_scope_count,
            progress_unit="targets",
            message=(
                f"Rebuilt item opportunities for {rebuild_scope_count} / {rebuild_scope_count} targets "
                f"({rebuild_generated_count} opportunity rows written)."
            ),
        )

        message = (
            "Synced ESI market orders "
            f"({total_processed} active orders, {total_created} created, {total_updated} updated, "
            f"{total_deleted} deleted, {total_stations_created} stations discovered, "
            f"{total_skipped_missing_items} skipped because item foundation data was missing, "
            f"{total_skipped_non_npc_locations} skipped because the location could not be resolved across {len(regions)} regions, "
            f"{result.delta_count} order deltas, {demand_period_count} demand periods, "
            f"{rebuild_generated_count} opportunity items across {rebuild_scope_count} target scopes)."
        )
        self._log_job_stage_checkpoint(
            "opportunity_rebuild",
            "sync_esi_market_orders_total",
            started_at=sync_started_at,
            processed_count=total_processed,
            downloaded_order_count=total_downloaded_orders,
        )
        return (total_processed, "regions", str(len(regions)), message)

    def _sync_everef_history(
        self,
        session: Session,
        *,
        job_id: int,
        cancellation_check: Callable[[], None] | None = None,
    ) -> tuple[int, str, str | None, str]:
        cache_dir = Path(tempfile.gettempdir()) / "everef_cache"
        sync_started_at = perf_counter()
        analysis_period_days = max(
            SettingsService(session_factory=lambda: session).get_settings_for_session(session).default_analysis_period_days,
            1,
        )

        def resolve_dates() -> list[tuple[date, int | None]]:
            totals = fetch_totals_json()
            state_rows = session.scalars(
                select(EveRefHistorySyncState).order_by(EveRefHistorySyncState.history_date.asc())
            ).all()
            existing_by_date = {row.history_date: row for row in state_rows}

            totals_by_date: dict[date, int | None] = {}
            for raw_date, payload in totals.items():
                try:
                    parsed_date = date.fromisoformat(raw_date)
                except ValueError:
                    continue
                file_size: int | None
                if isinstance(payload, dict):
                    raw_size = payload.get("size")
                    try:
                        file_size = int(raw_size) if raw_size is not None else None
                    except (TypeError, ValueError):
                        file_size = None
                elif isinstance(payload, int):
                    file_size = payload
                else:
                    file_size = None
                totals_by_date[parsed_date] = file_size

            analysis_window_dates = set(get_available_dates(analysis_period_days))
            if analysis_window_dates:
                totals_by_date = {
                    history_date: file_size
                    for history_date, file_size in totals_by_date.items()
                    if history_date in analysis_window_dates
                }

            if not existing_by_date:
                return [
                    (history_date, totals_by_date[history_date])
                    for history_date in get_available_dates(analysis_period_days)
                    if history_date in totals_by_date
                ]

            return [
                (history_date, file_size)
                for history_date, file_size in sorted(totals_by_date.items())
                if history_date not in existing_by_date or existing_by_date[history_date].file_size != file_size
            ]

        dates_to_download = self._run_job_stage(
            session,
            job_id=job_id,
            stage_key="resolve_dates",
            func=resolve_dates,
            success_metrics=lambda result: {"date_count": len(result)},
        )
        self._log_job_stage_checkpoint(
            "everef_history_sync",
            "resolve_dates",
            started_at=sync_started_at,
            date_count=len(dates_to_download),
        )

        if not dates_to_download:
            return (0, "targets", "0", "Skipped EVE Ref history sync because no files required refresh.")

        rows_inserted = 0
        ingestion_service = EveRefHistoryIngestionService()
        total_dates = len(dates_to_download)

        for index, (history_date, file_size) in enumerate(dates_to_download, start=1):
            if cancellation_check is not None:
                cancellation_check()
            self._update_job_progress(
                session,
                job_id,
                progress_phase="Ingesting EVE Ref history files",
                progress_current=index - 1,
                progress_total=total_dates,
                progress_unit="dates",
                message=f"Ingesting EVE Ref history for {history_date.isoformat()} ({index} / {total_dates}).",
            )

            def ingest_date() -> int:
                try:
                    csv_path = download_history_file(history_date, cache_dir)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        logger.info(
                            "EVE Ref history file not yet available for %s (404), skipping.",
                            history_date.isoformat(),
                        )
                        return 0
                    raise
                try:
                    inserted = ingestion_service.ingest_history_file(
                        session,
                        csv_path,
                        cancellation_check=cancellation_check,
                    )
                    state_row = session.scalar(
                        select(EveRefHistorySyncState).where(EveRefHistorySyncState.history_date == history_date)
                    )
                    if state_row is None:
                        state_row = EveRefHistorySyncState(
                            history_date=history_date,
                            loaded_at=datetime.now(UTC),
                            file_size=file_size,
                        )
                        session.add(state_row)
                    else:
                        state_row.loaded_at = datetime.now(UTC)
                        state_row.file_size = file_size
                    session.commit()
                    return inserted
                finally:
                    csv_path.unlink(missing_ok=True)
                    csv_archive_path = csv_path.with_suffix(f"{csv_path.suffix}.bz2")
                    csv_archive_path.unlink(missing_ok=True)

            def ingest_success_metrics(result: int) -> dict[str, object]:
                return {
                    "history_date": history_date.isoformat(),
                    "file_size": file_size,
                    "rows_inserted": result,
                }

            inserted = self._run_job_stage(
                session,
                job_id=job_id,
                stage_key="ingest",
                func=ingest_date,
                initial_metrics={"history_date": history_date.isoformat(), "file_size": file_size},
                success_metrics=ingest_success_metrics,
            )
            rows_inserted += inserted
            self._update_job_progress(
                session,
                job_id,
                progress_phase="Ingesting EVE Ref history files",
                progress_current=index,
                progress_total=total_dates,
                progress_unit="dates",
                message=f"Ingested EVE Ref history for {history_date.isoformat()} ({index} / {total_dates}).",
            )

        self._log_job_stage_checkpoint(
            "everef_history_sync",
            "ingest",
            started_at=sync_started_at,
            date_count=total_dates,
            rows_inserted=rows_inserted,
        )

        phase_started_at = perf_counter()
        esi_demand_keys = self._esi_demand_refresh_keys(session)
        total_esi_keys = len(esi_demand_keys)
        preload_started_at = perf_counter()
        unique_location_ids = {location_id for location_id, _ in esi_demand_keys}
        unique_type_ids = {type_id for _, type_id in esi_demand_keys}
        locations = (
            session.scalars(select(Location).where(Location.id.in_(unique_location_ids))).all()
            if unique_location_ids
            else []
        )
        items = (
            session.scalars(select(Item).where(Item.id.in_(unique_type_ids))).all()
            if unique_type_ids
            else []
        )
        self._log_profile_checkpoint(
            "preload_esi_demand_identity_map",
            started_at=preload_started_at,
            location_count=len(unique_location_ids),
            item_count=len(unique_type_ids),
        )
        adam_covered_preload_started_at = perf_counter()
        eve_location_id_by_internal = {
            location.id: location.location_id
            for location in locations
        }
        internal_location_id_by_eve = {
            eve_location_id: internal_id for internal_id, eve_location_id in eve_location_id_by_internal.items()
        }
        eve_type_id_by_internal = {
            item.id: item.type_id
            for item in items
        }
        internal_item_id_by_eve = {eve_type_id: internal_id for internal_id, eve_type_id in eve_type_id_by_internal.items()}
        adam_covered_keys: set[tuple[int, int]] = set()
        if eve_location_id_by_internal and eve_type_id_by_internal:
            covered_rows = session.execute(
                select(
                    AdamMarketOrdersTradeRaw.c.location_id,
                    AdamMarketOrdersTradeRaw.c.type_id,
                )
                .where(
                    AdamMarketOrdersTradeRaw.c.location_id.in_(eve_location_id_by_internal.values()),
                    AdamMarketOrdersTradeRaw.c.type_id.in_(eve_type_id_by_internal.values()),
                )
                .distinct()
            ).all()
            adam_covered_keys = {
                (internal_location_id, internal_item_id)
                for eve_location_id, eve_type_id in covered_rows
                if (internal_location_id := internal_location_id_by_eve.get(eve_location_id)) is not None
                if (internal_item_id := internal_item_id_by_eve.get(eve_type_id)) is not None
            }
        self._log_profile_checkpoint(
            "preload_adam_covered_keys",
            started_at=adam_covered_preload_started_at,
            covered_count=len(adam_covered_keys),
        )
        # Keys already covered by adam4eve are handled by adam4eve_sync — exclude them.
        esi_demand_keys = [k for k in esi_demand_keys if k not in adam_covered_keys]
        total_esi_keys = len(esi_demand_keys)
        self._update_job_progress(
            session,
            job_id,
            progress_phase="Refreshing ESI demand records",
            progress_current=0,
            progress_total=total_esi_keys,
            progress_unit="keys",
            message=f"Refreshing ESI demand for {total_esi_keys} location/item pairs.",
        )
        demand_service = MarketDemandResolutionService()
        demand_preload_started_at = perf_counter()
        demand_preload = demand_service.build_batch_preload(
            session,
            demand_keys=esi_demand_keys,
            period_days=analysis_period_days,
        )
        self._log_profile_checkpoint(
            "preload_esi_demand_batch_context",
            started_at=demand_preload_started_at,
            history_pair_count=len(demand_preload.esi_history_by_region_type),
            existing_row_count=len(demand_preload.existing_rows_by_key),
        )
        derived_count = 0
        total_adam_s = 0.0
        total_esi_history_s = 0.0
        total_upsert_s = 0.0
        _COMMIT_INTERVAL = 50
        _PROGRESS_INTERVAL = 100
        for idx, (location_id, type_id) in enumerate(esi_demand_keys, start=1):
            if cancellation_check is not None:
                cancellation_check()
            result = demand_service.upsert_for_location(
                session,
                location_id=location_id,
                type_id=type_id,
                period_days=analysis_period_days,
                adam_covered=(location_id, type_id) in adam_covered_keys,
                autocommit=False,
                preload=demand_preload,
            )
            if idx % _COMMIT_INTERVAL == 0:
                session.commit()
            total_adam_s += result.timing.adam_lookup_s
            total_esi_history_s += result.timing.esi_history_s
            total_upsert_s += result.timing.upsert_s
            if result.row is not None:
                derived_count += 1
            if idx % _PROGRESS_INTERVAL == 0 or idx == total_esi_keys:
                self._update_job_progress(
                    session,
                    job_id,
                    progress_phase="Refreshing ESI demand records",
                    progress_current=idx,
                    progress_total=total_esi_keys,
                    progress_unit="keys",
                    message=f"Refreshing ESI demand: {idx} / {total_esi_keys} keys ({derived_count} rows written).",
                )
        session.commit()
        self._log_profile_checkpoint(
            "refresh_esi_demand",
            started_at=phase_started_at,
            demand_key_count=total_esi_keys,
            derived_count=derived_count,
            total_s=round(perf_counter() - phase_started_at, 3),
            adam_lookup_s=round(total_adam_s, 3),
            esi_history_s=round(total_esi_history_s, 3),
            upsert_s=round(total_upsert_s, 3),
            avg_ms_per_key=round((perf_counter() - phase_started_at) / total_esi_keys * 1000, 1) if total_esi_keys else 0,
        )

        message = (
            "Synced EVE Ref history "
            f"({rows_inserted} rows inserted across {total_dates} dates, "
            f"{derived_count} ESI demand rows refreshed)."
        )
        return (rows_inserted, "targets", str(total_dates), message)

    def _should_refresh_esi_market_orders_before_rebuild(self, session: Session) -> bool:
        latest_success = session.scalar(
            select(SyncJobRun.finished_at)
            .where(
                SyncJobRun.job_type == "esi_market_orders_sync",
                SyncJobRun.status == "success",
                SyncJobRun.finished_at.is_not(None),
            )
            .order_by(SyncJobRun.finished_at.desc(), SyncJobRun.id.desc())
            .limit(1)
        )
        if latest_success is None:
            return True
        latest_success_at = self._ensure_utc(latest_success)
        max_age = timedelta(minutes=self.PRE_REBUILD_ESI_MARKET_ORDER_MAX_AGE_MINUTES)
        return (datetime.now(UTC) - latest_success_at) >= max_age

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

    def _refresh_market_prices_for_locations(
        self,
        session: Session,
        *,
        location_ids: Sequence[int],
        type_ids: list[int],
        period_days: int | None = None,
        period_days_list: Sequence[int] | None = None,
        cancellation_check: Callable[[], None] | None = None,
    ) -> int:
        if not type_ids:
            return 0

        normalized_location_ids = list(dict.fromkeys(location_ids))
        if not normalized_location_ids:
            return 0

        service = MarketPricePeriodService()
        if cancellation_check is not None:
            cancellation_check()
        requested_periods = (
            sorted(set(period_days_list))
            if period_days_list is not None
            else ([period_days] if period_days is not None else [])
        )
        if not requested_periods:
            return 0
        return service.refresh_region_periods_from_history(
            session,
            region_id=0,
            location_ids=normalized_location_ids,
            type_ids=type_ids,
            period_days_list=requested_periods,
        )

    def _refresh_market_demand_for_locations(
        self,
        session: Session,
        *,
        location_ids: list[int],
        type_ids: list[int],
        period_days: int,
        cancellation_check: Callable[[], None] | None = None,
    ) -> int:
        if not location_ids or not type_ids:
            return 0

        service = MarketDemandResolutionService()
        refreshed_count = 0
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

    def _refresh_market_demand_for_keys(
        self,
        session: Session,
        *,
        demand_keys: Sequence[tuple[int, int]],
        period_days: int,
        cancellation_check: Callable[[], None] | None = None,
    ) -> int:
        if not demand_keys:
            return 0

        service = MarketDemandResolutionService()
        if cancellation_check is not None:
            cancellation_check()
        return service.refresh_npc_keys_from_adam(
            session,
            demand_keys=list(dict.fromkeys(demand_keys)),
            period_days=period_days,
        )

    def _load_rebuild_scopes(
        self,
        session: Session,
        *,
        period_days: int | None,
    ) -> list[tuple[int, int]]:
        configured_target_market_ids = (
            SettingsService(session_factory=lambda: session).get_settings_for_session(session).target_market_location_ids
        )
        if not configured_target_market_ids:
            return []
        configured_target_ids = set(
            session.scalars(select(Location.id).where(Location.location_id.in_(configured_target_market_ids))).all()
        )
        if not configured_target_ids:
            return []

        scope_query = (
            select(
                MarketDemandResolved.location_id,
                MarketDemandResolved.period_days,
            )
            .where(MarketDemandResolved.location_id.in_(configured_target_ids))
            .distinct()
        )
        if period_days is not None:
            scope_query = scope_query.where(MarketDemandResolved.period_days == period_days)
        return [(int(row[0]), int(row[1])) for row in session.execute(scope_query).all()]

    def _adam_demand_refresh_keys(
        self,
        session: Session,
        *,
        locations: Sequence[Location],
        items: Sequence[Item],
        internal_location_id_by_eve_id: dict[int, int],
        internal_item_id_by_type_id: dict[int, int],
    ) -> list[tuple[int, int]]:
        if not locations or not items:
            return []

        # Keys with adam4eve data — primary source
        raw_pairs = session.execute(
            select(
                distinct(AdamMarketOrdersTradeRaw.c.location_id),
                AdamMarketOrdersTradeRaw.c.type_id,
            ).where(
                AdamMarketOrdersTradeRaw.c.location_id.in_([location.location_id for location in locations]),
                AdamMarketOrdersTradeRaw.c.type_id.in_([item.type_id for item in items]),
            )
        ).all()

        keys: list[tuple[int, int]] = []
        for external_location_id, external_type_id in raw_pairs:
            internal_location_id = internal_location_id_by_eve_id.get(external_location_id)
            internal_item_id = internal_item_id_by_type_id.get(external_type_id)
            if internal_location_id is None or internal_item_id is None:
                continue
            keys.append((internal_location_id, internal_item_id))

        return list(dict.fromkeys(keys))

    def _esi_demand_refresh_keys(
        self,
        session: Session,
    ) -> list[tuple[int, int]]:
        """Return (internal_location_id, internal_item_id) pairs for NPC stations
        where ESI market orders exist AND the region has ESI history data for that item.
        Applies the same target-station / source-region constraints as the ESI order sync
        so the scope stays manageable."""
        settings = SettingsService(session_factory=lambda: session).get_settings_for_session(session)
        target_eve_ids: list[int] = settings.target_market_location_ids or []
        if not target_eve_ids:
            return []

        target_location_ids: set[int] = set(
            session.scalars(
                select(Location.id).where(
                    Location.location_id.in_(target_eve_ids),
                    Location.location_type == "npc_station",
                )
            ).all()
        )
        if not target_location_ids:
            return []
        target_locations_by_region: dict[int, list[int]] = defaultdict(list)
        for location_id, region_id in session.execute(
            select(Location.id, Location.region_id).where(Location.id.in_(target_location_ids))
        ).all():
            if region_id is not None:
                target_locations_by_region[region_id].append(location_id)

        # Same desired-region logic as the ESI order sync
        desired_eve_region_ids: set[int] = set(settings.source_region_ids or [])
        desired_eve_region_ids.update(
            rid
            for rid in session.scalars(
                select(Region.region_id)
                .join(Location, Location.region_id == Region.id)
                .where(Location.location_id.in_(target_eve_ids))
            ).all()
            if rid is not None
        )
        desired_internal_region_ids: set[int] = set(
            session.scalars(
                select(Region.id).where(Region.region_id.in_(desired_eve_region_ids))
            ).all()
        )
        if not desired_internal_region_ids:
            return []

        # Items with live market orders at target stations
        order_pairs = session.execute(
            select(
                distinct(EsiMarketOrder.location_id),
                EsiMarketOrder.type_id,
            ).where(
                EsiMarketOrder.location_id.in_(target_location_ids),
            )
        ).all()

        # Items with live market orders at target stations AND ESI history
        items_with_orders: set[int] = {type_id for _, type_id in order_pairs}
        items_with_history: set[int] = set(
            session.scalars(
                select(distinct(EsiHistoryDaily.type_id)).where(
                    EsiHistoryDaily.type_id.in_(items_with_orders),
                    EsiHistoryDaily.region_id.in_(desired_internal_region_ids),
                )
            ).all()
        )
        order_based_pairs: list[tuple[int, int]] = [
            (location_id, type_id)
            for location_id, type_id in dict.fromkeys(order_pairs)
            if type_id in items_with_history
        ]

        # Items with npc_station_demand_period at target stations
        # (self-contained demand signal — no ESI history gate needed)
        analysis_period_days = max(settings.default_analysis_period_days, 1)
        period_based_pairs: list[tuple[int, int]] = [
            (location_id, type_id)
            for location_id, type_id in session.execute(
                select(
                    distinct(NpcStationDemandPeriod.location_id),
                    NpcStationDemandPeriod.type_id,
                ).where(
                    NpcStationDemandPeriod.location_id.in_(target_location_ids),
                    NpcStationDemandPeriod.period_days == analysis_period_days,
                    NpcStationDemandPeriod.buy_from_sell_period > 0,
                )
            ).all()
        ]

        cutoff_date = date.today() - timedelta(days=analysis_period_days)
        history_based_pairs: list[tuple[int, int]] = []
        for region_id, type_id in session.execute(
            select(
                distinct(EsiHistoryDaily.region_id),
                EsiHistoryDaily.type_id,
            ).where(
                EsiHistoryDaily.region_id.in_(desired_internal_region_ids),
                EsiHistoryDaily.date >= cutoff_date,
                EsiHistoryDaily.volume > 0,
            )
        ).all():
            for location_id in target_locations_by_region.get(region_id, []):
                history_based_pairs.append((location_id, type_id))

        # Union — order-based first, then period-based, then history-only gaps
        all_pairs: dict[tuple[int, int], None] = dict.fromkeys(order_based_pairs)
        all_pairs.update(dict.fromkeys(period_based_pairs))
        all_pairs.update(dict.fromkeys(history_based_pairs))
        return list(all_pairs.keys())

    def _rebuild_opportunities(
        self,
        session: Session,
        job_id: int,
        period_days: int | None = None,
        cancellation_check: Callable[[], None] | None = None,
        progress_phase_label: str | None = None,
    ) -> tuple[int, int]:
        rebuild_started_at = perf_counter()
        scope_load_started_at = perf_counter()

        scopes = self._run_job_stage(
            session,
            job_id=job_id,
            stage_key="load_rebuild_scopes",
            func=lambda: self._load_rebuild_scopes(session, period_days=period_days),
            success_metrics=lambda result: {"scope_count": len(result)},
        )
        if not scopes:
            return (0, 0)
        self._log_job_stage_checkpoint(
            "opportunity_rebuild",
            "load_rebuild_scopes",
            started_at=scope_load_started_at,
            scope_count=len(scopes),
        )
        if progress_phase_label is not None:
            self._update_job_progress(
                session,
                job_id,
                progress_phase=progress_phase_label,
                progress_current=0,
                progress_total=len(scopes),
                progress_unit="targets",
                message=f"{progress_phase_label} for 0 / {len(scopes)} targets.",
                isolated=True,
            )

        scope_count = 0
        generated_count = 0
        scope_generation_started_at = perf_counter()
        for target_location_id, scope_period_days in scopes:
            if cancellation_check is not None:
                cancellation_check()
            type_ids = list(
                session.scalars(
                    select(MarketDemandResolved.type_id).where(
                        MarketDemandResolved.location_id == target_location_id,
                        MarketDemandResolved.period_days == scope_period_days,
                    )
                ).all()
            )
            if not type_ids:
                continue
            source_location_ids: list[int] = list(
                session.scalars(
                    select(MarketPricePeriod.location_id)
                    .where(
                        MarketPricePeriod.period_days == scope_period_days,
                        MarketPricePeriod.type_id.in_(type_ids),
                        MarketPricePeriod.location_id != target_location_id,
                    )
                    .distinct()
                ).all()
            )
            if not source_location_ids:
                continue

            def record_scope_stage(stage_key: str, stage_started_at: float, metrics: dict[str, object]) -> None:
                self._record_completed_job_stage(
                    session,
                    job_id=job_id,
                    stage_key=f"target_scope.{stage_key}",
                    stage_started_at=stage_started_at,
                    metrics={
                        "target_location_id": target_location_id,
                        "period_days": scope_period_days,
                        **metrics,
                    },
                )

            result = self._run_job_stage(
                session,
                job_id=job_id,
                stage_key="target_scope.total",
                func=lambda: OpportunityGenerationService().generate_for_target(
                    session,
                    target_location_id=target_location_id,
                    source_location_ids=source_location_ids,
                    type_ids=type_ids,
                    period_days=scope_period_days,
                    replace_entire_target_scope=True,
                    cancellation_check=cancellation_check,
                    stage_callback=record_scope_stage,
                ),
                initial_metrics={
                    "target_location_id": target_location_id,
                    "period_days": scope_period_days,
                    "type_count": len(type_ids),
                    "source_count": len(source_location_ids),
                },
                success_metrics=lambda scope_result: {
                    "target_location_id": target_location_id,
                    "period_days": scope_period_days,
                    "type_count": len(type_ids),
                    "source_count": len(source_location_ids),
                    "generated_count": scope_result.item_count,
                    "summary_count": scope_result.summary_count,
                },
            )
            scope_count += 1
            generated_count += result.item_count
            if progress_phase_label is not None:
                self._update_job_progress(
                    session,
                    job_id,
                    progress_phase=progress_phase_label,
                    progress_current=scope_count,
                    progress_total=len(scopes),
                    progress_unit="targets",
                    message=(
                        f"{progress_phase_label}: {scope_count} / {len(scopes)} targets "
                        f"({generated_count} opportunity rows written)."
                    ),
                    isolated=True,
                )

        self._log_job_stage_checkpoint(
            "opportunity_rebuild",
            "generate_opportunity_rows",
            started_at=scope_generation_started_at,
            scope_count=scope_count,
            generated_count=generated_count,
        )
        self._log_job_stage_checkpoint(
            "opportunity_rebuild",
            "_rebuild_opportunities_total",
            started_at=rebuild_started_at,
            scope_count=scope_count,
            generated_count=generated_count,
        )

        return (generated_count, scope_count)

    def prepare_trade_period(
        self,
        session: Session,
        *,
        target_location_id: int,
        period_days: int,
        source_location_id: int | None = None,
        type_id: int | None = None,
        refresh_inputs: bool = True,
    ) -> None:
        target_location = session.get(Location, target_location_id)
        if target_location is None:
            return

        requested_period_days = max(period_days, 1)
        type_ids = self._trade_period_type_ids(
            session,
            target_location_id=target_location.id,
            requested_type_id=type_id,
        )
        if not type_ids:
            return

        source_location_ids = self._trade_period_source_location_ids(
            session,
            target_location_id=target_location.id,
            type_ids=type_ids,
            requested_source_location_id=source_location_id,
        )
        if not source_location_ids:
            return

        if refresh_inputs:
            self._refresh_market_prices_for_locations(
                session,
                location_ids=[target_location.id],
                type_ids=type_ids,
                period_days=requested_period_days,
            )
            if target_location.location_type == "structure":
                self._refresh_structure_demand_for_location(
                    session,
                    location=target_location,
                    type_ids=type_ids,
                    period_days=requested_period_days,
                )
            if target_location.location_type == "npc_station":
                self._refresh_market_demand_for_keys(
                    session,
                    demand_keys=[(target_location.id, current_type_id) for current_type_id in type_ids],
                    period_days=requested_period_days,
                )
            else:
                self._refresh_market_demand_for_locations(
                    session,
                    location_ids=[target_location.id],
                    type_ids=type_ids,
                    period_days=requested_period_days,
                )
        OpportunityGenerationService().generate_for_target(
            session,
            target_location_id=target_location.id,
            source_location_ids=source_location_ids,
            type_ids=type_ids,
            period_days=requested_period_days,
            replace_entire_target_scope=source_location_id is None and type_id is None,
        )

    def refresh_trade_scope_from_existing_rows(
        self,
        session: Session,
        *,
        target_location_id: int,
        period_days: int,
        source_location_id: int | None = None,
        type_id: int | None = None,
    ) -> bool:
        requested_period_days = max(period_days, 1)
        type_ids = self._trade_period_type_ids(
            session,
            target_location_id=target_location_id,
            requested_type_id=type_id,
        )
        if not type_ids:
            return False

        source_location_ids = self._trade_period_source_location_ids(
            session,
            target_location_id=target_location_id,
            type_ids=type_ids,
            requested_source_location_id=source_location_id,
        )
        if not source_location_ids:
            return False

        OpportunityGenerationService().generate_for_target(
            session,
            target_location_id=target_location_id,
            source_location_ids=source_location_ids,
            type_ids=type_ids,
            period_days=requested_period_days,
            replace_entire_target_scope=source_location_id is None and type_id is None,
        )
        return True

    def _trade_period_type_ids(
        self,
        session: Session,
        *,
        target_location_id: int,
        requested_type_id: int | None = None,
    ) -> list[int]:
        if requested_type_id is not None:
            resolved_type_id = session.scalar(
                select(Item.id).where((Item.id == requested_type_id) | (Item.type_id == requested_type_id))
            )
            return [resolved_type_id] if resolved_type_id is not None else []

        type_ids = set(
            session.scalars(
                select(EsiMarketOrder.type_id).where(EsiMarketOrder.location_id == target_location_id).distinct()
            ).all()
        )
        type_ids.update(
            session.scalars(
                select(Item.id)
                .join(AdamMarketOrdersTradeRaw, AdamMarketOrdersTradeRaw.c.type_id == Item.type_id)
                .join(Location, Location.location_id == AdamMarketOrdersTradeRaw.c.location_id)
                .where(Location.id == target_location_id)
                .distinct()
            ).all()
        )
        type_ids.update(
            session.scalars(
                select(StructureOrderDelta.type_id)
                .where(StructureOrderDelta.structure_id == target_location_id)
                .distinct()
            ).all()
        )
        return sorted(type_ids)

    def _trade_period_source_location_ids(
        self,
        session: Session,
        *,
        target_location_id: int,
        type_ids: list[int],
        requested_source_location_id: int | None = None,
    ) -> list[int]:
        if not type_ids:
            return []
        source_location_ids = list(
            session.scalars(
                select(EsiMarketOrder.location_id)
                .where(
                    EsiMarketOrder.location_id != target_location_id,
                    EsiMarketOrder.type_id.in_(type_ids),
                    EsiMarketOrder.is_buy_order.is_(False),
                )
                .distinct()
                .order_by(EsiMarketOrder.location_id.asc())
            ).all()
        )
        if requested_source_location_id is not None:
            if requested_source_location_id not in source_location_ids:
                return []
            return [requested_source_location_id]
        return source_location_ids

    def _refresh_structure_demand_for_location(
        self,
        session: Session,
        *,
        location: Location,
        type_ids: list[int],
        period_days: int,
    ) -> None:
        service = StructureDemandPeriodService()
        for type_id in type_ids:
            service.upsert_period(
                session,
                structure_id=location.location_id,
                type_id=type_id,
                period_days=period_days,
            )

    def _all_regions(self, session: Session, *, debug_enabled: bool = False) -> list[Region]:
        regions = list(
            session.scalars(
                select(Region).order_by(Region.region_id.asc())
            ).all()
        )
        if debug_enabled:
            return regions[: self.DEBUG_REGION_LIMIT]
        return regions

    def _adam_demand_regions(
        self,
        session: Session,
        *,
        locations: Sequence[Location],
        latest_export: AdamMarketOrdersExport,
        required_since_date: date,
    ) -> set[int]:
        region_ids = sorted({location.region_id for location in locations})
        if not region_ids:
            return set()

        state_by_region_id = {
            row.region_id: row
            for row in session.scalars(
                select(AdamNpcDemandSyncState).where(AdamNpcDemandSyncState.region_id.in_(region_ids))
            ).all()
        }
        regions_to_fetch: set[int] = set()
        created_state = False
        for region_id in region_ids:
            state = state_by_region_id.get(region_id)
            cursor = self.bulk_imports.get_cursor(
                session,
                import_kind=self.IMPORT_KIND_ADAM_DEMAND,
                scope_key=f"region:{region_id}",
            )
            synced_through_date = cursor.synced_through_date if cursor is not None else None
            if synced_through_date is None and state is not None:
                synced_through_date = state.synced_through_date
            oldest_persisted_date = self._min_persisted_adam_demand_date(session, region_id=region_id)
            if synced_through_date is None:
                synced_through_date = self._max_persisted_adam_demand_date(session, region_id=region_id)
            if self._adam_demand_region_synced_for_export(
                last_completed_key=cursor.last_completed_key if cursor is not None else (state.export_key if state is not None else None),
                latest_export=latest_export,
                synced_through_date=synced_through_date,
                oldest_persisted_date=oldest_persisted_date,
                required_since_date=required_since_date,
            ):
                if state is None:
                    session.add(
                        AdamNpcDemandSyncState(
                            region_id=region_id,
                            export_key=latest_export.export_key,
                            synced_through_date=synced_through_date,
                            last_checked_at=datetime.now(UTC),
                        )
                    )
                    created_state = True
                continue
            regions_to_fetch.add(region_id)

        if created_state:
            session.commit()
        return regions_to_fetch

    def _adam_demand_region_synced_for_export(
        self,
        *,
        last_completed_key: str | None,
        latest_export: AdamMarketOrdersExport,
        synced_through_date: date | None,
        oldest_persisted_date: date | None,
        required_since_date: date,
    ) -> bool:
        has_required_history_window = (
            oldest_persisted_date is not None and oldest_persisted_date <= required_since_date
        )
        if synced_through_date is None or not has_required_history_window:
            return False
        if last_completed_key == latest_export.export_key:
            return synced_through_date >= latest_export.covered_through_date and synced_through_date >= required_since_date
        return synced_through_date >= latest_export.covered_through_date

    def _record_adam_demand_region_check(
        self,
        session: Session,
        *,
        region_ids: list[int],
        exports: list[AdamMarketOrdersExport],
    ) -> None:
        if not region_ids or not exports:
            return
        latest_export = max(exports, key=lambda export: (export.covered_through_date, export.export_key))

        for region_id in region_ids:
            state = session.scalar(select(AdamNpcDemandSyncState).where(AdamNpcDemandSyncState.region_id == region_id))
            if state is None:
                state = AdamNpcDemandSyncState(region_id=region_id)
                session.add(state)

            existing_synced_through = state.synced_through_date
            state.synced_through_date = (
                max(existing_synced_through, latest_export.covered_through_date)
                if existing_synced_through is not None
                else latest_export.covered_through_date
            )
            state.export_key = latest_export.export_key
            state.last_checked_at = datetime.now(UTC)

            self.bulk_imports.mark_cursor(
                session,
                import_kind=self.IMPORT_KIND_ADAM_DEMAND,
                scope_key=f"region:{region_id}",
                synced_through_date=state.synced_through_date,
                last_completed_key=latest_export.export_key,
            )

        self.bulk_imports.mark_cursor(
            session,
            import_kind=self.IMPORT_KIND_ADAM_DEMAND,
            scope_key=self.IMPORT_SCOPE_GLOBAL,
            synced_through_date=latest_export.covered_through_date,
            last_completed_key=latest_export.export_key,
        )

        session.commit()

    def _max_persisted_adam_demand_date(self, session: Session, *, region_id: int) -> date | None:
        region = session.get(Region, region_id)
        if region is None:
            return None
        persisted_dates = session.scalars(
            select(AdamMarketOrdersTradeRaw.c.scanDate)
            .where(AdamMarketOrdersTradeRaw.c.region_id == region.region_id)
            .order_by(AdamMarketOrdersTradeRaw.c.scanDate.desc())
        ).all()
        return persisted_dates[0] if persisted_dates else None

    def _min_persisted_adam_demand_date(self, session: Session, *, region_id: int) -> date | None:
        region = session.get(Region, region_id)
        if region is None:
            return None
        persisted_dates = session.scalars(
            select(AdamMarketOrdersTradeRaw.c.scanDate)
            .where(AdamMarketOrdersTradeRaw.c.region_id == region.region_id)
            .order_by(AdamMarketOrdersTradeRaw.c.scanDate.asc())
        ).all()
        return persisted_dates[0] if persisted_dates else None

    def _adam_demand_sync_since_date(self, session: Session, *, lookback_days: int) -> date:
        rolling_since_date = datetime.now(UTC).date() - timedelta(days=max(lookback_days, 1))
        cursor = self.bulk_imports.get_cursor(
            session,
            import_kind=self.IMPORT_KIND_ADAM_DEMAND,
            scope_key=self.IMPORT_SCOPE_GLOBAL,
        )
        if cursor is not None and cursor.synced_through_date is not None:
            return max(rolling_since_date, cursor.synced_through_date - timedelta(days=max(lookback_days, 1)))

        persisted = session.scalar(select(func.max(AdamMarketOrdersTradeRaw.c.scanDate)))
        if persisted is not None:
            return max(rolling_since_date, persisted - timedelta(days=max(lookback_days, 1)))
        return rolling_since_date

    def _history_sync_since_date(self, session: Session, *, lookback_days: int) -> date:
        cursor = self.bulk_imports.get_cursor(
            session,
            import_kind=self.IMPORT_KIND_ADAM_PRICE_HISTORY,
            scope_key=self.IMPORT_SCOPE_GLOBAL,
        )
        rolling_since_date = datetime.now(UTC).date() - timedelta(days=max(lookback_days, 1))
        if cursor is not None and cursor.synced_through_date is not None:
            return max(rolling_since_date, cursor.synced_through_date - timedelta(days=max(lookback_days, 1)))
        persisted = self._max_persisted_history_date(session)
        if persisted is not None:
            return max(rolling_since_date, persisted - timedelta(days=max(lookback_days, 1)))
        return rolling_since_date

    def _history_checked_today(self, session: Session) -> bool:
        cursor = self.bulk_imports.get_cursor(
            session,
            import_kind=self.IMPORT_KIND_ADAM_PRICE_HISTORY,
            scope_key=self.IMPORT_SCOPE_GLOBAL,
        )
        if cursor is None or cursor.last_checked_at is None:
            return False
        return self._ensure_utc(cursor.last_checked_at).date() >= datetime.now(UTC).date()

    def _record_history_check(
        self,
        session: Session,
        *,
        synced_through_date: date | None,
    ) -> None:
        self.bulk_imports.mark_cursor(
            session,
            import_kind=self.IMPORT_KIND_ADAM_PRICE_HISTORY,
            scope_key=self.IMPORT_SCOPE_GLOBAL,
            synced_through_date=synced_through_date,
        )

    def _max_persisted_history_date(self, session: Session) -> date | None:
        persisted_dates = session.scalars(
            select(AdamMarketPriceHistoryDaily.date)
            .order_by(AdamMarketPriceHistoryDaily.date.desc())
        ).all()
        return persisted_dates[0] if persisted_dates else None

    def _history_sync_workset(
        self,
        session: Session,
        *,
        region_ids: list[int],
    ) -> list[AdamStationHistoryWorksetEntry]:
        if not region_ids:
            return []
        rows = session.execute(
            select(
                Region.id,
                Region.region_id,
                Location.id,
                Location.location_id,
                Item.id,
                Item.type_id,
            )
            .select_from(EsiMarketOrder)
            .join(Location, Location.id == EsiMarketOrder.location_id)
            .join(Item, Item.id == EsiMarketOrder.type_id)
            .join(Region, Region.id == Location.region_id)
            .where(Region.id.in_(region_ids))
            .distinct()
            .order_by(Region.id.asc(), Location.id.asc(), Item.id.asc())
        ).all()
        return [
            AdamStationHistoryWorksetEntry(
                internal_region_id=internal_region_id,
                external_region_id=external_region_id,
                internal_location_id=internal_location_id,
                external_location_id=external_location_id,
                internal_type_id=internal_type_id,
                external_type_id=external_type_id,
            )
            for (
                internal_region_id,
                external_region_id,
                internal_location_id,
                external_location_id,
                internal_type_id,
                external_type_id,
            ) in rows
        ]

    def _history_workset_has_missing_price_periods(
        self,
        session: Session,
        *,
        region_ids: list[int],
        period_days: int,
    ) -> bool:
        if not region_ids:
            return False
        missing_row = session.execute(
            select(EsiMarketOrder.id)
            .join(Location, Location.id == EsiMarketOrder.location_id)
            .join(Item, Item.id == EsiMarketOrder.type_id)
            .join(Region, Region.id == Location.region_id)
            .outerjoin(
                MarketPricePeriod,
                and_(
                    MarketPricePeriod.location_id == Location.id,
                    MarketPricePeriod.type_id == Item.id,
                    MarketPricePeriod.period_days == period_days,
                ),
            )
            .where(
                Region.id.in_(region_ids),
                MarketPricePeriod.id.is_(None),
            )
            .limit(1)
        ).first()
        return missing_row is not None

    def _sync_adam_regional_price_history(
        self,
        session: Session,
        *,
        job_id: int,
        regions: list[Region],
        lookback_days: int,
    ) -> tuple[int, int, int, int]:
        workset_entries = self._history_sync_workset(
            session,
            region_ids=[region.id for region in regions],
        )
        if not workset_entries:
            return (0, 0, 0, 0)

        current_period_days = min(max(lookback_days, 1), self.ADAM_HISTORY_MAX_LOOKBACK_DAYS)
        if self._history_checked_today(session) and not self._history_workset_has_missing_price_periods(
            session,
            region_ids=[region.id for region in regions],
            period_days=current_period_days,
        ):
            return (0, 0, 0, 0)

        since_date = self._history_sync_since_date(session, lookback_days=lookback_days)
        cached_history_exports = self.adam_client.cache_station_price_history_exports(
            since_date=since_date,
            session=session,
        )
        if not cached_history_exports:
            self._record_history_check(session, synced_through_date=since_date)
            return (0, 0, 0, 0)

        self._update_job_progress(
            session,
            job_id,
            progress_phase="Downloading Adam4EVE station price history",
            progress_current=0,
            progress_total=len(cached_history_exports),
            progress_unit="files",
            message=f"Downloading Adam4EVE station price history for 0 / {len(cached_history_exports)} files.",
        )

        total_history_processed = 0
        total_created = 0
        total_updated = 0
        total_price_rows = 0
        for file_index, (export, cached_file) in enumerate(cached_history_exports, start=1):
            self._check_for_cancellation(session, job_id)
            file_started_at = perf_counter()
            self._update_job_progress(
                session,
                job_id,
                progress_phase="Downloading Adam4EVE station price history",
                progress_current=file_index,
                progress_total=len(cached_history_exports),
                progress_unit="files",
                message=(
                    f"Downloading Adam4EVE station price history file {file_index} / "
                    f"{len(cached_history_exports)}: {export.export_key}."
                ),
            )
            file_result = AdamStationPriceHistoryIngestionService().ingest_region_history_file(
                session,
                csv_file_path=cached_file.path,
                workset_entries=workset_entries,
                since_date=since_date,
            )
            total_history_processed += file_result.records_processed
            total_created += file_result.created
            total_updated += file_result.updated
            self._log_profile_checkpoint(
                "ingest_history_file",
                started_at=file_started_at,
                file_index=file_index,
                file_total=len(cached_history_exports),
                export_key=export.export_key,
                records_processed=file_result.records_processed,
            )
            self._update_job_progress(
                session,
                job_id,
                progress_phase="Downloading Adam4EVE station price history",
                progress_current=file_index,
                progress_total=len(cached_history_exports),
                progress_unit="files",
                message=(
                    f"Downloaded Adam4EVE station price history for {file_index} / "
                    f"{len(cached_history_exports)} files: {export.export_key}."
                ),
            )

        all_location_ids = sorted({entry.internal_location_id for entry in workset_entries})
        all_type_ids = sorted({entry.internal_type_id for entry in workset_entries})
        refresh_started_at = perf_counter()
        total_price_rows = MarketPricePeriodService().refresh_region_periods_from_history(
            session,
            region_id=0,
            location_ids=all_location_ids,
            type_ids=all_type_ids,
            period_days_list=list(self.MARKET_PRICE_PERIODS),
        )
        self._log_profile_checkpoint(
            "refresh_price_periods_from_history",
            started_at=refresh_started_at,
            location_count=len(all_location_ids),
            type_count=len(all_type_ids),
            price_row_count=total_price_rows,
        )
        self._record_history_check(
            session,
            synced_through_date=max(
                [export.covered_through_date for export, _ in cached_history_exports],
                default=since_date,
            ),
        )
        return (total_history_processed, total_created, total_updated, total_price_rows)

    def _history_sync_items(self, session: Session, *, region_ids: list[int]) -> list[Item]:
        if not region_ids:
            return []

        item_ids = set(
            session.scalars(
                select(EsiMarketOrder.type_id).where(EsiMarketOrder.region_id.in_(region_ids)).distinct()
            ).all()
        )
        if not item_ids:
            return []

        return list(
            session.scalars(select(Item).where(Item.id.in_(item_ids)).order_by(Item.type_id.asc())).all()
        )

    def _history_sync_locations(self, session: Session, *, region_ids: list[int]) -> list[Location]:
        if not region_ids:
            return []

        location_ids = set(
            session.scalars(
                select(EsiMarketOrder.location_id).where(EsiMarketOrder.region_id.in_(region_ids)).distinct()
            ).all()
        )
        if not location_ids:
            return []

        return list(
            session.scalars(
                select(Location).where(Location.id.in_(location_ids)).order_by(Location.location_id.asc())
            ).all()
        )

    def _adam4eve_sync_totals(self, session: Session, *, period_days: int) -> dict[str, int]:
        return {
            "history_rows": int(session.scalar(select(func.count()).select_from(AdamMarketPriceHistoryDaily)) or 0),
            "resolved_demand_rows": int(
                session.scalar(
                    select(func.count())
                    .select_from(MarketDemandResolved)
                    .where(MarketDemandResolved.period_days == period_days)
                )
                or 0
            ),
            "price_period_rows": int(session.scalar(select(func.count()).select_from(MarketPricePeriod)) or 0),
            "opportunity_item_rows": int(
                session.scalar(
                    select(func.count())
                    .select_from(OpportunityItem)
                    .where(OpportunityItem.period_days == period_days)
                )
                or 0
            ),
        }

    def _check_for_cancellation(self, session: Session, job_id: int) -> None:
        if _PROCESS_CANCELLATION_EVENT.is_set():
            self._mark_job_cancelling(session, job_id, "Cancelling due to process shutdown signal.")
            raise JobCancelledError("Cancelled due to process shutdown signal.")

        probe_session = self.session_factory()
        try:
            job_run = probe_session.get(SyncJobRun, job_id)
            if (
                job_run is not None
                and job_run.job_type == "opportunity_rebuild"
                and job_run.finished_at is None
                and (datetime.now(UTC) - self._ensure_utc(job_run.started_at)) >= self.OPPORTUNITY_REBUILD_MAX_RUNTIME
            ):
                timeout_seconds = int(self.OPPORTUNITY_REBUILD_MAX_RUNTIME.total_seconds())
                if timeout_seconds >= 60 and timeout_seconds % 60 == 0:
                    timeout_label = f"{timeout_seconds // 60} minute"
                elif timeout_seconds >= 60:
                    timeout_label = f"{self.OPPORTUNITY_REBUILD_MAX_RUNTIME.total_seconds() / 60:.1f} minute"
                else:
                    timeout_label = f"{max(timeout_seconds, 1)} second"
                timeout_message = (
                    "Cancelled opportunity_rebuild after exceeding "
                    f"{timeout_label} runtime limit."
                )
                self._mark_job_cancelling(session, job_id, timeout_message)
                raise JobCancelledError(timeout_message)
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
        isolated: bool = False,
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

        if isolated:
            progress_session = self.session_factory()
            try:
                session = progress_session
                apply_progress()
                progress_session.commit()
            finally:
                progress_session.close()
            return

        apply_progress()
        session.commit()

    def _to_job_response(self, session: Session, job_run: SyncJobRun) -> SyncJobRunResponse:
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
            stages=[self._stage_response(stage_run) for stage_run in self._job_stage_rows(session, job_run.id)],
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
