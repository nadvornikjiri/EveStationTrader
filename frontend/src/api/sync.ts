import { apiGet, apiPost } from "./client";
import type { FallbackDiagnostic, SyncJobRun, SyncStatusCard } from "../types/sync";

export function getSyncStatus() {
  return apiGet<SyncStatusCard[]>("/sync/status");
}

export function getSyncJobs() {
  return apiGet<SyncJobRun[]>("/sync/jobs");
}

export function getFallbackDiagnostics() {
  return apiGet<FallbackDiagnostic[]>("/sync/fallback-status");
}

export function runSyncJob(jobType: string) {
  return apiPost<SyncJobRun>(`/sync/run/${jobType}`);
}
