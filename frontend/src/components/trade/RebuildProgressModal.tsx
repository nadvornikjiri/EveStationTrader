import { useEffect, useState } from "react";

import { getSyncJobs } from "../../api/sync";
import type { SyncJobRun } from "../../types/sync";

type Props = {
  isOpen: boolean;
  rebuildStartedAt: Date | null;
  isComplete: boolean;
  error: string | null;
  onClose: () => void;
};

export function RebuildProgressModal({ isOpen, rebuildStartedAt, isComplete, error, onClose }: Props) {
  const [activeJob, setActiveJob] = useState<SyncJobRun | null>(null);

  useEffect(() => {
    if (isOpen) {
      setActiveJob(null);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || isComplete || error !== null) {
      return;
    }

    const poll = async () => {
      try {
        const jobs = await getSyncJobs();
        const job = jobs.find(
          (j) =>
            j.job_type === "target_rebuild" &&
            rebuildStartedAt !== null &&
            new Date(j.started_at) >= rebuildStartedAt,
        );
        if (job) {
          setActiveJob(job);
        }
      } catch {
        // ignore poll errors — POST result is authoritative
      }
    };

    const interval = setInterval(() => {
      void poll();
    }, 1000);

    return () => clearInterval(interval);
  }, [isOpen, rebuildStartedAt, isComplete, error]);

  if (!isOpen) {
    return null;
  }

  const progressPercent =
    activeJob?.progress_current != null &&
    activeJob?.progress_total != null &&
    activeJob.progress_total > 0
      ? Math.max(0, Math.min(100, (activeJob.progress_current / activeJob.progress_total) * 100))
      : null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Rebuild progress">
      <div className="modal-panel">
        <h2>Rebuilding Target Opportunities</h2>

        {isComplete ? (
          <div className="rebuild-success-banner">Rebuild complete!</div>
        ) : error !== null ? (
          <div className="rebuild-error-message">{error}</div>
        ) : activeJob !== null ? (
          <div className="sync-progress-block">
            <p className="sync-progress-label">{activeJob.progress_phase ?? "Running"}</p>
            {progressPercent !== null ? (
              <div
                aria-label="Rebuild progress"
                aria-valuemax={activeJob.progress_total ?? 100}
                aria-valuemin={0}
                aria-valuenow={activeJob.progress_current ?? 0}
                className="sync-progress"
                role="progressbar"
              >
                <div className="sync-progress-fill" style={{ width: `${progressPercent}%` }} />
              </div>
            ) : null}
            {activeJob.progress_current !== null && activeJob.progress_total !== null ? (
              <p className="sync-progress-meta">
                {activeJob.progress_current.toLocaleString()} / {activeJob.progress_total.toLocaleString()}{" "}
                {activeJob.progress_unit ?? "records"}
              </p>
            ) : null}
          </div>
        ) : (
          <div className="rebuild-spinner">Starting rebuild...</div>
        )}

        <button type="button" className="modal-close-btn" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
