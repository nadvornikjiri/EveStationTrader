import type { SyncJobRun } from "../../types/sync";

type Props = {
  jobs: SyncJobRun[];
  onCancel: (jobId: number) => void;
  isCancelling: boolean;
};

function canCancel(status: string) {
  return status === "running" || status === "cancelling";
}

function progressPercent(current: number | null, total: number | null) {
  if (current === null || total === null || total <= 0) {
    return null;
  }
  return Math.max(0, Math.min(100, (current / total) * 100));
}

function formatProgress(job: SyncJobRun) {
  if (job.progress_current === null || job.progress_total === null) {
    return null;
  }
  return `${job.progress_current.toLocaleString()} / ${job.progress_total.toLocaleString()} ${job.progress_unit ?? "records"}`;
}

export function JobHistoryTable({ jobs, onCancel, isCancelling }: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Job History</h2>
        <span>{jobs.length} recent jobs</span>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Started</th>
            <th>Job Type</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Duration</th>
            <th>Records</th>
            <th>Message</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>{new Date(job.started_at).toLocaleString()}</td>
              <td>{job.job_type}</td>
              <td>{job.status}</td>
              <td>
                {job.progress_current !== null && job.progress_total !== null ? (
                  <div className="sync-progress-block">
                    <p className="sync-progress-label">{job.progress_phase ?? "Running"}</p>
                    <div
                      aria-label={`${job.job_type} progress`}
                      aria-valuemax={job.progress_total}
                      aria-valuemin={0}
                      aria-valuenow={job.progress_current}
                      className="sync-progress"
                      role="progressbar"
                    >
                      <div
                        className="sync-progress-fill"
                        style={{ width: `${progressPercent(job.progress_current, job.progress_total) ?? 0}%` }}
                      />
                    </div>
                    <p className="sync-progress-meta">{formatProgress(job)}</p>
                  </div>
                ) : (
                  "-"
                )}
              </td>
              <td>{job.duration_ms ? `${job.duration_ms} ms` : "Pending"}</td>
              <td>{job.records_processed}</td>
              <td>{job.message ?? "-"}</td>
              <td>
                {canCancel(job.status) ? (
                  <button
                    className="refresh-button"
                    disabled={isCancelling || job.status === "cancelling"}
                    onClick={() => onCancel(job.id)}
                    type="button"
                  >
                    {job.status === "cancelling" ? "Cancelling" : "Cancel"}
                  </button>
                ) : (
                  "-"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
