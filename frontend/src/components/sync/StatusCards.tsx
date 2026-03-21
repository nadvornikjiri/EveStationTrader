import type { SyncStatusCard } from "../../types/sync";

type Props = {
  cards: SyncStatusCard[];
};

function formatTimestamp(value: string | null) {
  return value ? new Date(value).toLocaleString() : "N/A";
}

export function StatusCards({ cards }: Props) {
  return (
    <section className="card-grid">
      {cards.map((card) => (
        <article key={card.key} className="panel status-card">
          <span className="eyebrow">{card.status}</span>
          <h2>{card.label}</h2>
          <p>Last success: {formatTimestamp(card.last_successful_sync)}</p>
          <p>Next run: {formatTimestamp(card.next_scheduled_sync)}</p>
          <p>Recent errors: {card.recent_error_count}</p>
        </article>
      ))}
    </section>
  );
}
