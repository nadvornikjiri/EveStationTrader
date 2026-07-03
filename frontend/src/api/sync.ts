import { apiGet, apiPost, apiPut } from "./client";
import type { ClearSyncDataResponse, FallbackDiagnostic, JobScheduleConfig, JobScheduleConfigUpdate, PaginatedSyncJobs, SyncJobRun, SyncStatusCard } from "../types/sync";

export function getSyncStatus() {
  return apiGet<SyncStatusCard[]>("/sync/status");
}

export function getSyncJobs(limit = 25, offset = 0) {
  return apiGet<PaginatedSyncJobs>(`/sync/jobs?limit=${limit}&offset=${offset}`);
}

export function getFallbackDiagnostics() {
  return apiGet<FallbackDiagnostic[]>("/sync/fallback-status");
}

export function runSyncJob(jobType: string) {
  return apiPost<SyncJobRun>(`/sync/run/${jobType}`);
}

export function clearSyncData(jobType: string) {
  return apiPost<ClearSyncDataResponse>(`/sync/clear/${jobType}`);
}

export function cancelSyncJob(jobId: number) {
  return apiPost<SyncJobRun>(`/sync/cancel/${jobId}`);
}

export function clearStaleJobs() {
  return apiPost<{ cleared: number; message: string }>("/sync/clear-stale-jobs");
}

export function getScheduleConfigs() {
  return apiGet<JobScheduleConfig[]>("/sync/schedules");
}

export function updateScheduleConfig(args: { jobType: string; update: JobScheduleConfigUpdate }) {
  return apiPut<JobScheduleConfig>(`/sync/schedules/${args.jobType}`, args.update);
}
