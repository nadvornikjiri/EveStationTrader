import type { SyncJobRun } from "../../types/sync";

type Props = {
  jobs: SyncJobRun[];
};

export function JobHistoryTable({ jobs }: Props) {
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
            <th>Duration</th>
            <th>Records</th>
            <th>Message</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>{new Date(job.started_at).toLocaleString()}</td>
              <td>{job.job_type}</td>
              <td>{job.status}</td>
              <td>{job.duration_ms ? `${job.duration_ms} ms` : "Pending"}</td>
              <td>{job.records_processed}</td>
              <td>{job.message ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
