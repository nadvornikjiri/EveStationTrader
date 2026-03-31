import type { ChangeEvent } from "react";

import type { TargetLocation } from "../../types/trade";

type Props = {
  targets: TargetLocation[];
  targetId: number | null;
  itemSearch: string;
  minProfit: string;
  minRoiNowPct: string;
  minDemandDay: string;
  maxDos: string;
  sourceType: string;
  minSecurity: string;
  demandSource: string;
  onTargetChange: (targetId: number) => void;
  onItemSearchChange: (value: string) => void;
  onMinProfitChange: (value: string) => void;
  onMinRoiNowPctChange: (value: string) => void;
  onMinDemandDayChange: (value: string) => void;
  onMaxDosChange: (value: string) => void;
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
  itemSearch,
  minProfit,
  minRoiNowPct,
  minDemandDay,
  maxDos,
  sourceType,
  minSecurity,
  demandSource,
  onTargetChange,
  onItemSearchChange,
  onMinProfitChange,
  onMinRoiNowPctChange,
  onMinDemandDayChange,
  onMaxDosChange,
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
        <span>Item Search</span>
        <input
          aria-label="Item Search"
          value={itemSearch}
          placeholder="Search items"
          onChange={(event) => onItemSearchChange(event.target.value)}
        />
      </label>
      <label>
        <span>Min Profit (ISK)</span>
        <input
          aria-label="Min Profit"
          type="number"
          inputMode="decimal"
          value={minProfit}
          placeholder="15000000"
          onChange={(event) => onMinProfitChange(event.target.value)}
        />
      </label>
      <label>
        <span>Min ROI Now %</span>
        <input
          aria-label="Min ROI Now Pct"
          type="number"
          inputMode="decimal"
          step="5"
          min="0"
          value={minRoiNowPct}
          placeholder="20"
          onChange={(event) => onMinRoiNowPctChange(event.target.value)}
        />
      </label>
      <label>
        <span>Min Demand/Day</span>
        <input
          aria-label="Min Demand Day"
          type="number"
          inputMode="decimal"
          step="0.1"
          min="0"
          value={minDemandDay}
          placeholder="1"
          onChange={(event) => onMinDemandDayChange(event.target.value)}
        />
      </label>
      <label>
        <span>Max D.O.S</span>
        <input
          aria-label="Max DOS"
          type="number"
          inputMode="decimal"
          step="0.1"
          min="0"
          value={maxDos}
          placeholder=""
          onChange={(event) => onMaxDosChange(event.target.value)}
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
        Analysis period follows settings. Min Profit filters `target now profit`, and Min ROI Now % filters `ROI Now`,
        so `20` means `ROI Now` must be above `20%`. Expand a source market row to inspect its item opportunities inline.
      </div>
    </section>
  );
}
