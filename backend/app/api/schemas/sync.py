from datetime import datetime

from pydantic import BaseModel, Field


class SyncStatusCard(BaseModel):
    key: str
    label: str
    status: str
    last_successful_sync: datetime | None = None
    next_scheduled_sync: datetime | None = None
    recent_error_count: int = 0
    active_message: str | None = None
    progress_phase: str | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    progress_unit: str | None = None


class SyncJobStageRunResponse(BaseModel):
    id: int
    stage_key: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    metrics: dict[str, object] = Field(default_factory=dict)
    error_details: str | None = None


class SyncJobRunResponse(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None = None
    job_type: str
    status: str
    duration_ms: int | None = None
    records_processed: int = 0
    target_type: str | None = None
    target_id: str | None = None
    progress_phase: str | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    progress_unit: str | None = None
    message: str | None = None
    error_details: str | None = None
    stages: list[SyncJobStageRunResponse] = Field(default_factory=list)


class FallbackDiagnostic(BaseModel):
    structure_name: str
    structure_id: int
    demand_source: str
    coverage_pct: float


class ClearSyncDataResponse(BaseModel):
    job_type: str
    records_deleted: int
    message: str
