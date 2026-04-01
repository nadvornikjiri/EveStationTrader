import { FallbackDiagnosticsTable } from "../components/sync/FallbackDiagnosticsTable";
import { JobHistoryTable } from "../components/sync/JobHistoryTable";
import { ManualSyncActions } from "../components/sync/ManualSyncActions";
import { StatusCards } from "../components/sync/StatusCards";
import {
  useCancelSyncJob,
  useClearSyncData,
  useFallbackDiagnostics,
  useRunSyncJob,
  useSyncJobs,
  useSyncStatus,
} from "../hooks/useSyncData";

function formatError(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }
  return fallback;
}

export function SyncPage() {
  const status = useSyncStatus();
  const jobs = useSyncJobs();
  const diagnostics = useFallbackDiagnostics();
  const runJob = useRunSyncJob();
  const clearData = useClearSyncData();
  const cancelJob = useCancelSyncJob();
  const pendingJobType = runJob.isPending ? runJob.variables : null;
  const clearingJobType = clearData.isPending ? clearData.variables : null;
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
      <StatusCards cards={status.data ?? []} />
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
        isPending={runJob.isPending}
        pendingJobType={pendingJobType}
        isClearing={clearData.isPending}
        clearingJobType={clearingJobType}
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
