import type { OpportunityItem } from "../../types/trade";

type SortKey = "item_name" | "purchase_units" | "roi_now" | "confidence_score";
type SortDirection = "asc" | "desc";

type Props = {
  rows: OpportunityItem[];
  sortKey: SortKey;
  sortDirection: SortDirection;
  onSortChange: (sortKey: SortKey) => void;
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

export function ItemOpportunityTable({ rows, sortKey, sortDirection, onSortChange }: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Item Opportunities</h2>
        <span>{rows.length} items</span>
      </div>
      <table className="data-table">
        <thead>
          <tr>
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
            <th>Source Price</th>
            <th>Target Now Price</th>
            <th>Demand Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.type_id}>
              <td>{row.item_name}</td>
              <td>{row.purchase_units}</td>
              <td>{(row.roi_now * 100).toFixed(1)}%</td>
              <td>{(row.confidence_score * 100).toFixed(0)}%</td>
              <td>{row.source_station_sell_price.toLocaleString()}</td>
              <td>{row.target_station_sell_price.toLocaleString()}</td>
              <td>{row.demand_source}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
