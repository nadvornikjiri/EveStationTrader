type Props = {
  onRun: (jobType: string) => void;
  onClear: (jobType: string) => void;
  onClearStaleJobs: () => void;
  isPending: boolean;
  pendingJobType?: string | null;
  activeJobTypes?: string[];
  isClearing: boolean;
  clearingJobType?: string | null;
  isClearingStale?: boolean;
  lastMessage?: string | null;
};

const actions = [
  {
    key: "foundation_import_sync",
    runLabel: "Import SDE Data Now",
    clearLabel: "Clear SDE Data",
  },
  {
    key: "adam4eve_sync",
    runLabel: "Sync Adam4EVE Now",
    clearLabel: "Clear Adam4EVE Data",
  },
  {
    key: "esi_market_orders_sync",
    runLabel: "Sync NPC Orders + Split Estimation Now",
    clearLabel: "Clear NPC Orders Data",
  },
  {
    key: "everef_history_sync",
    runLabel: "Sync EVE Ref History Now",
    clearLabel: "Clear EVE Ref History Data",
  },
  {
    key: "structure_snapshot_sync",
    runLabel: "Sync Tracked Structures Now",
    clearLabel: "Clear Tracked Structures Data",
  },
  {
    key: "character_sync",
    runLabel: "Sync All Characters Now",
    clearLabel: "Clear Character Sync Data",
  },
  {
    key: "opportunity_rebuild",
    runLabel: "Rebuild All Opportunities Now",
    clearLabel: "Clear Opportunity Data",
  },
];

export function ManualSyncActions({
  onRun,
  onClear,
  onClearStaleJobs,
  isPending,
  pendingJobType,
  activeJobTypes = [],
  isClearing,
  clearingJobType,
  isClearingStale = false,
  lastMessage,
}: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Manual Sync Actions</h2>
        <span>{lastMessage ?? "Choose a job to enqueue or run."}</span>
      </div>
      <div style={{ marginBottom: "0.5rem" }}>
        <button
          className="refresh-button clear-button"
          disabled={isClearingStale}
          onClick={onClearStaleJobs}
          type="button"
        >
          {isClearingStale ? "Clearing stale jobs..." : "Clear Stale Jobs"}
        </button>
      </div>
      <div className="action-grid clear-action-grid">
        {actions.map((action) => (
          <button
            key={`${action.key}-clear`}
            className="refresh-button clear-button"
            disabled={isClearing}
            onClick={() => onClear(action.key)}
            type="button"
          >
            {isClearing && clearingJobType === action.key
              ? `Clearing ${action.clearLabel.replace(/^Clear /, "")}...`
              : action.clearLabel}
          </button>
        ))}
      </div>
      <div className="action-grid">
        {actions.map((action) => (
          (() => {
            const isActive = activeJobTypes.includes(action.key);
            const isDisabled = isPending || isActive;
            let label = action.runLabel;
            if (isPending && pendingJobType === action.key) {
              label = `Starting ${action.runLabel}...`;
            } else if (isActive) {
              label = `${action.runLabel} Already Running`;
            }

            return (
              <button
                key={action.key}
                className="refresh-button"
                disabled={isDisabled}
                onClick={() => onRun(action.key)}
                type="button"
              >
                {label}
              </button>
            );
          })()
        ))}
      </div>
    </section>
  );
}
