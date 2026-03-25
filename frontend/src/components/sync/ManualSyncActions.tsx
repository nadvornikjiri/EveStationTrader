type Props = {
  onRun: (jobType: string) => void;
  isPending: boolean;
  lastMessage?: string | null;
};

const actions = [
  { key: "foundation_seed_sync", label: "Seed Foundation Data" },
  { key: "foundation_import_sync", label: "Import SDE Data Now" },
  { key: "adam4eve_sync", label: "Sync Adam4EVE Now" },
  { key: "esi_market_orders_sync", label: "Sync NPC Orders Now" },
  { key: "structure_snapshot_sync", label: "Sync Tracked Structures Now" },
  { key: "character_sync", label: "Sync All Characters Now" },
  { key: "opportunity_rebuild", label: "Rebuild Opportunities Now" },
];

export function ManualSyncActions({ onRun, isPending, lastMessage }: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Manual Sync Actions</h2>
        <span>{lastMessage ?? "Choose a job to enqueue or run."}</span>
      </div>
      <div className="action-grid">
        {actions.map((action) => (
          <button
            key={action.key}
            className="refresh-button"
            disabled={isPending}
            onClick={() => onRun(action.key)}
            type="button"
          >
            {action.label}
          </button>
        ))}
      </div>
    </section>
  );
}
