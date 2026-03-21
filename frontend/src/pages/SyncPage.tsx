import { FallbackDiagnosticsTable } from "../components/sync/FallbackDiagnosticsTable";
import { JobHistoryTable } from "../components/sync/JobHistoryTable";
import { ManualSyncActions } from "../components/sync/ManualSyncActions";
import { StatusCards } from "../components/sync/StatusCards";
import { useFallbackDiagnostics, useRunSyncJob, useSyncJobs, useSyncStatus } from "../hooks/useSyncData";

export function SyncPage() {
  const status = useSyncStatus();
  const jobs = useSyncJobs();
  const diagnostics = useFallbackDiagnostics();
  const runJob = useRunSyncJob();

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Operations</span>
          <h1>Sync Dashboard</h1>
        </div>
      </header>
      <StatusCards cards={status.data ?? []} />
      <ManualSyncActions
        isPending={runJob.isPending}
        lastMessage={runJob.data?.message}
        onRun={(jobType) => runJob.mutate(jobType)}
      />
      <JobHistoryTable jobs={jobs.data ?? []} />
      <FallbackDiagnosticsTable rows={diagnostics.data ?? []} />
    </div>
  );
}
