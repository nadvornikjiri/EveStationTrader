import { startTransition, useEffect, useMemo, useState } from "react";

import { refreshTradeOpportunities } from "../api/trade";
import { runSyncJob } from "../api/sync";
import { InTransitOverlay } from "../components/trade/InTransitOverlay";
import { ItemDetailPanel } from "../components/trade/ItemDetailPanel";
import { RebuildProgressModal } from "../components/trade/RebuildProgressModal";
import { ShoppingListOverlay } from "../components/trade/ShoppingListOverlay";
import {
  SourceSummaryTable,
  type GroupedSortDirection,
  type GroupedSortKey,
  sortOpportunityItems,
  sortSummaries,
} from "../components/trade/SourceSummaryTable";
import { useSettings } from "../hooks/useSettingsData";
import { useSyncStatus } from "../hooks/useSyncData";
import { TradeControls } from "../components/trade/TradeControls";
import {
  useDeleteInTransitAsset,
  useInTransitAssets,
  useOpportunityItems,
  useOpportunityItemDetail,
  useSources,
  useSourceSummaries,
  useTargetOpportunityItems,
  useTargets,
  useUpsertInTransitAsset,
} from "../hooks/useTradeData";
import type { OpportunityItem, ShoppingListEntry, TradeFilters } from "../types/trade";

function formatDurationAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return "Never";
  const diff = Date.now() - new Date(dateStr).getTime();
  if (diff < 0) return "Just now";
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  if (hours < 24) return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m ago` : `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h ago`;
}

const INITIAL_EXPANDED_ROW_RENDER_LIMIT = 200;
const EXPANDED_ROW_RENDER_INCREMENT = 200;
const DEFAULT_MIN_PROFIT = "15000000";
const DEFAULT_MIN_ROI_NOW_PCT = "20";
const DEFAULT_MIN_DEMAND_DAY = "1";

function parseNumberInput(value: string, fallback: number) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function formatFilterValue(value: number, fallback: string) {
  return Number.isFinite(value) ? `${value}` : fallback;
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

export function TradePage() {
  const { data: targets = [] } = useTargets();
  const settings = useSettings();
  const [targetId, setTargetId] = useState<number | null>(null);
  const [sourceId, setSourceId] = useState<number | null>(null);
  const [itemSearch, setItemSearch] = useState("");
  const [minProfit, setMinProfit] = useState(DEFAULT_MIN_PROFIT);
  const [minRoiNowPct, setMinRoiNowPct] = useState(DEFAULT_MIN_ROI_NOW_PCT);
  const [minDemandDay, setMinDemandDay] = useState(DEFAULT_MIN_DEMAND_DAY);
  const [maxDos, setMaxDos] = useState("");
  const [maxItemVolumeM3, setMaxItemVolumeM3] = useState("");
  const [sourceType, setSourceType] = useState("all");
  const [minSecurity, setMinSecurity] = useState("all");
  const [demandSource, setDemandSource] = useState("all");
  const [minEsiDemandDay, setMinEsiDemandDay] = useState("");
  const [sortKey, setSortKey] = useState<GroupedSortKey>("target_now_profit");
  const [sortDirection, setSortDirection] = useState<GroupedSortDirection>("desc");
  const [selectedTypeId, setSelectedTypeId] = useState<number | null>(null);
  const [currentGroupPage, setCurrentGroupPage] = useState(1);
  const [expandedRowRenderLimit, setExpandedRowRenderLimit] = useState(INITIAL_EXPANDED_ROW_RENDER_LIMIT);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [isRebuildModalOpen, setIsRebuildModalOpen] = useState(false);
  const [rebuildStartedAt, setRebuildStartedAt] = useState<Date | null>(null);
  const [isRebuildComplete, setIsRebuildComplete] = useState(false);
  const [isRebuildingAll, setIsRebuildingAll] = useState(false);
  const [rebuildAllError, setRebuildAllError] = useState<string | null>(null);
  const syncStatus = useSyncStatus();
  const [shoppingList, setShoppingList] = useState<ShoppingListEntry[]>([]);
  const [isShoppingListOpen, setIsShoppingListOpen] = useState(false);
  const [isInTransitOpen, setIsInTransitOpen] = useState(false);
  const [filtersInitialized, setFiltersInitialized] = useState(false);
  const periodDays = useMemo(() => {
    const configuredPeriod = Number(settings.data?.default_analysis_period_days ?? 14);
    if (!Number.isFinite(configuredPeriod)) {
      return 14;
    }
    return Math.max(Math.floor(configuredPeriod), 1);
  }, [settings.data?.default_analysis_period_days]);
  const groupsPerPage = useMemo(() => {
    const configuredSize = Number(settings.data?.trade_groups_page_size ?? 20);
    if (!Number.isFinite(configuredSize)) {
      return 20;
    }
    return Math.max(Math.floor(configuredSize), 1);
  }, [settings.data?.trade_groups_page_size]);
  const defaultFilterSettings = useMemo(() => {
    const rawFilters = settings.data?.default_filters ?? {};
    const minItemProfit = Number(rawFilters.min_item_profit);
    const roiNow = Number(rawFilters.roi_now);
    const targetDemandDay = Number(rawFilters.target_demand_day);
    return {
      minProfit: formatFilterValue(minItemProfit, DEFAULT_MIN_PROFIT),
      minRoiNowPct: formatFilterValue(roiNow * 100, DEFAULT_MIN_ROI_NOW_PCT),
      minDemandDay: formatFilterValue(targetDemandDay, DEFAULT_MIN_DEMAND_DAY),
    };
  }, [settings.data?.default_filters]);

  useEffect(() => {
    if (targetId === null && targets.length > 0) {
      setTargetId(targets[0].location_id);
    }
  }, [targetId, targets]);

  useEffect(() => {
    if (!settings.data || filtersInitialized) {
      return;
    }

    setMinProfit(defaultFilterSettings.minProfit);
    setMinRoiNowPct(defaultFilterSettings.minRoiNowPct);
    setMinDemandDay(defaultFilterSettings.minDemandDay);
    setFiltersInitialized(true);
  }, [defaultFilterSettings, filtersInitialized, settings.data]);

  const filters = useMemo<TradeFilters>(
    () => ({
      itemSearch,
      minProfit,
      minRoiNowPct,
      minDemandDay,
      maxDos,
      maxItemVolumeM3,
      sourceType,
      minSecurity,
      demandSource,
      minEsiDemandDay,
    }),
    [
      demandSource,
      itemSearch,
      maxDos,
      maxItemVolumeM3,
      minDemandDay,
      minEsiDemandDay,
      minProfit,
      minRoiNowPct,
      minSecurity,
      sourceType,
    ],
  );

  const queriesEnabled = targetId !== null && filtersInitialized;
  const selectedTarget = useMemo(
    () => targets.find((target) => target.location_id === targetId) ?? null,
    [targetId, targets],
  );
  const summaries = useSourceSummaries(targetId, periodDays, filters, queriesEnabled);
  const sources = useSources(targetId, periodDays, queriesEnabled);
  const filteredSummaries = summaries.data ?? [];
  const sortedSummaries = useMemo(
    () => sortSummaries(filteredSummaries, sortKey, sortDirection),
    [filteredSummaries, sortDirection, sortKey],
  );
  const totalGroupPages = Math.max(Math.ceil(sortedSummaries.length / groupsPerPage), 1);
  const pagedSummaries = useMemo(() => {
    const pageStart = (currentGroupPage - 1) * groupsPerPage;
    return sortedSummaries.slice(pageStart, pageStart + groupsPerPage);
  }, [currentGroupPage, groupsPerPage, sortedSummaries]);
  const firstVisibleGroupIndex = sortedSummaries.length === 0 ? 0 : (currentGroupPage - 1) * groupsPerPage + 1;
  const lastVisibleGroupIndex = Math.min(currentGroupPage * groupsPerPage, sortedSummaries.length);

  useEffect(() => {
    if (currentGroupPage > totalGroupPages) {
      setCurrentGroupPage(totalGroupPages);
    }
  }, [currentGroupPage, totalGroupPages]);

  useEffect(() => {
    const availableSummaries = pagedSummaries;
    if (availableSummaries.length === 0) {
      if (sourceId !== null) {
        setSourceId(null);
      }
      return;
    }

    const hasExpandedSource = availableSummaries.some((summary) => summary.source_location_id === sourceId);
    if (sourceId !== null && !hasExpandedSource) {
      setSourceId(null);
    }
  }, [pagedSummaries, sourceId]);

  const items = useOpportunityItems(targetId, sourceId, periodDays, filters, sourceId !== null && queriesEnabled);
  const targetItems = useTargetOpportunityItems(targetId, periodDays, queriesEnabled);
  const inTransitAssets = useInTransitAssets(targetId, queriesEnabled);
  const upsertInTransitAsset = useUpsertInTransitAsset();
  const deleteInTransitAsset = useDeleteInTransitAsset();
  const expandedItems = useMemo(() => items.data ?? [], [items.data]);
  const inTransitByTargetType = useMemo(() => {
    const totals = new Map<number, number>();
    for (const entry of inTransitAssets.data ?? []) {
      totals.set(entry.type_id, (totals.get(entry.type_id) ?? 0) + entry.quantity);
    }
    return totals;
  }, [inTransitAssets.data]);
  const sortedFilteredItems = useMemo(
    () => sortOpportunityItems(expandedItems, sortKey, sortDirection),
    [expandedItems, sortDirection, sortKey],
  );
  const visibleExpandedItems = useMemo(
    () => sortedFilteredItems.slice(0, expandedRowRenderLimit),
    [expandedRowRenderLimit, sortedFilteredItems],
  );

  useEffect(() => {
    if (visibleExpandedItems.length === 0) {
      if (selectedTypeId !== null) {
        setSelectedTypeId(null);
      }
      return;
    }

    const hasSelectedItem = visibleExpandedItems.some((row) => row.type_id === selectedTypeId);
    if (!hasSelectedItem) {
      setSelectedTypeId(visibleExpandedItems[0].type_id);
    }
  }, [selectedTypeId, visibleExpandedItems]);

  const itemDetail = useOpportunityItemDetail(targetId, sourceId, selectedTypeId, periodDays);
  const sourceSummariesLoading = Boolean(
    !filtersInitialized || summaries.isLoading || (summaries.isFetching && filteredSummaries.length === 0),
  );
  const itemRowsLoading = Boolean(sourceId !== null && (items.isLoading || items.isFetching) && expandedItems.length === 0);
  const sourceSummariesError =
    summaries.error instanceof Error ? `Grouped opportunities failed to load: ${summaries.error.message}` : null;
  const itemRowsError =
    items.error instanceof Error ? `Item opportunities failed to load: ${items.error.message}` : null;

  const handleSortChange = (nextSortKey: GroupedSortKey) => {
    setCurrentGroupPage(1);
    setExpandedRowRenderLimit(INITIAL_EXPANDED_ROW_RENDER_LIMIT);
    if (nextSortKey === sortKey) {
      startTransition(() => {
        setSortDirection((currentDirection) => (currentDirection === "desc" ? "asc" : "desc"));
      });
      return;
    }

    startTransition(() => {
      setSortKey(nextSortKey);
      setSortDirection(nextSortKey === "name" || nextSortKey === "demand_source" ? "asc" : "desc");
    });
  };

  const handleRebuildSelectedTarget = async () => {
    if (targetId === null || isRefreshing) {
      return;
    }

    const startedAt = new Date();
    setIsRefreshing(true);
    setRefreshError(null);
    setIsRebuildComplete(false);
    setRebuildStartedAt(startedAt);
    setIsRebuildModalOpen(true);
    try {
      await refreshTradeOpportunities(targetId, periodDays);
      setIsRebuildComplete(true);
      await summaries.refetch();
      await items.refetch();
      if (sourceId !== null && selectedTypeId !== null) {
        await itemDetail.refetch();
      }
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "Target rebuild failed.");
    } finally {
      setIsRefreshing(false);
    }
  };

  const lastRebuildCard = useMemo(
    () => (syncStatus.data ?? []).find((c) => c.key === "opportunity_rebuild"),
    [syncStatus.data],
  );
  const lastRebuildAge = formatDurationAgo(lastRebuildCard?.last_successful_sync);
  const isRebuildRunning = lastRebuildCard?.status === "running";

  const handleRebuildAllTargets = async () => {
    if (isRebuildingAll || isRebuildRunning) return;
    setIsRebuildingAll(true);
    setRebuildAllError(null);
    try {
      await runSyncJob("opportunity_rebuild");
    } catch (error) {
      setRebuildAllError(error instanceof Error ? error.message : "Rebuild all targets failed.");
    } finally {
      setIsRebuildingAll(false);
    }
  };

  const handleOpenShoppingList = () => {
    setIsShoppingListOpen(true);
    setIsInTransitOpen(false);
  };

  const handleOpenInTransit = () => {
    setIsInTransitOpen(true);
    setIsShoppingListOpen(false);
  };

  const handleMinimizeShoppingList = () => {
    setIsShoppingListOpen(false);
  };

  const handleMinimizeInTransit = () => {
    setIsInTransitOpen(false);
  };

  const shoppingListSourceId = useMemo(() => {
    if (shoppingList.length === 0) return null;
    return shoppingList[0].source_location_id;
  }, [shoppingList]);

  const shoppingListTypeIds = useMemo(() => new Set(shoppingList.map((e) => e.type_id)), [shoppingList]);

  const handleToggleShoppingList = (item: OpportunityItem, sourceStationName: string, sourceLocationId: number) => {
    setShoppingList((current) => {
      const exists = current.some((e) => e.type_id === item.type_id && e.source_location_id === sourceLocationId);
      if (exists) {
        const next = current.filter((e) => !(e.type_id === item.type_id && e.source_location_id === sourceLocationId));
        if (next.length === 0) {
          setIsShoppingListOpen(false);
        }
        return next;
      }
      // Lock to one source station
      if (current.length > 0 && current[0].source_location_id !== sourceLocationId) {
        return current;
      }
      const entry: ShoppingListEntry = {
        type_id: item.type_id,
        item_name: item.item_name,
        quantity: Math.max(1, Math.floor(item.target_demand_day) - (inTransitByTargetType.get(item.type_id) ?? 0)),
        source_station_sell_price: item.source_station_sell_price,
        target_now_profit: item.target_now_profit,
        target_period_profit: item.target_period_profit,
        item_volume_m3: item.item_volume_m3,
        target_demand_day: item.target_demand_day,
        source_station_name: sourceStationName,
        source_location_id: sourceLocationId,
      };
      if (current.length === 0) {
        setIsShoppingListOpen(true);
        setIsInTransitOpen(false);
      }
      return [...current, entry];
    });
  };

  const handleRemoveFromShoppingList = (typeId: number) => {
    setShoppingList((current) => {
      const next = current.filter((e) => e.type_id !== typeId);
      if (next.length === 0) {
        setIsShoppingListOpen(false);
      }
      return next;
    });
  };

  const handleUpdateShoppingListQty = (typeId: number, quantity: number) => {
    setShoppingList((current) =>
      current.map((e) => (e.type_id === typeId ? { ...e, quantity: Math.max(1, quantity) } : e)),
    );
  };

  const handleClearShoppingList = () => {
    setShoppingList([]);
    setIsShoppingListOpen(false);
  };

  const inTransitErrorMessage =
    upsertInTransitAsset.error instanceof Error
      ? upsertInTransitAsset.error.message
      : deleteInTransitAsset.error instanceof Error
        ? deleteInTransitAsset.error.message
        : null;

  const handleExportMultibuy = async (): Promise<boolean> => {
    const text = shoppingList.map((e) => `${e.item_name} ${e.quantity}`).join("\n");
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Fallback for older browsers / non-secure contexts
      try {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
        return true;
      } catch {
        return false;
      }
    }
  };

  return (
    <div className={`page-stack${shoppingList.length > 0 || selectedTarget !== null ? " page-stack--has-bottom-bar" : ""}`}>
      <header className="page-header">
        <div>
          <span className="eyebrow">Trading Analysis</span>
          <h1>Regional Day Trader</h1>
        </div>
        <div className="trade-header-actions">
          <span className="trade-rebuild-age" title="Time since last full opportunity rebuild">
            {isRebuildRunning ? "Rebuilding..." : `Last rebuild: ${lastRebuildAge}`}
          </span>
          <button
            className="refresh-button"
            type="button"
            disabled={targetId === null || isRefreshing}
            onClick={() => {
              void handleRebuildSelectedTarget();
            }}
          >
            {isRefreshing ? "Rebuilding Target..." : "Rebuild Target"}
          </button>
          <button
            className="refresh-button"
            type="button"
            disabled={isRebuildingAll || isRebuildRunning}
            onClick={() => {
              void handleRebuildAllTargets();
            }}
          >
            {isRebuildingAll || isRebuildRunning ? "Rebuilding All..." : "Rebuild All"}
          </button>
        </div>
      </header>
      {refreshError ? <p role="alert">{refreshError}</p> : null}
      {rebuildAllError ? <p role="alert">{rebuildAllError}</p> : null}
      <TradeControls
        targets={targets}
        targetId={targetId}
        itemSearch={itemSearch}
        minProfit={minProfit}
        minRoiNowPct={minRoiNowPct}
        minDemandDay={minDemandDay}
        maxDos={maxDos}
        maxItemVolumeM3={maxItemVolumeM3}
        sourceType={sourceType}
        minSecurity={minSecurity}
        demandSource={demandSource}
        minEsiDemandDay={minEsiDemandDay}
        onTargetChange={(nextTargetId) => {
                setTargetId(nextTargetId);
                setSourceId(null);
                setSelectedTypeId(null);
                setCurrentGroupPage(1);
                setExpandedRowRenderLimit(INITIAL_EXPANDED_ROW_RENDER_LIMIT);
                setShoppingList([]);
                setIsShoppingListOpen(false);
                setIsInTransitOpen(false);
        }}
        onItemSearchChange={setItemSearch}
        onMinProfitChange={setMinProfit}
        onMinRoiNowPctChange={setMinRoiNowPct}
        onMinDemandDayChange={setMinDemandDay}
        onMaxDosChange={setMaxDos}
        onMaxItemVolumeM3Change={setMaxItemVolumeM3}
        onSourceTypeChange={setSourceType}
        onMinSecurityChange={setMinSecurity}
        onDemandSourceChange={setDemandSource}
        onMinEsiDemandDayChange={setMinEsiDemandDay}
      />
      <SourceSummaryTable
        rows={pagedSummaries}
        totalRowCount={sortedSummaries.length}
        expandedSourceId={sourceId}
        expandedRows={expandedItems}
        expandedRowRenderLimit={expandedRowRenderLimit}
        selectedTypeId={selectedTypeId}
        isLoading={sourceSummariesLoading}
        errorMessage={sourceSummariesError}
        isExpandedRowsLoading={itemRowsLoading}
        expandedRowsErrorMessage={itemRowsError}
        sortKey={sortKey}
        sortDirection={sortDirection}
        shoppingListTypeIds={shoppingListTypeIds}
        shoppingListSourceId={shoppingListSourceId}
        onSortChange={handleSortChange}
        onToggleSource={(nextSourceId) => {
          startTransition(() => {
            setSourceId((currentSourceId) => (currentSourceId === nextSourceId ? null : nextSourceId));
            setSelectedTypeId(null);
            setExpandedRowRenderLimit(INITIAL_EXPANDED_ROW_RENDER_LIMIT);
          });
        }}
        onShowMoreExpandedRows={() => {
          setExpandedRowRenderLimit((currentLimit) => currentLimit + EXPANDED_ROW_RENDER_INCREMENT);
        }}
        onSelectItem={setSelectedTypeId}
        onToggleShoppingList={handleToggleShoppingList}
      />
      {sortedSummaries.length > 0 ? (
        <div className="panel pagination-panel" aria-label="Grouped source market pagination">
          <span>
            Showing groups {firstVisibleGroupIndex}-{lastVisibleGroupIndex} of {sortedSummaries.length}
          </span>
          <div className="pagination-controls">
            <button
              type="button"
              className="inline-more-button"
              disabled={currentGroupPage === 1}
              onClick={() => {
                setCurrentGroupPage(1);
                setSourceId(null);
                setSelectedTypeId(null);
              }}
            >
              First
            </button>
            <button
              type="button"
              className="inline-more-button"
              disabled={currentGroupPage === 1}
              onClick={() => {
                setCurrentGroupPage((currentPage) => Math.max(currentPage - 1, 1));
                setSourceId(null);
                setSelectedTypeId(null);
              }}
            >
              Previous
            </button>
            <span>
              Page {currentGroupPage} / {totalGroupPages}
            </span>
            <button
              type="button"
              className="inline-more-button"
              disabled={currentGroupPage === totalGroupPages}
              onClick={() => {
                setCurrentGroupPage((currentPage) => Math.min(currentPage + 1, totalGroupPages));
                setSourceId(null);
                setSelectedTypeId(null);
              }}
            >
              Next
            </button>
            <button
              type="button"
              className="inline-more-button"
              disabled={currentGroupPage === totalGroupPages}
              onClick={() => {
                setCurrentGroupPage(totalGroupPages);
                setSourceId(null);
                setSelectedTypeId(null);
              }}
            >
              Last
            </button>
          </div>
        </div>
      ) : null}
      <ItemDetailPanel detail={itemDetail.data} isLoading={itemDetail.isLoading} />
      {shoppingList.length > 0 || selectedTarget !== null ? (
        <div className="trade-bottom-tabs">
          {shoppingList.length > 0 ? (
            <div
              className={`shopping-list-tab${isShoppingListOpen ? " shopping-list-tab--active" : ""}`}
              onClick={isShoppingListOpen ? handleMinimizeShoppingList : handleOpenShoppingList}
              role="button"
              tabIndex={0}
              aria-pressed={isShoppingListOpen}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  if (isShoppingListOpen) {
                    handleMinimizeShoppingList();
                  } else {
                    handleOpenShoppingList();
                  }
                }
              }}
            >
              <span className="shopping-list-tab__count">{shoppingList.length}</span>
              <span className="shopping-list-tab__label">Shopping List</span>
              <span className="shopping-list-tab__chevron">{isShoppingListOpen ? "▼" : "▲"}</span>
            </div>
          ) : null}
          {selectedTarget !== null ? (
            <div
              className={`in-transit-tab${isInTransitOpen ? " in-transit-tab--active" : ""}`}
              onClick={isInTransitOpen ? handleMinimizeInTransit : handleOpenInTransit}
              role="button"
              tabIndex={0}
              aria-pressed={isInTransitOpen}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  if (isInTransitOpen) {
                    handleMinimizeInTransit();
                  } else {
                    handleOpenInTransit();
                  }
                }
              }}
            >
              <span className="in-transit-tab__count">{(inTransitAssets.data ?? []).length}</span>
              <span className="in-transit-tab__label">In Transit</span>
              <span className="in-transit-tab__chevron">{isInTransitOpen ? "▼" : "▲"}</span>
            </div>
          ) : null}
        </div>
      ) : null}
      <ShoppingListOverlay
        entries={shoppingList}
        isOpen={isShoppingListOpen}
        onRemove={handleRemoveFromShoppingList}
        onUpdateQty={handleUpdateShoppingListQty}
        onClearAll={handleClearShoppingList}
        onExportMultibuy={handleExportMultibuy}
        onMinimize={handleMinimizeShoppingList}
      />
      <InTransitOverlay
        target={selectedTarget}
        sourceOptions={sources.data ?? []}
        itemOptions={targetItems.data ?? []}
        entries={inTransitAssets.data ?? []}
        isOpen={isInTransitOpen}
        isSaving={upsertInTransitAsset.isPending}
        isDeleting={deleteInTransitAsset.isPending}
        errorMessage={inTransitErrorMessage}
        onMinimize={handleMinimizeInTransit}
        onSave={(payload) => upsertInTransitAsset.mutate(payload)}
        onDelete={(entryId) => deleteInTransitAsset.mutate({ entryId })}
      />
      <RebuildProgressModal
        isOpen={isRebuildModalOpen}
        rebuildStartedAt={rebuildStartedAt}
        isComplete={isRebuildComplete}
        error={refreshError}
        onClose={() => setIsRebuildModalOpen(false)}
      />
    </div>
  );
}
