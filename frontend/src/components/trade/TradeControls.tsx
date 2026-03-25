import type { ChangeEvent } from "react";

import type { TargetLocation } from "../../types/trade";

type Props = {
  targets: TargetLocation[];
  targetId: number | null;
  periodDays: number;
  itemSearch: string;
  minRoi: string;
  onTargetChange: (targetId: number) => void;
  onPeriodChange: (periodDays: number) => void;
  onItemSearchChange: (value: string) => void;
  onMinRoiChange: (value: string) => void;
};

function readNumericValue(event: ChangeEvent<HTMLSelectElement | HTMLInputElement>) {
  const parsed = Number.parseInt(event.target.value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}

export function TradeControls({
  targets,
  targetId,
  periodDays,
  itemSearch,
  minRoi,
  onTargetChange,
  onPeriodChange,
  onItemSearchChange,
  onMinRoiChange,
}: Props) {
  return (
    <section className="panel controls-grid trade-controls-grid">
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
        <input
          aria-label="Analysis Period"
          type="number"
          min={1}
          step={1}
          value={periodDays}
          onChange={(event) => onPeriodChange(readNumericValue(event))}
        />
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
      <div className="trade-filter-note" role="status">
        Filters apply to the item table using live query results for the selected target and analysis period.
      </div>
    </section>
  );
}
