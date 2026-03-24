import { FallbackDiagnosticsTable } from "../components/sync/FallbackDiagnosticsTable";
import { JobHistoryTable } from "../components/sync/JobHistoryTable";
import { ManualSyncActions } from "../components/sync/ManualSyncActions";
import { StatusCards } from "../components/sync/StatusCards";
import { useCancelSyncJob, useFallbackDiagnostics, useRunSyncJob, useSyncJobs, useSyncStatus } from "../hooks/useSyncData";

export function SyncPage() {
  const status = useSyncStatus();
  const jobs = useSyncJobs();
  const diagnostics = useFallbackDiagnostics();
  const runJob = useRunSyncJob();
  const cancelJob = useCancelSyncJob();
  const latestRun = runJob.data;
  const latestRunFailed = latestRun?.status === "failed";
  const latestRunSummary = latestRunFailed
    ? latestRun.error_details ?? latestRun.message ?? "The selected job failed."
    : latestRun?.message ?? null;

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Operations</span>
          <h1>Sync Dashboard</h1>
        </div>
      </header>
      <StatusCards cards={status.data ?? []} />
      {latestRunFailed ? (
        <section aria-live="assertive" className="sync-alert sync-alert-error" role="alert">
          <strong>Sync job failed:</strong> {latestRunSummary}
        </section>
      ) : null}
      <ManualSyncActions
        isPending={runJob.isPending}
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
