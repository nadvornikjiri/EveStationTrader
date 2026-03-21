import type { ChangeEvent } from "react";

import type { TargetLocation } from "../../types/trade";

type Props = {
  targets: TargetLocation[];
  targetId: number | null;
  periodDays: number;
  itemSearch: string;
  minRoi: string;
  warningThreshold: string;
  onTargetChange: (targetId: number) => void;
  onPeriodChange: (periodDays: number) => void;
  onItemSearchChange: (value: string) => void;
  onMinRoiChange: (value: string) => void;
  onWarningThresholdChange: (value: string) => void;
};

function readNumericValue(event: ChangeEvent<HTMLSelectElement | HTMLInputElement>) {
  return Number.parseInt(event.target.value, 10);
}

export function TradeControls({
  targets,
  targetId,
  periodDays,
  itemSearch,
  minRoi,
  warningThreshold,
  onTargetChange,
  onPeriodChange,
  onItemSearchChange,
  onMinRoiChange,
  onWarningThresholdChange,
}: Props) {
  return (
    <section className="panel controls-grid">
      <label>
        <span>Target Market</span>
        <select
          aria-label="Target Market"
          value={targetId ?? ""}
          onChange={(event) => onTargetChange(readNumericValue(event))}
        >
          {targets.map((target) => (
            <option key={target.location_id} value={target.location_id}>
              {target.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>Analysis Period</span>
        <select
          aria-label="Analysis Period"
          value={periodDays}
          onChange={(event) => onPeriodChange(readNumericValue(event))}
        >
          <option value={3}>3 days</option>
          <option value={7}>7 days</option>
          <option value={14}>14 days</option>
          <option value={30}>30 days</option>
        </select>
      </label>
      <label>
        <span>Item Search</span>
        <input
          aria-label="Item Search"
          value={itemSearch}
          placeholder="Search items"
          onChange={(event) => onItemSearchChange(event.target.value)}
        />
      </label>
      <label>
        <span>Min ROI</span>
        <input aria-label="Min ROI" value={minRoi} onChange={(event) => onMinRoiChange(event.target.value)} />
      </label>
      <label>
        <span>Warning Threshold</span>
        <input
          aria-label="Warning Threshold"
          value={warningThreshold}
          onChange={(event) => onWarningThresholdChange(event.target.value)}
        />
      </label>
      <div className="trade-filter-note" role="status">
        Filters apply to the item table using live query results for the selected target and analysis period.
      </div>
    </section>
  );
}
