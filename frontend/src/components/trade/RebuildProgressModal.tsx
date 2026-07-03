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
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (isOpen) {
      setActiveJob(null);
      setElapsedSeconds(0);
    }
  }, [isOpen]);

  // Elapsed time counter
  useEffect(() => {
    if (!isOpen || isComplete || error !== null) {
      return;
    }

    const timer = setInterval(() => {
      if (rebuildStartedAt !== null) {
        setElapsedSeconds(Math.floor((Date.now() - rebuildStartedAt.getTime()) / 1000));
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [isOpen, rebuildStartedAt, isComplete, error]);

  // Poll for job progress
  useEffect(() => {
    if (!isOpen || isComplete || error !== null) {
      return;
    }

    const poll = async () => {
      try {
        const { jobs } = await getSyncJobs();
        const job = jobs.find(
          (j: SyncJobRun) =>
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
    }, 800);

    // Fire immediately on open
    void poll();

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

  const formatElapsed = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Rebuild progress">
      <div className="modal-panel">
        <h2>Rebuilding Target Opportunities</h2>

        {isComplete ? (
          <>
            <div className="rebuild-success-banner">
              Rebuild complete in {formatElapsed(elapsedSeconds)}
            </div>
          </>
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
            <p className="sync-progress-meta">
              {activeJob.progress_current != null && activeJob.progress_total != null
                ? `${activeJob.progress_current.toLocaleString()} / ${activeJob.progress_total.toLocaleString()} ${activeJob.progress_unit ?? "records"}`
                : activeJob.message ?? "Working..."
              }
              {" \u00b7 "}
              {formatElapsed(elapsedSeconds)}
            </p>
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
