import type { OpportunityItem } from "../../types/trade";

type SortKey = "item_name" | "purchase_units" | "target_now_profit" | "roi_now";
type SortDirection = "asc" | "desc";

type Props = {
  rows: OpportunityItem[];
  sortKey: SortKey;
  sortDirection: SortDirection;
  selectedTypeId: number | null;
  isLoading?: boolean;
  onSortChange: (sortKey: SortKey) => void;
  onSelectItem: (typeId: number) => void;
};

const SORTABLE_COLUMNS: Array<{ key: SortKey; label: string }> = [
  { key: "item_name", label: "Item Name" },
  { key: "purchase_units", label: "Purchase Units" },
  { key: "target_now_profit", label: "Target Now Profit" },
  { key: "roi_now", label: "ROI Now" },
];

const NUMERIC_HEADERS = new Set([
  "Sec",
  "Purchase Units",
  "ROI Now",
  "Source Units Avail",
  "Target Demand / Day",
  "ESI Traded Vol",
  "Target Supply Units",
  "Target D.O.S",
  "In Transit",
  "Assets",
  "Active Sell Orders",
  "Source Now Price",
  "Target Now Price",
  "Target Period Avg Price",
  "Target Now Profit",
  "Target Period Profit",
  "Capital Required",
  "ROI Period",
  "Item Volume",
  "Shipping Cost",
]);

function getSortIndicator(columnKey: SortKey, activeKey: SortKey, direction: SortDirection) {
  if (columnKey !== activeKey) {
    return "";
  }

  return direction === "asc" ? " ↑" : " ↓";
}

function formatWholeNumber(value: number) {
  return Math.round(value).toLocaleString();
}

function formatWholePercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function ItemOpportunityTable({
  rows,
  sortKey,
  sortDirection,
  selectedTypeId,
  isLoading = false,
  onSortChange,
  onSelectItem,
}: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Item Opportunities</h2>
        <span>{rows.length > 0 ? `${rows.length} items` : isLoading ? "Loading..." : "0 items"}</span>
      </div>
      <div className="table-scroll">
        <table className="data-table trade-table">
          <thead>
            <tr>
              <th className="numeric-cell">Sec</th>
              {SORTABLE_COLUMNS.map((column) => (
                <th key={column.key} className={NUMERIC_HEADERS.has(column.label) ? "numeric-cell" : undefined}>
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
              <th className="numeric-cell">Source Units Avail</th>
              <th className="numeric-cell">Target Demand / Day</th>
              <th className="numeric-cell">ESI Traded Vol</th>
              <th className="numeric-cell">Target Supply Units</th>
              <th className="numeric-cell">Target D.O.S</th>
              <th className="numeric-cell">In Transit</th>
              <th className="numeric-cell">Assets</th>
              <th className="numeric-cell">Active Sell Orders</th>
              <th className="numeric-cell">Source Now Price</th>
              <th className="numeric-cell">Target Now Price</th>
              <th className="numeric-cell">Target Period Avg Price</th>
              <th className="numeric-cell">Target Now Profit</th>
              <th className="numeric-cell">Target Period Profit</th>
              <th className="numeric-cell">Capital Required</th>
              <th className="numeric-cell">ROI Period</th>
              <th className="numeric-cell">Item Volume</th>
              <th className="numeric-cell">Shipping Cost</th>
              <th>Demand Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && isLoading ? (
              <tr>
                <td colSpan={22}>Loading item opportunities for this source...</td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={22}>No computed item opportunities available for this source yet.</td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr
                  key={row.type_id}
                  className={selectedTypeId === row.type_id ? "selected-row" : undefined}
                  onClick={() => onSelectItem(row.type_id)}
                >
                  <td className="numeric-cell">{row.source_security_status.toFixed(1)}</td>
                  <td>{row.item_name}</td>
                  <td className="numeric-cell">{row.purchase_units}</td>
                  <td className="numeric-cell">{formatWholePercent(row.roi_now)}</td>
                  <td className="numeric-cell">{row.source_units_available}</td>
                  <td className="numeric-cell">{row.target_demand_day.toFixed(1)}</td>
                  <td className="numeric-cell">{row.esi_demand_day.toFixed(1)}</td>
                  <td className="numeric-cell">{row.target_supply_units}</td>
                  <td className="numeric-cell">{row.target_dos.toFixed(1)}</td>
                  <td className="numeric-cell">{row.in_transit_units_item}</td>
                  <td className="numeric-cell">{row.assets_units_item}</td>
                  <td className="numeric-cell">{row.active_sell_orders_units_item}</td>
                  <td className="numeric-cell">{formatWholeNumber(row.source_station_sell_price)}</td>
                  <td className="numeric-cell">{formatWholeNumber(row.target_station_sell_price)}</td>
                  <td className="numeric-cell">{formatWholeNumber(row.target_period_avg_price)}</td>
                  <td className="numeric-cell">{formatWholeNumber(row.target_now_profit)}</td>
                  <td className="numeric-cell">{formatWholeNumber(row.target_period_profit)}</td>
                  <td className="numeric-cell">{formatWholeNumber(row.capital_required)}</td>
                  <td className="numeric-cell">{formatWholePercent(row.roi_period)}</td>
                  <td className="numeric-cell">{row.item_volume_m3.toFixed(2)}</td>
                  <td className="numeric-cell">{formatWholeNumber(row.shipping_cost)}</td>
                  <td>{row.demand_source}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
