import type { SyncJobRun } from "../../types/sync";

type Props = {
  jobs: SyncJobRun[];
  total: number;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
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
  if (job.progress_unit === "bytes") {
    const currentMB = (job.progress_current / 1_048_576).toFixed(1);
    const totalMB = (job.progress_total / 1_048_576).toFixed(1);
    return `${currentMB} / ${totalMB} MB`;
  }
  return `${job.progress_current.toLocaleString()} / ${job.progress_total.toLocaleString()} ${job.progress_unit ?? "records"}`;
}

export function JobHistoryTable({ jobs, total, page, totalPages, onPageChange, onCancel, isCancelling }: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Job History</h2>
        <span>{total} total jobs</span>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Started</th>
              <th>Job Type</th>
              <th>Status</th>
              <th>Progress</th>
              <th>Duration</th>
              <th>Records</th>
              <th className="job-history-message-col">Message</th>
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
                <td className="job-history-message-col">{job.message ?? "-"}</td>
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
      </div>
      {totalPages > 1 ? (
        <div className="pagination-panel" style={{ display: "flex", alignItems: "center", gap: "12px", padding: "12px 0" }}>
          <button
            type="button"
            className="inline-more-button"
            disabled={page === 0}
            onClick={() => onPageChange(0)}
          >
            First
          </button>
          <button
            type="button"
            className="inline-more-button"
            disabled={page === 0}
            onClick={() => onPageChange(page - 1)}
          >
            ← Prev
          </button>
          <span>
            Page {page + 1} of {totalPages}
          </span>
          <button
            type="button"
            className="inline-more-button"
            disabled={page >= totalPages - 1}
            onClick={() => onPageChange(page + 1)}
          >
            Next →
          </button>
          <button
            type="button"
            className="inline-more-button"
            disabled={page >= totalPages - 1}
            onClick={() => onPageChange(totalPages - 1)}
          >
            Last
          </button>
        </div>
      ) : null}
    </section>
  );
}
