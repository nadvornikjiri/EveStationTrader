from fastapi import APIRouter, HTTPException, Query

from app.api.schemas.sync import (
    ClearSyncDataResponse,
    FallbackDiagnostic,
    JobScheduleConfigResponse,
    JobScheduleConfigUpdate,
    PaginatedSyncJobsResponse,
    SyncJobRunResponse,
    SyncStatusCard,
)
from app.services.sync.service import SyncService

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/status", response_model=list[SyncStatusCard])
def get_sync_status() -> list[SyncStatusCard]:
    return SyncService().get_status()


@router.get("/jobs", response_model=PaginatedSyncJobsResponse)
def get_sync_jobs(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedSyncJobsResponse:
    jobs, total = SyncService().list_jobs(limit=limit, offset=offset)
    return PaginatedSyncJobsResponse(jobs=jobs, total=total)


@router.post("/run/{job_type}", response_model=SyncJobRunResponse)
def run_job(job_type: str) -> SyncJobRunResponse:
    return SyncService().enqueue_job(job_type)


@router.post("/clear/{job_type}", response_model=ClearSyncDataResponse)
def clear_job_data(job_type: str) -> ClearSyncDataResponse:
    try:
        return SyncService().clear_job_data(job_type)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/cancel/{job_id}", response_model=SyncJobRunResponse)
def cancel_job(job_id: int) -> SyncJobRunResponse:
    try:
        return SyncService().cancel_job(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/clear-stale-jobs")
def clear_stale_jobs() -> dict:
    count = SyncService().clear_stale_jobs()
    return {"cleared": count, "message": f"Cleared {count} stale job(s)." if count else "No stale jobs found."}


@router.get("/fallback-status", response_model=list[FallbackDiagnostic])
def get_fallback_status() -> list[FallbackDiagnostic]:
    return SyncService().get_fallback_status()


@router.get("/schedules", response_model=list[JobScheduleConfigResponse])
def get_schedules() -> list[JobScheduleConfigResponse]:
    return SyncService().get_schedule_configs()


@router.put("/schedules/{job_type}", response_model=JobScheduleConfigResponse)
def update_schedule(job_type: str, body: JobScheduleConfigUpdate) -> JobScheduleConfigResponse:
    try:
        return SyncService().update_schedule_config(job_type, body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
