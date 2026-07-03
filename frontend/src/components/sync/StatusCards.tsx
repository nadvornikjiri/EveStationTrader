import type { SyncStatusCard } from "../../types/sync";

type Props = {
  cards: SyncStatusCard[];
};

function formatTimestamp(value: string | null) {
  return value ? new Date(value).toLocaleString() : "N/A";
}

function formatProgress(current: number | null, total: number | null, unit: string | null) {
  if (current === null || total === null) {
    return null;
  }
  if (unit === "bytes") {
    const currentMB = (current / 1_048_576).toFixed(1);
    const totalMB = (total / 1_048_576).toFixed(1);
    return `${currentMB} / ${totalMB} MB`;
  }
  return `${current.toLocaleString()} / ${total.toLocaleString()} ${unit ?? "records"}`;
}

function progressPercent(current: number | null, total: number | null) {
  if (current === null || total === null || total <= 0) {
    return null;
  }
  return Math.max(0, Math.min(100, (current / total) * 100));
}

export function StatusCards({ cards }: Props) {
  return (
    <section className="card-grid">
      {cards.map((card) => (
        <article
          key={card.key}
          className={`panel status-card${card.health_color ? ` status-card-${card.health_color}` : ""}`}
        >
          <span className="sync-health-line">
            <span className="eyebrow">{card.status}</span>
            {card.health_color ? (
              <span aria-label={`${card.label} health ${card.health_color}`} className="sync-health-dot" />
            ) : null}
          </span>
          <h2>{card.label}</h2>
          <p>Last success: {formatTimestamp(card.last_successful_sync)}</p>
          <p>Next run: {formatTimestamp(card.next_scheduled_sync)}</p>
          <p>Recent errors: {card.recent_error_count}</p>
          {card.progress_current !== null && card.progress_total !== null ? (
            <div className="sync-progress-block">
              <p className="sync-progress-label">{card.progress_phase ?? "Running"}</p>
              <div
                aria-label={`${card.label} progress`}
                aria-valuemax={card.progress_total}
                aria-valuemin={0}
                aria-valuenow={card.progress_current}
                className="sync-progress"
                role="progressbar"
              >
                <div
                  className="sync-progress-fill"
                  style={{ width: `${progressPercent(card.progress_current, card.progress_total) ?? 0}%` }}
                />
              </div>
              <p className="sync-progress-meta">
                {formatProgress(card.progress_current, card.progress_total, card.progress_unit)}
              </p>
            </div>
          ) : null}
          {card.active_message ? <p>{card.active_message}</p> : null}
        </article>
      ))}
    </section>
  );
}
