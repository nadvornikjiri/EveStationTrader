from fastapi import APIRouter

from app.api.schemas.sync import FallbackDiagnostic, SyncJobRunResponse, SyncStatusCard
from app.services.sync.service import SyncService

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/status", response_model=list[SyncStatusCard])
def get_sync_status() -> list[SyncStatusCard]:
    return SyncService().get_status()


@router.get("/jobs", response_model=list[SyncJobRunResponse])
def get_sync_jobs() -> list[SyncJobRunResponse]:
    return SyncService().list_jobs()


@router.post("/run/{job_type}", response_model=SyncJobRunResponse)
def run_job(job_type: str) -> SyncJobRunResponse:
    return SyncService().trigger_job(job_type)


@router.get("/fallback-status", response_model=list[FallbackDiagnostic])
def get_fallback_status() -> list[FallbackDiagnostic]:
    return SyncService().get_fallback_status()
