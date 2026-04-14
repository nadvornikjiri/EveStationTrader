import { useEffect, useMemo, useState } from "react";

import type { OpportunityItem, SourceSummary } from "../../types/trade";

export type GroupedSortKey =
  | "name"
  | "source_security_status"
  | "purchase_units"
  | "source_units_available"
  | "target_demand_day"
  | "target_supply_units"
  | "target_dos"
  | "in_transit_units"
  | "assets_units"
  | "active_sell_orders_units"
  | "source_avg_price"
  | "target_now_price"
  | "target_period_avg_price"
  | "target_now_profit"
  | "target_period_profit"
  | "capital_required"
  | "roi_now"
  | "roi_period"
  | "item_volume_m3"
  | "shipping_cost"
  | "demand_source"
  | "esi_demand_day";

export type GroupedSortDirection = "asc" | "desc";

type Props = {
  rows: SourceSummary[];
  totalRowCount?: number;
  expandedSourceId: number | null;
  expandedRows: OpportunityItem[];
  expandedRowRenderLimit: number;
  selectedTypeId: number | null;
  isLoading?: boolean;
  errorMessage?: string | null;
  isExpandedRowsLoading?: boolean;
  expandedRowsErrorMessage?: string | null;
  sortKey: GroupedSortKey;
  sortDirection: GroupedSortDirection;
  shoppingListTypeIds: Set<number>;
  shoppingListSourceId: number | null;
  onSortChange: (sortKey: GroupedSortKey) => void;
  onToggleSource: (sourceId: number) => void;
  onShowMoreExpandedRows: () => void;
  onSelectItem: (typeId: number) => void;
  onToggleShoppingList: (item: OpportunityItem, sourceStationName: string, sourceLocationId: number) => void;
};

const SORTABLE_COLUMNS: Array<{ key: GroupedSortKey; label: string }> = [
  { key: "name", label: "Source Market / Item" },
  { key: "source_security_status", label: "Sec" },
  { key: "purchase_units", label: "Purchase Units" },
  { key: "source_units_available", label: "Source Units Avail" },
  { key: "target_demand_day", label: "Target Demand / Day" },
  { key: "esi_demand_day", label: "ESI Traded Vol" },
  { key: "target_supply_units", label: "Target Supply Units" },
  { key: "target_dos", label: "Target D.O.S" },
  { key: "in_transit_units", label: "In Transit" },
  { key: "assets_units", label: "Assets" },
  { key: "active_sell_orders_units", label: "Active Sell Orders" },
  { key: "source_avg_price", label: "Source Now Price" },
  { key: "target_now_price", label: "Target Now Price" },
  { key: "target_period_avg_price", label: "Target Period Avg Price" },
  { key: "target_now_profit", label: "Target Now Profit" },
  { key: "target_period_profit", label: "Target Period Profit" },
  { key: "capital_required", label: "Capital Required" },
  { key: "roi_now", label: "ROI Now" },
  { key: "roi_period", label: "ROI Period" },
  { key: "item_volume_m3", label: "Item Volume" },
  { key: "shipping_cost", label: "Shipping Cost" },
  { key: "demand_source", label: "Demand Source" },
];

function getSortIndicator(columnKey: GroupedSortKey, activeKey: GroupedSortKey, direction: GroupedSortDirection) {
  if (columnKey !== activeKey) {
    return "";
  }

  return direction === "asc" ? " ^" : " v";
}

function compareValues(left: number | string, right: number | string) {
  if (typeof left === "string" && typeof right === "string") {
    return left.localeCompare(right);
  }
  return Number(left) - Number(right);
}

function combineClasses(...classNames: Array<string | null>) {
  return classNames.filter(Boolean).join(" ");
}

function metricToneClass(value: number) {
  if (value > 0) {
    return "metric-cell-positive";
  }
  if (value < 0) {
    return "metric-cell-negative";
  }
  return null;
}

function summaryCellClass(row: SourceSummary, key: GroupedSortKey) {
  switch (key) {
    case "source_avg_price":
      return "metric-cell-source-price";
    case "capital_required":
      return "metric-cell-capital";
    case "target_now_profit":
      return metricToneClass(row.target_now_profit_weighted);
    case "target_period_profit":
      return metricToneClass(row.target_period_profit_weighted);
    case "roi_now":
      return metricToneClass(row.roi_now_weighted);
    case "roi_period":
      return metricToneClass(row.roi_period_weighted);
    default:
      return null;
  }
}

function itemCellClass(row: OpportunityItem, key: GroupedSortKey) {
  switch (key) {
    case "source_avg_price":
      return "metric-cell-source-price";
    case "capital_required":
      return "metric-cell-capital";
    case "target_now_profit":
      return metricToneClass(row.target_now_profit);
    case "target_period_profit":
      return metricToneClass(row.target_period_profit);
    case "roi_now":
      return metricToneClass(row.roi_now);
    case "roi_period":
      return metricToneClass(row.roi_period);
    default:
      return null;
  }
}

function summaryValue(row: SourceSummary, key: GroupedSortKey): number | string {
  switch (key) {
    case "name":
      return row.source_market_name;
    case "source_security_status":
      return row.source_security_status;
    case "purchase_units":
      return row.purchase_units_total;
    case "source_units_available":
      return row.source_units_available_total;
    case "target_demand_day":
      return row.target_demand_day_total;
    case "target_supply_units":
      return row.target_supply_units_total;
    case "target_dos":
      return row.target_dos_weighted;
    case "in_transit_units":
      return row.in_transit_units;
    case "assets_units":
      return row.assets_units;
    case "active_sell_orders_units":
      return row.active_sell_orders_units;
    case "source_avg_price":
      return row.source_avg_price_weighted;
    case "target_now_price":
      return row.target_now_price_weighted;
    case "target_period_avg_price":
      return row.target_period_avg_price_weighted;
    case "target_now_profit":
      return row.target_now_profit_weighted;
    case "target_period_profit":
      return row.target_period_profit_weighted;
    case "capital_required":
      return row.capital_required_total;
    case "roi_now":
      return row.roi_now_weighted;
    case "roi_period":
      return row.roi_period_weighted;
    case "item_volume_m3":
      return row.total_item_volume_m3;
    case "shipping_cost":
      return row.shipping_cost_total;
    case "demand_source":
      return row.demand_source_summary;
    case "esi_demand_day":
      return row.esi_demand_day_total;
  }
}

function itemValue(row: OpportunityItem, key: GroupedSortKey): number | string {
  switch (key) {
    case "name":
      return row.item_name;
    case "source_security_status":
      return row.source_security_status;
    case "purchase_units":
      return row.purchase_units;
    case "source_units_available":
      return row.source_units_available;
    case "target_demand_day":
      return row.target_demand_day;
    case "target_supply_units":
      return row.target_supply_units;
    case "target_dos":
      return row.target_dos;
    case "in_transit_units":
      return row.in_transit_units_item;
    case "assets_units":
      return row.assets_units_item;
    case "active_sell_orders_units":
      return row.active_sell_orders_units_item;
    case "source_avg_price":
      return row.source_station_sell_price;
    case "target_now_price":
      return row.target_station_sell_price;
    case "target_period_avg_price":
      return row.target_period_avg_price;
    case "target_now_profit":
      return row.target_now_profit;
    case "target_period_profit":
      return row.target_period_profit;
    case "capital_required":
      return row.capital_required;
    case "roi_now":
      return row.roi_now;
    case "roi_period":
      return row.roi_period;
    case "item_volume_m3":
      return row.item_volume_m3;
    case "shipping_cost":
      return row.shipping_cost;
    case "demand_source":
      return row.demand_source;
    case "esi_demand_day":
      return row.esi_demand_day;
  }
}

export function sortSummaries(rows: SourceSummary[], sortKey: GroupedSortKey, sortDirection: GroupedSortDirection) {
  const sorted = [...rows].sort((left, right) => compareValues(summaryValue(left, sortKey), summaryValue(right, sortKey)));
  return sortDirection === "asc" ? sorted : sorted.reverse();
}

export function sortOpportunityItems(rows: OpportunityItem[], sortKey: GroupedSortKey, sortDirection: GroupedSortDirection) {
  const sorted = [...rows].sort((left, right) => compareValues(itemValue(left, sortKey), itemValue(right, sortKey)));
  return sortDirection === "asc" ? sorted : sorted.reverse();
}

function renderSummaryCell(row: SourceSummary, key: GroupedSortKey) {
  switch (key) {
    case "name":
      return row.source_market_name;
    case "source_security_status":
      return row.source_security_status.toFixed(1);
    case "purchase_units":
      return row.purchase_units_total;
    case "source_units_available":
      return row.source_units_available_total;
    case "target_demand_day":
      return row.target_demand_day_total.toFixed(1);
    case "target_supply_units":
      return row.target_supply_units_total;
    case "target_dos":
      return row.target_dos_weighted.toFixed(1);
    case "in_transit_units":
      return row.in_transit_units;
    case "assets_units":
      return row.assets_units;
    case "active_sell_orders_units":
      return row.active_sell_orders_units;
    case "source_avg_price":
      return row.source_avg_price_weighted.toLocaleString();
    case "target_now_price":
      return row.target_now_price_weighted.toLocaleString();
    case "target_period_avg_price":
      return row.target_period_avg_price_weighted.toLocaleString();
    case "target_now_profit":
      return row.target_now_profit_weighted.toLocaleString();
    case "target_period_profit":
      return row.target_period_profit_weighted.toLocaleString();
    case "capital_required":
      return row.capital_required_total.toLocaleString();
    case "roi_now":
      return `${(row.roi_now_weighted * 100).toFixed(1)}%`;
    case "roi_period":
      return `${(row.roi_period_weighted * 100).toFixed(1)}%`;
    case "item_volume_m3":
      return `${Math.round(row.total_item_volume_m3).toLocaleString()} m3`;
    case "shipping_cost":
      return row.shipping_cost_total.toLocaleString();
    case "demand_source":
      return row.demand_source_summary;
    case "esi_demand_day":
      return row.esi_demand_day_total.toFixed(1);
  }
}

function renderItemCell(row: OpportunityItem, key: GroupedSortKey) {
  switch (key) {
    case "name":
      return row.item_name;
    case "source_security_status":
      return row.source_security_status.toFixed(1);
    case "purchase_units":
      return row.purchase_units;
    case "source_units_available":
      return row.source_units_available;
    case "target_demand_day":
      return row.target_demand_day.toFixed(1);
    case "target_supply_units":
      return row.target_supply_units;
    case "target_dos":
      return row.target_dos.toFixed(1);
    case "in_transit_units":
      return row.in_transit_units_item;
    case "assets_units":
      return row.assets_units_item;
    case "active_sell_orders_units":
      return row.active_sell_orders_units_item;
    case "source_avg_price":
      return row.source_station_sell_price.toLocaleString();
    case "target_now_price":
      return row.target_station_sell_price.toLocaleString();
    case "target_period_avg_price":
      return row.target_period_avg_price.toLocaleString();
    case "target_now_profit":
      return row.target_now_profit.toLocaleString();
    case "target_period_profit":
      return row.target_period_profit.toLocaleString();
    case "capital_required":
      return row.capital_required.toLocaleString();
    case "roi_now":
      return `${(row.roi_now * 100).toFixed(1)}%`;
    case "roi_period":
      return `${(row.roi_period * 100).toFixed(1)}%`;
    case "item_volume_m3":
      return `${Math.round(row.item_volume_m3).toLocaleString()} m3`;
    case "shipping_cost":
      return row.shipping_cost.toLocaleString();
    case "demand_source":
      return row.demand_source;
    case "esi_demand_day":
      return row.esi_demand_day.toFixed(1);
  }
}

export function SourceSummaryTable({
  rows,
  totalRowCount,
  expandedSourceId,
  expandedRows,
  expandedRowRenderLimit,
  selectedTypeId,
  isLoading = false,
  errorMessage = null,
  isExpandedRowsLoading = false,
  expandedRowsErrorMessage = null,
  sortKey,
  sortDirection,
  shoppingListTypeIds,
  shoppingListSourceId,
  onSortChange,
  onToggleSource,
  onShowMoreExpandedRows,
  onSelectItem,
  onToggleShoppingList,
}: Props) {
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    itemName: string;
    url: string;
  } | null>(null);
  const sortedRows = useMemo(() => sortSummaries(rows, sortKey, sortDirection), [rows, sortDirection, sortKey]);
  const sortedExpandedRows = useMemo(
    () => sortOpportunityItems(expandedRows, sortKey, sortDirection),
    [expandedRows, sortDirection, sortKey],
  );
  const visibleExpandedRows = useMemo(
    () => sortedExpandedRows.slice(0, expandedRowRenderLimit),
    [expandedRowRenderLimit, sortedExpandedRows],
  );

  useEffect(() => {
    if (contextMenu === null) {
      return undefined;
    }

    const dismissMenu = () => {
      setContextMenu(null);
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        dismissMenu();
      }
    };

    window.addEventListener("click", dismissMenu);
    window.addEventListener("scroll", dismissMenu, true);
    window.addEventListener("resize", dismissMenu);
    window.addEventListener("keydown", handleEscape);

    return () => {
      window.removeEventListener("click", dismissMenu);
      window.removeEventListener("scroll", dismissMenu, true);
      window.removeEventListener("resize", dismissMenu);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [contextMenu]);

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Grouped Opportunities</h2>
        <span>
          {(totalRowCount ?? rows.length) > 0
            ? `${totalRowCount ?? rows.length} tracked`
            : isLoading
              ? "Loading..."
              : errorMessage
                ? "Load failed"
                : "0 tracked"}
        </span>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th className="checkbox-col" />
              {SORTABLE_COLUMNS.map((column) => (
                <th key={column.key} className={column.key === "name" ? "source-market-item-col" : undefined}>
                  <button
                    type="button"
                    className="sort-button"
                    aria-label={`Sort by ${column.label}`}
                    onClick={() => onSortChange(column.key)}
                  >
                    {column.label}
                    {getSortIndicator(column.key, sortKey, sortDirection)}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && isLoading ? (
              <tr>
                <td colSpan={23}>Loading source markets for this target...</td>
              </tr>
            ) : rows.length === 0 && errorMessage ? (
              <tr>
                <td colSpan={23}>{errorMessage}</td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={23}>No computed source markets available for this target yet.</td>
              </tr>
            ) : (
              sortedRows.flatMap((row) => {
                const isExpanded = expandedSourceId === row.source_location_id;
                const renderedRows = [
                  <tr
                    key={`source-${row.source_location_id}`}
                    className={isExpanded ? "selected-row grouped-source-row" : "grouped-source-row"}
                  >
                    <td className="checkbox-col" />
                    <td className="source-market-item-col">
                      <button
                        type="button"
                        className="group-toggle"
                        aria-label={isExpanded ? `Collapse ${row.source_market_name}` : `Expand ${row.source_market_name}`}
                        onClick={() => onToggleSource(row.source_location_id)}
                      >
                        <span className="group-toggle-indicator">{isExpanded ? "-" : "+"}</span>
                        <span>{row.source_market_name}</span>
                      </button>
                    </td>
                    {SORTABLE_COLUMNS.slice(1).map((column) => (
                      <td
                        key={`${row.source_location_id}-${column.key}`}
                        className={combineClasses("metric-cell", summaryCellClass(row, column.key))}
                      >
                        {renderSummaryCell(row, column.key)}
                      </td>
                    ))}
                  </tr>,
                ];

                if (!isExpanded) {
                  return renderedRows;
                }

                if (isExpandedRowsLoading) {
                  renderedRows.push(
                    <tr key={`loading-${row.source_location_id}`} className="grouped-item-row">
                      <td colSpan={23}>Loading item opportunities for this source...</td>
                    </tr>,
                  );
                  return renderedRows;
                }

                if (expandedRowsErrorMessage) {
                  renderedRows.push(
                    <tr key={`error-${row.source_location_id}`} className="grouped-item-row">
                      <td colSpan={23}>{expandedRowsErrorMessage}</td>
                    </tr>,
                  );
                  return renderedRows;
                }

                if (sortedExpandedRows.length === 0) {
                  renderedRows.push(
                    <tr key={`empty-${row.source_location_id}`} className="grouped-item-row">
                      <td colSpan={23}>No item opportunities match the current filters for this source.</td>
                    </tr>,
                  );
                  return renderedRows;
                }

                renderedRows.push(
                  ...visibleExpandedRows.map((item) => (
                    <tr
                      key={`item-${row.source_location_id}-${item.type_id}`}
                      className={selectedTypeId === item.type_id ? "selected-row grouped-item-row" : "grouped-item-row"}
                      onClick={() => onSelectItem(item.type_id)}
                      onContextMenu={(event) => {
                        if (!item.market_browser_url) {
                          return;
                        }
                        event.preventDefault();
                        setContextMenu({
                          x: event.clientX,
                          y: event.clientY,
                          itemName: item.item_name,
                          url: item.market_browser_url,
                        });
                      }}
                    >
                      <td
                        className="checkbox-col"
                        onClick={(event) => event.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          aria-label={`Add ${item.item_name} to shopping list`}
                          checked={shoppingListTypeIds.has(item.type_id) && (shoppingListSourceId === null || shoppingListSourceId === row.source_location_id)}
                          disabled={shoppingListSourceId !== null && shoppingListSourceId !== row.source_location_id}
                          onChange={() => onToggleShoppingList(item, row.source_market_name, row.source_location_id)}
                        />
                      </td>
                      <td className="source-market-item-col">
                        <span className="grouped-item-label">{item.item_name}</span>
                      </td>
                      {SORTABLE_COLUMNS.slice(1).map((column) => (
                        <td
                          key={`${row.source_location_id}-${item.type_id}-${column.key}`}
                          className={combineClasses("metric-cell", itemCellClass(item, column.key))}
                        >
                          {renderItemCell(item, column.key)}
                        </td>
                      ))}
                    </tr>
                  )),
                );

                if (visibleExpandedRows.length < sortedExpandedRows.length) {
                  renderedRows.push(
                    <tr key={`show-more-${row.source_location_id}`} className="grouped-item-row grouped-item-more-row">
                      <td colSpan={23}>
                        <button
                          type="button"
                          className="inline-more-button"
                          onClick={onShowMoreExpandedRows}
                        >
                          Show more item opportunities ({visibleExpandedRows.length} of {sortedExpandedRows.length} shown)
                        </button>
                      </td>
                    </tr>,
                  );
                }

                return renderedRows;
              })
            )}
          </tbody>
        </table>
      </div>
      {contextMenu ? (
        <div
          className="trade-context-menu"
          role="menu"
          aria-label={`${contextMenu.itemName} actions`}
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <button
            type="button"
            className="trade-context-menu__item"
            role="menuitem"
            onClick={() => {
              window.open(contextMenu.url, "_blank", "noopener,noreferrer");
              setContextMenu(null);
            }}
          >
            Open MarketBrowser
          </button>
        </div>
      ) : null}
    </section>
  );
}
