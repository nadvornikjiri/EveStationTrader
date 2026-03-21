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
      <table className="data-table">
        <thead>
          <tr>
            <th>Source Market</th>
            <th>Sec</th>
            <th>Purchase Units</th>
            <th>Target Demand / Day</th>
            <th>ROI Now</th>
            <th>Target Now Profit</th>
            <th>Capital Required</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.source_location_id}
              className={selectedSourceId === row.source_location_id ? "selected-row" : undefined}
              onClick={() => onSelectSource(row.source_location_id)}
            >
              <td>{row.source_market_name}</td>
              <td>{row.source_security_status.toFixed(1)}</td>
              <td>{row.purchase_units_total}</td>
              <td>{row.target_demand_day_total}</td>
              <td>{(row.roi_now_weighted * 100).toFixed(1)}%</td>
              <td>{row.target_now_profit_weighted.toLocaleString()}</td>
              <td>{row.capital_required_total.toLocaleString()}</td>
              <td>{(row.confidence_score_summary * 100).toFixed(0)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
