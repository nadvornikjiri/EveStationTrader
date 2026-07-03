export type SyncStatusCard = {
  key: string;
  label: string;
  status: string;
  health_color: "green" | "yellow" | "red" | null;
  last_successful_sync: string | null;
  next_scheduled_sync: string | null;
  recent_error_count: number;
  active_message: string | null;
  progress_phase: string | null;
  progress_current: number | null;
  progress_total: number | null;
  progress_unit: string | null;
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
  progress_phase: string | null;
  progress_current: number | null;
  progress_total: number | null;
  progress_unit: string | null;
  message: string | null;
  error_details: string | null;
};

export type PaginatedSyncJobs = {
  jobs: SyncJobRun[];
  total: number;
};

export type FallbackDiagnostic = {
  structure_name: string;
  structure_id: number;
  demand_source: string;
  coverage_pct: number;
};

export type ClearSyncDataResponse = {
  job_type: string;
  records_deleted: number;
  message: string;
};

export type JobScheduleConfig = {
  job_type: string;
  label: string;
  trigger_type: "interval" | "cron";
  interval_minutes: number | null;
  cron_hour: number | null;
  cron_minute: number | null;
  enabled: boolean;
};

export type JobScheduleConfigUpdate = {
  trigger_type?: string;
  interval_minutes?: number;
  cron_hour?: number;
  cron_minute?: number;
  enabled?: boolean;
};
