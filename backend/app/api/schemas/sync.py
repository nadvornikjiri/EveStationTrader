from datetime import datetime

from pydantic import BaseModel, Field


class SyncStatusCard(BaseModel):
    key: str
    label: str
    status: str
    health_color: str | None = None
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


class PaginatedSyncJobsResponse(BaseModel):
    jobs: list[SyncJobRunResponse] = Field(default_factory=list)
    total: int = 0


class FallbackDiagnostic(BaseModel):
    structure_name: str
    structure_id: int
    demand_source: str
    coverage_pct: float


class ClearSyncDataResponse(BaseModel):
    job_type: str
    records_deleted: int
    message: str


class JobScheduleConfigResponse(BaseModel):
    job_type: str
    label: str
    trigger_type: str
    interval_minutes: int | None = None
    cron_hour: int | None = None
    cron_minute: int | None = None
    enabled: bool = True


class JobScheduleConfigUpdate(BaseModel):
    trigger_type: str | None = None
    interval_minutes: int | None = None
    cron_hour: int | None = None
    cron_minute: int | None = None
    enabled: bool | None = None
