import type { SourceSummary } from "../../types/trade";

type Props = {
  rows: SourceSummary[];
  selectedSourceId: number | null;
  onSelectSource: (sourceId: number) => void;
};

export function SourceSummaryTable({ rows, selectedSourceId, onSelectSource }: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Source Markets</h2>
        <span>{rows.length} tracked</span>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Source Market</th>
              <th>Sec</th>
              <th>Purchase Units</th>
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
              <th>ROI Now</th>
              <th>ROI Period</th>
              <th>Item Volume</th>
              <th>Shipping Cost</th>
              <th>Demand Source</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={22}>No computed source markets available for this target yet.</td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr
                  key={row.source_location_id}
                  className={selectedSourceId === row.source_location_id ? "selected-row" : undefined}
                  onClick={() => onSelectSource(row.source_location_id)}
                >
                  <td>{row.source_market_name}</td>
                  <td>{row.source_security_status.toFixed(1)}</td>
                  <td>{row.purchase_units_total}</td>
                  <td>{row.source_units_available_total}</td>
                  <td>{row.target_demand_day_total.toFixed(1)}</td>
                  <td>{row.target_supply_units_total}</td>
                  <td>{row.target_dos_weighted.toFixed(1)}</td>
                  <td>{row.in_transit_units}</td>
                  <td>{row.assets_units}</td>
                  <td>{row.active_sell_orders_units}</td>
                  <td>{row.source_avg_price_weighted.toLocaleString()}</td>
                  <td>{row.target_now_price_weighted.toLocaleString()}</td>
                  <td>{row.target_period_avg_price_weighted.toLocaleString()}</td>
                  <td>{row.target_now_profit_weighted.toLocaleString()}</td>
                  <td>{row.target_period_profit_weighted.toLocaleString()}</td>
                  <td>{row.capital_required_total.toLocaleString()}</td>
                  <td>{(row.roi_now_weighted * 100).toFixed(1)}%</td>
                  <td>{(row.roi_period_weighted * 100).toFixed(1)}%</td>
                  <td>{row.total_item_volume_m3.toFixed(2)}</td>
                  <td>{row.shipping_cost_total.toLocaleString()}</td>
                  <td>{row.demand_source_summary}</td>
                  <td>{(row.confidence_score_summary * 100).toFixed(0)}%</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
