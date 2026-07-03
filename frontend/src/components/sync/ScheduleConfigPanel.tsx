import { useState } from "react";

import type { JobScheduleConfig, JobScheduleConfigUpdate } from "../../types/sync";

type Props = {
  configs: JobScheduleConfig[];
  onUpdate: (args: { jobType: string; update: JobScheduleConfigUpdate }) => void;
  isUpdating: boolean;
};

const INTERVAL_OPTIONS = [5, 10, 15, 20, 30, 45, 60, 120, 180, 240, 360, 720, 1440];
const HOUR_OPTIONS = Array.from({ length: 24 }, (_, i) => i);

function formatInterval(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function formatHour(hour: number): string {
  return `${hour.toString().padStart(2, "0")}:00 UTC`;
}

export function ScheduleConfigPanel({ configs, onUpdate, isUpdating }: Props) {
  const [editingJob, setEditingJob] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<JobScheduleConfigUpdate>({});

  const startEditing = (config: JobScheduleConfig) => {
    setEditingJob(config.job_type);
    setEditValues({
      trigger_type: config.trigger_type,
      interval_minutes: config.interval_minutes ?? undefined,
      cron_hour: config.cron_hour ?? undefined,
      cron_minute: config.cron_minute ?? undefined,
      enabled: config.enabled,
    });
  };

  const cancelEditing = () => {
    setEditingJob(null);
    setEditValues({});
  };

  const saveEditing = (jobType: string) => {
    onUpdate({ jobType, update: editValues });
    setEditingJob(null);
    setEditValues({});
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Job Schedules</h2>
        <span>Configure when each job runs. Changes apply within 5 minutes.</span>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Job</th>
              <th>Type</th>
              <th>Schedule</th>
              <th>Enabled</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {configs.map((config) => {
              const isEditing = editingJob === config.job_type;

              if (isEditing) {
                const triggerType = editValues.trigger_type ?? config.trigger_type;
                return (
                  <tr key={config.job_type}>
                    <td>{config.label}</td>
                    <td>
                      <select
                        className="schedule-select"
                        value={triggerType}
                        onChange={(e) =>
                          setEditValues((v) => ({ ...v, trigger_type: e.target.value }))
                        }
                      >
                        <option value="interval">Interval</option>
                        <option value="cron">Daily (cron)</option>
                      </select>
                    </td>
                    <td>
                      {triggerType === "interval" ? (
                        <select
                          className="schedule-select"
                          value={editValues.interval_minutes ?? config.interval_minutes ?? 60}
                          onChange={(e) =>
                            setEditValues((v) => ({
                              ...v,
                              interval_minutes: parseInt(e.target.value, 10),
                            }))
                          }
                        >
                          {INTERVAL_OPTIONS.map((m) => (
                            <option key={m} value={m}>
                              Every {formatInterval(m)}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <select
                          className="schedule-select"
                          value={editValues.cron_hour ?? config.cron_hour ?? 0}
                          onChange={(e) =>
                            setEditValues((v) => ({
                              ...v,
                              cron_hour: parseInt(e.target.value, 10),
                              cron_minute: 0,
                            }))
                          }
                        >
                          {HOUR_OPTIONS.map((h) => (
                            <option key={h} value={h}>
                              {formatHour(h)}
                            </option>
                          ))}
                        </select>
                      )}
                    </td>
                    <td>
                      <input
                        type="checkbox"
                        checked={editValues.enabled ?? config.enabled}
                        onChange={(e) =>
                          setEditValues((v) => ({ ...v, enabled: e.target.checked }))
                        }
                      />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="refresh-button"
                        disabled={isUpdating}
                        onClick={() => saveEditing(config.job_type)}
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        className="refresh-button clear-button"
                        onClick={cancelEditing}
                        style={{ marginLeft: 6 }}
                      >
                        Cancel
                      </button>
                    </td>
                  </tr>
                );
              }

              const scheduleLabel =
                config.trigger_type === "interval" && config.interval_minutes
                  ? `Every ${formatInterval(config.interval_minutes)}`
                  : config.trigger_type === "cron" && config.cron_hour !== null
                    ? `Daily at ${formatHour(config.cron_hour)}`
                    : "—";

              return (
                <tr key={config.job_type}>
                  <td>{config.label}</td>
                  <td>{config.trigger_type === "interval" ? "Interval" : "Daily (cron)"}</td>
                  <td>{scheduleLabel}</td>
                  <td>{config.enabled ? "Yes" : "No"}</td>
                  <td>
                    <button
                      type="button"
                      className="refresh-button"
                      onClick={() => startEditing(config)}
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
