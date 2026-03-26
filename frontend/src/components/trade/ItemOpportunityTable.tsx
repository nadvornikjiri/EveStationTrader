import type { OpportunityItem } from "../../types/trade";

type SortKey = "item_name" | "purchase_units" | "roi_now" | "confidence_score";
type SortDirection = "asc" | "desc";

type Props = {
  rows: OpportunityItem[];
  sortKey: SortKey;
  sortDirection: SortDirection;
  selectedTypeId: number | null;
  onSortChange: (sortKey: SortKey) => void;
  onSelectItem: (typeId: number) => void;
};

const SORTABLE_COLUMNS: Array<{ key: SortKey; label: string }> = [
  { key: "item_name", label: "Item Name" },
  { key: "purchase_units", label: "Purchase Units" },
  { key: "roi_now", label: "ROI Now" },
  { key: "confidence_score", label: "Confidence" },
];

function getSortIndicator(columnKey: SortKey, activeKey: SortKey, direction: SortDirection) {
  if (columnKey !== activeKey) {
    return "";
  }

  return direction === "asc" ? " ↑" : " ↓";
}

export function ItemOpportunityTable({
  rows,
  sortKey,
  sortDirection,
  selectedTypeId,
  onSortChange,
  onSelectItem,
}: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Item Opportunities</h2>
        <span>{rows.length} items</span>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Sec</th>
              {SORTABLE_COLUMNS.map((column) => (
                <th key={column.key}>
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
              <th>Source Units Avail</th>
              <th>Target Demand / Day</th>
              <th>Target Supply Units</th>
              <th>Target D.O.S</th>
              <th>In Transit</th>
              <th>Assets</th>
              <th>Active Sell Orders</th>
              <th>Source Avg Price</th>
              <th>Target Now Price</th>
              <th>Target Period Avg Price</th>
              <th>Target Now Profit</th>
              <th>Target Period Profit</th>
              <th>Capital Required</th>
              <th>ROI Period</th>
              <th>Item Volume</th>
              <th>Shipping Cost</th>
              <th>Demand Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
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
                  <td>{row.source_security_status.toFixed(1)}</td>
                  <td>{row.item_name}</td>
                  <td>{row.purchase_units}</td>
                  <td>{(row.roi_now * 100).toFixed(1)}%</td>
                  <td>{(row.confidence_score * 100).toFixed(0)}%</td>
                  <td>{row.source_units_available}</td>
                  <td>{row.target_demand_day.toFixed(1)}</td>
                  <td>{row.target_supply_units}</td>
                  <td>{row.target_dos.toFixed(1)}</td>
                  <td>{row.in_transit_units_item}</td>
                  <td>{row.assets_units_item}</td>
                  <td>{row.active_sell_orders_units_item}</td>
                  <td>{row.source_station_sell_price.toLocaleString()}</td>
                  <td>{row.target_station_sell_price.toLocaleString()}</td>
                  <td>{row.target_period_avg_price.toLocaleString()}</td>
                  <td>{row.target_now_profit.toLocaleString()}</td>
                  <td>{row.target_period_profit.toLocaleString()}</td>
                  <td>{row.capital_required.toLocaleString()}</td>
                  <td>{(row.roi_period * 100).toFixed(1)}%</td>
                  <td>{row.item_volume_m3.toFixed(2)}</td>
                  <td>{row.shipping_cost.toLocaleString()}</td>
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
