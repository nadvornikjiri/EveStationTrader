import type { OpportunityItem } from "../../types/trade";

type Props = {
  rows: OpportunityItem[];
};

export function ItemOpportunityTable({ rows }: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Item Opportunities</h2>
        <span>{rows.length} items</span>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Item Name</th>
            <th>Purchase Units</th>
            <th>Source Price</th>
            <th>Target Now Price</th>
            <th>ROI Now</th>
            <th>Demand Source</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.type_id}>
              <td>{row.item_name}</td>
              <td>{row.purchase_units}</td>
              <td>{row.source_station_sell_price.toLocaleString()}</td>
              <td>{row.target_station_sell_price.toLocaleString()}</td>
              <td>{(row.roi_now * 100).toFixed(1)}%</td>
              <td>{row.demand_source}</td>
              <td>{(row.confidence_score * 100).toFixed(0)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
