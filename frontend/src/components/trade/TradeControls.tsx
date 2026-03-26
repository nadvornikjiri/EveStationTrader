import type { ChangeEvent } from "react";

import type { TargetLocation } from "../../types/trade";

type Props = {
  targets: TargetLocation[];
  targetId: number | null;
  periodDays: number;
  itemSearch: string;
  minRoi: string;
  minProfit: string;
  minMarginPct: string;
  minDemandDay: string;
  maxDos: string;
  minConfidence: string;
  sourceType: string;
  minSecurity: string;
  demandSource: string;
  onTargetChange: (targetId: number) => void;
  onPeriodChange: (periodDays: number) => void;
  onItemSearchChange: (value: string) => void;
  onMinRoiChange: (value: string) => void;
  onMinProfitChange: (value: string) => void;
  onMinMarginPctChange: (value: string) => void;
  onMinDemandDayChange: (value: string) => void;
  onMaxDosChange: (value: string) => void;
  onMinConfidenceChange: (value: string) => void;
  onSourceTypeChange: (value: string) => void;
  onMinSecurityChange: (value: string) => void;
  onDemandSourceChange: (value: string) => void;
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
  minProfit,
  minMarginPct,
  minDemandDay,
  maxDos,
  minConfidence,
  sourceType,
  minSecurity,
  demandSource,
  onTargetChange,
  onPeriodChange,
  onItemSearchChange,
  onMinRoiChange,
  onMinProfitChange,
  onMinMarginPctChange,
  onMinDemandDayChange,
  onMaxDosChange,
  onMinConfidenceChange,
  onSourceTypeChange,
  onMinSecurityChange,
  onDemandSourceChange,
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
      <label>
        <span>Min Profit (ISK)</span>
        <input
          aria-label="Min Profit"
          value={minProfit}
          placeholder="15000000"
          onChange={(event) => onMinProfitChange(event.target.value)}
        />
      </label>
      <label>
        <span>Min Margin %</span>
        <input
          aria-label="Min Margin Pct"
          value={minMarginPct}
          placeholder="20"
          onChange={(event) => onMinMarginPctChange(event.target.value)}
        />
      </label>
      <label>
        <span>Min Demand/Day</span>
        <input
          aria-label="Min Demand Day"
          value={minDemandDay}
          placeholder="1"
          onChange={(event) => onMinDemandDayChange(event.target.value)}
        />
      </label>
      <label>
        <span>Max D.O.S</span>
        <input
          aria-label="Max DOS"
          value={maxDos}
          placeholder=""
          onChange={(event) => onMaxDosChange(event.target.value)}
        />
      </label>
      <label>
        <span>Min Confidence</span>
        <input
          aria-label="Min Confidence"
          value={minConfidence}
          placeholder=""
          onChange={(event) => onMinConfidenceChange(event.target.value)}
        />
      </label>
      <label>
        <span>Source Type</span>
        <select aria-label="Source Type" value={sourceType} onChange={(event) => onSourceTypeChange(event.target.value)}>
          <option value="all">All</option>
          <option value="npc">NPC Stations</option>
          <option value="structure">Structures</option>
        </select>
      </label>
      <label>
        <span>Min Security</span>
        <select
          aria-label="Min Security"
          value={minSecurity}
          onChange={(event) => onMinSecurityChange(event.target.value)}
        >
          <option value="all">All</option>
          <option value="highsec">High Sec (≥0.5)</option>
          <option value="lowsec">Low Sec (≥0.0)</option>
          <option value="nullsec">Null Sec</option>
        </select>
      </label>
      <label>
        <span>Demand Source</span>
        <select
          aria-label="Demand Source"
          value={demandSource}
          onChange={(event) => onDemandSourceChange(event.target.value)}
        >
          <option value="all">All</option>
          <option value="adam4eve">Adam4EVE</option>
          <option value="local_structure">Local</option>
          <option value="regional_fallback">Fallback</option>
          <option value="blended">Blended</option>
        </select>
      </label>
      <div className="trade-filter-note" role="status">
        Filters apply to the item table using live query results for the selected target and analysis period.
      </div>
    </section>
  );
}
