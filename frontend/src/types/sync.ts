export type SyncStatusCard = {
  key: string;
  label: string;
  status: string;
  last_successful_sync: string | null;
  next_scheduled_sync: string | null;
  recent_error_count: number;
};

export type SyncJobRun = {
  id: number;
  started_at: string;
  finished_at: string | null;
  job_type: string;
  status: string;
  duration_ms: number | null;
  records_processed: number;
  target_type: string | null;
  target_id: string | null;
  message: string | null;
  error_details: string | null;
};

export type FallbackDiagnostic = {
  structure_name: string;
  structure_id: number;
  demand_source: string;
  confidence_score: number;
  coverage_pct: number;
};
