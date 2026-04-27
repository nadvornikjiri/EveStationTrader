import { useMemo } from "react";

import { FallbackDiagnosticsTable } from "../components/sync/FallbackDiagnosticsTable";
import { JobHistoryTable } from "../components/sync/JobHistoryTable";
import { ManualSyncActions } from "../components/sync/ManualSyncActions";
import { StatusCards } from "../components/sync/StatusCards";
import {
  useCancelSyncJob,
  useClearStaleJobs,
  useClearSyncData,
  useFallbackDiagnostics,
  useRunSyncJob,
  useSyncJobs,
  useSyncStatus,
} from "../hooks/useSyncData";
import type { SyncJobRun, SyncStatusCard } from "../types/sync";

function formatError(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }
  return fallback;
}

function mergeStatusCardsWithJobs(cards: SyncStatusCard[], jobs: SyncJobRun[]): SyncStatusCard[] {
  const activeJobsByType = new Map<string, SyncJobRun>();
  for (const job of jobs) {
    if (job.status !== "running" && job.status !== "cancelling") {
      continue
    }
    const existing = activeJobsByType.get(job.job_type);
    if (existing === undefined || new Date(job.started_at).getTime() > new Date(existing.started_at).getTime()) {
      activeJobsByType.set(job.job_type, job);
    }
  }

  return cards.map((card) => {
    const activeJob = activeJobsByType.get(card.key);
    if (activeJob === undefined) {
      return card;
    }
    return {
      ...card,
      status: activeJob.status === "cancelling" ? "degraded" : "running",
      active_message: activeJob.message,
      progress_phase: activeJob.progress_phase,
      progress_current: activeJob.progress_current,
      progress_total: activeJob.progress_total,
      progress_unit: activeJob.progress_unit,
    };
  });
}

export function SyncPage() {
  const status = useSyncStatus();
  const jobs = useSyncJobs();
  const diagnostics = useFallbackDiagnostics();
  const runJob = useRunSyncJob();
  const clearData = useClearSyncData();
  const cancelJob = useCancelSyncJob();
  const clearStale = useClearStaleJobs();
  const pendingJobType = runJob.isPending ? runJob.variables : null;
  const clearingJobType = clearData.isPending ? clearData.variables : null;
  const activeJobTypes = Array.from(
    new Set((jobs.data ?? []).filter((job) => job.status === "running" || job.status === "cancelling").map((job) => job.job_type)),
  );
  const latestRun = runJob.data;
  const latestClear = clearData.data;
  const latestRunFailed = latestRun?.status === "failed";
  const latestRunSummary = latestRunFailed
    ? latestRun.error_details ?? latestRun.message ?? "The selected job failed."
    : latestRun?.message ?? latestClear?.message ?? null;
  const runJobError = runJob.isError ? formatError(runJob.error, "Unable to start the selected sync job.") : null;
  const clearDataError = clearData.isError ? formatError(clearData.error, "Unable to clear the selected sync data.") : null;
  const cancelJobError = cancelJob.isError ? formatError(cancelJob.error, "Unable to cancel the selected sync job.") : null;
  const dashboardError = status.isError
    ? formatError(status.error, "Unable to load sync status.")
    : jobs.isError
      ? formatError(jobs.error, "Unable to load sync job history.")
      : diagnostics.isError
        ? formatError(diagnostics.error, "Unable to load fallback diagnostics.")
        : null;
  const displayedCards = useMemo(
    () => mergeStatusCardsWithJobs(status.data ?? [], jobs.data ?? []),
    [jobs.data, status.data],
  );

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Operations</span>
          <h1>Sync Dashboard</h1>
        </div>
      </header>
      {dashboardError ? (
        <section aria-live="assertive" className="sync-alert sync-alert-error" role="alert">
          <strong>Sync dashboard error:</strong> {dashboardError}
        </section>
      ) : null}
      <StatusCards cards={displayedCards} />
      {latestRunFailed ? (
        <section aria-live="assertive" className="sync-alert sync-alert-error" role="alert">
          <strong>Sync job failed:</strong> {latestRunSummary}
        </section>
      ) : null}
      {runJobError ? (
        <section aria-live="assertive" className="sync-alert sync-alert-error" role="alert">
          <strong>Unable to start sync job:</strong> {runJobError}
        </section>
      ) : null}
      {clearDataError ? (
        <section aria-live="assertive" className="sync-alert sync-alert-error" role="alert">
          <strong>Unable to clear sync data:</strong> {clearDataError}
        </section>
      ) : null}
      {cancelJobError ? (
        <section aria-live="assertive" className="sync-alert sync-alert-error" role="alert">
          <strong>Unable to cancel sync job:</strong> {cancelJobError}
        </section>
      ) : null}
      <ManualSyncActions
        onClear={(jobType) => clearData.mutate(jobType)}
        onClearStaleJobs={() => clearStale.mutate()}
        isPending={runJob.isPending}
        pendingJobType={pendingJobType}
        activeJobTypes={activeJobTypes}
        isClearing={clearData.isPending}
        clearingJobType={clearingJobType}
        isClearingStale={clearStale.isPending}
        lastMessage={latestRunSummary}
        onRun={(jobType) => runJob.mutate(jobType)}
      />
      <JobHistoryTable
        jobs={jobs.data ?? []}
        onCancel={(jobId) => cancelJob.mutate(jobId)}
        isCancelling={cancelJob.isPending}
      />
      <FallbackDiagnosticsTable rows={diagnostics.data ?? []} />
    </div>
  );
}
