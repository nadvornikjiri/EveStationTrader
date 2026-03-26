import { useEffect, useMemo, useState } from "react";

import {
  useOpportunityItemDetail,
  useOpportunityItems,
  useSourceSummaries,
  useTargets,
} from "../hooks/useTradeData";
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

function securityThreshold(minSecurity: string): number {
  switch (minSecurity) {
    case "highsec":
      return 0.5;
    case "lowsec":
      return 0.0;
    case "nullsec":
      return -10.0;
    default:
      return -10.0;
  }
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
  const [minProfit, setMinProfit] = useState("");
  const [minMarginPct, setMinMarginPct] = useState("");
  const [minDemandDay, setMinDemandDay] = useState("1");
  const [maxDos, setMaxDos] = useState("");
  const [minConfidence, setMinConfidence] = useState("");
  const [sourceType, setSourceType] = useState("all");
  const [minSecurity, setMinSecurity] = useState("all");
  const [demandSource, setDemandSource] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("roi_now");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [selectedTypeId, setSelectedTypeId] = useState<number | null>(null);

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
    const minProfitValue = parseNumberInput(minProfit, 0);
    const minMarginPctValue = parseNumberInput(minMarginPct, 0) / 100;
    const minDemandDayValue = parseNumberInput(minDemandDay, 0);
    const maxDosValue = parseNumberInput(maxDos, Infinity);
    const minConfidenceValue = parseNumberInput(minConfidence, 0);
    const secThreshold = securityThreshold(minSecurity);

    return (items.data ?? []).filter((row) => {
      const matchesSearch = searchValue.length === 0 || row.item_name.toLowerCase().includes(searchValue);
      const meetsRoi = row.roi_now >= minRoiValue;
      const meetsProfit = row.target_now_profit >= minProfitValue;
      const meetsMargin =
        minMarginPctValue <= 0 ||
        (row.source_station_sell_price > 0 &&
          row.target_now_profit / row.source_station_sell_price >= minMarginPctValue);
      const meetsDemand = row.target_demand_day >= minDemandDayValue;
      const meetsDos = row.target_dos <= maxDosValue;
      const meetsConfidence = row.confidence_score >= minConfidenceValue;
      const meetsSecurity = row.source_security_status >= secThreshold;
      const meetsDemandSource = demandSource === "all" || row.demand_source === demandSource;
      return (
        matchesSearch &&
        meetsRoi &&
        meetsProfit &&
        meetsMargin &&
        meetsDemand &&
        meetsDos &&
        meetsConfidence &&
        meetsSecurity &&
        meetsDemandSource
      );
    });
  }, [itemSearch, items.data, minRoi, minProfit, minMarginPct, minDemandDay, maxDos, minConfidence, minSecurity, demandSource]);

  const sortedItems = useMemo(
    () => sortItems(filteredItems, sortKey, sortDirection),
    [filteredItems, sortDirection, sortKey],
  );

  useEffect(() => {
    if (sortedItems.length === 0) {
      if (selectedTypeId !== null) {
        setSelectedTypeId(null);
      }
      return;
    }

    const hasSelectedItem = sortedItems.some((row) => row.type_id === selectedTypeId);
    if (!hasSelectedItem) {
      setSelectedTypeId(sortedItems[0].type_id);
    }
  }, [selectedTypeId, sortedItems]);

  const itemDetail = useOpportunityItemDetail(targetId, sourceId, selectedTypeId, periodDays);

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
        minProfit={minProfit}
        minMarginPct={minMarginPct}
        minDemandDay={minDemandDay}
        maxDos={maxDos}
        minConfidence={minConfidence}
        sourceType={sourceType}
        minSecurity={minSecurity}
        demandSource={demandSource}
        onTargetChange={setTargetId}
        onPeriodChange={setPeriodDays}
        onItemSearchChange={setItemSearch}
        onMinRoiChange={setMinRoi}
        onMinProfitChange={setMinProfit}
        onMinMarginPctChange={setMinMarginPct}
        onMinDemandDayChange={setMinDemandDay}
        onMaxDosChange={setMaxDos}
        onMinConfidenceChange={setMinConfidence}
        onSourceTypeChange={setSourceType}
        onMinSecurityChange={setMinSecurity}
        onDemandSourceChange={setDemandSource}
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
          selectedTypeId={selectedTypeId}
          onSortChange={handleSortChange}
          onSelectItem={setSelectedTypeId}
        />
        <ItemDetailPanel detail={itemDetail.data} isLoading={itemDetail.isLoading} />
      </div>
    </div>
  );
}
