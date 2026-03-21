import { useEffect, useMemo, useState } from "react";

import { useOpportunityItems, useSourceSummaries, useTargets } from "../hooks/useTradeData";
import { ItemDetailPanel } from "../components/trade/ItemDetailPanel";
import { ItemOpportunityTable } from "../components/trade/ItemOpportunityTable";
import { SourceSummaryTable } from "../components/trade/SourceSummaryTable";
import { TradeControls } from "../components/trade/TradeControls";
import type { OpportunityItem } from "../types/trade";

type SortKey = "item_name" | "purchase_units" | "roi_now" | "confidence_score";
type SortDirection = "asc" | "desc";

function parseNumberInput(value: string, fallback: number) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function sortItems(rows: OpportunityItem[], sortKey: SortKey, sortDirection: SortDirection) {
  const sortedRows = [...rows].sort((left, right) => {
    if (sortKey === "item_name") {
      return left.item_name.localeCompare(right.item_name);
    }

    return left[sortKey] - right[sortKey];
  });

  return sortDirection === "asc" ? sortedRows : sortedRows.reverse();
}

export function TradePage() {
  const { data: targets = [] } = useTargets();
  const [targetId, setTargetId] = useState<number | null>(null);
  const [sourceId, setSourceId] = useState<number | null>(null);
  const [periodDays, setPeriodDays] = useState(14);
  const [itemSearch, setItemSearch] = useState("");
  const [minRoi, setMinRoi] = useState("0.05");
  const [warningThreshold, setWarningThreshold] = useState("50");
  const [sortKey, setSortKey] = useState<SortKey>("roi_now");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  useEffect(() => {
    if (targetId === null && targets.length > 0) {
      setTargetId(targets[0].location_id);
    }
  }, [targetId, targets]);

  const summaries = useSourceSummaries(targetId, periodDays);

  useEffect(() => {
    const availableSummaries = summaries.data ?? [];
    if (availableSummaries.length === 0) {
      if (sourceId !== null) {
        setSourceId(null);
      }
      return;
    }

    const hasSelectedSource = availableSummaries.some((summary) => summary.source_location_id === sourceId);
    if (!hasSelectedSource) {
      setSourceId(availableSummaries[0].source_location_id);
    }
  }, [sourceId, summaries.data]);

  const items = useOpportunityItems(targetId, sourceId, periodDays);

  const filteredItems = useMemo(() => {
    const searchValue = itemSearch.trim().toLowerCase();
    const minRoiValue = parseNumberInput(minRoi, 0);
    const warningThresholdValue = parseNumberInput(warningThreshold, 50) / 100;

    return (items.data ?? []).filter((row) => {
      const matchesSearch = searchValue.length === 0 || row.item_name.toLowerCase().includes(searchValue);
      const meetsRoi = row.roi_now >= minRoiValue;
      const withinWarningThreshold = row.risk_pct <= warningThresholdValue;
      return matchesSearch && meetsRoi && withinWarningThreshold;
    });
  }, [itemSearch, items.data, minRoi, warningThreshold]);

  const sortedItems = useMemo(
    () => sortItems(filteredItems, sortKey, sortDirection),
    [filteredItems, sortDirection, sortKey],
  );

  const handleSortChange = (nextSortKey: SortKey) => {
    if (nextSortKey === sortKey) {
      setSortDirection((currentDirection) => (currentDirection === "desc" ? "asc" : "desc"));
      return;
    }

    setSortKey(nextSortKey);
    setSortDirection(nextSortKey === "item_name" ? "asc" : "desc");
  };

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Trading Analysis</span>
          <h1>Regional Day Trader</h1>
        </div>
        <button
          className="refresh-button"
          onClick={() => {
            void summaries.refetch();
            void items.refetch();
          }}
        >
          Refresh
        </button>
      </header>
      <TradeControls
        targets={targets}
        targetId={targetId}
        periodDays={periodDays}
        itemSearch={itemSearch}
        minRoi={minRoi}
        warningThreshold={warningThreshold}
        onTargetChange={setTargetId}
        onPeriodChange={setPeriodDays}
        onItemSearchChange={setItemSearch}
        onMinRoiChange={setMinRoi}
        onWarningThresholdChange={setWarningThreshold}
      />
      <SourceSummaryTable
        rows={summaries.data ?? []}
        selectedSourceId={sourceId}
        onSelectSource={setSourceId}
      />
      <div className="trade-lower-grid">
        <ItemOpportunityTable
          rows={sortedItems}
          sortKey={sortKey}
          sortDirection={sortDirection}
          onSortChange={handleSortChange}
        />
        <ItemDetailPanel />
      </div>
    </div>
  );
}
