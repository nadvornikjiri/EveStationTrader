from datetime import datetime

from pydantic import BaseModel


class SyncStatusCard(BaseModel):
    key: str
    label: str
    status: str
    last_successful_sync: datetime | None = None
    next_scheduled_sync: datetime | None = None
    recent_error_count: int = 0


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
    message: str | None = None
    error_details: str | None = None


class FallbackDiagnostic(BaseModel):
    structure_name: str
    structure_id: int
    demand_source: str
    confidence_score: float
    coverage_pct: float
