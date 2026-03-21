import type { ItemOrderRow, OpportunityItemDetail } from "../../types/trade";

type Props = {
  detail?: OpportunityItemDetail;
  isLoading?: boolean;
};

function formatNumber(value: number) {
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function renderOrders(rows: ItemOrderRow[]) {
  if (rows.length === 0) {
    return <p className="detail-empty">No orders available.</p>;
  }

  return (
    <ul className="detail-list">
      {rows.map((row, index) => (
        <li key={`${row.price}-${row.volume}-${index}`}>
          <strong>{formatNumber(row.price)} ISK</strong>
          <span>{formatNumber(row.volume)} units</span>
          <span>{formatNumber(row.order_value)} order value</span>
          {row.cumulative_volume !== undefined && row.cumulative_volume !== null ? (
            <span>{formatNumber(row.cumulative_volume)} cumulative</span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function ItemDetailPanel({ detail, isLoading = false }: Props) {
  if (isLoading) {
    return (
      <section className="panel detail-panel">
        <div className="panel-header">
          <h2>Execution Context</h2>
          <span>Loading item detail…</span>
        </div>
      </section>
    );
  }

  if (detail === undefined) {
    return (
      <section className="panel detail-panel">
        <div className="panel-header">
          <h2>Execution Context</h2>
          <span>Select an item to inspect its detail.</span>
        </div>
      </section>
    );
  }

  return (
    <section className="panel detail-panel">
      <div className="panel-header">
        <h2>Execution Context</h2>
        <span>{detail.item_name}</span>
      </div>
      <div className="detail-grid">
        <div>
          <h3>Target Market Sell Orders</h3>
          {renderOrders(detail.target_market_sell_orders)}
        </div>
        <div>
          <h3>Source Market Sell Orders</h3>
          {renderOrders(detail.source_market_sell_orders)}
        </div>
        <div>
          <h3>Source Market Buy Orders</h3>
          {renderOrders(detail.source_market_buy_orders)}
        </div>
        <div>
          <h3>Trade Metrics Summary</h3>
          <dl className="detail-metrics">
            <div>
              <dt>Demand Source</dt>
              <dd>{detail.metrics.demand_source}</dd>
            </div>
            <div>
              <dt>ROI Now</dt>
              <dd>{(detail.metrics.roi_now * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt>Profit Now</dt>
              <dd>{formatNumber(detail.metrics.target_now_profit)} ISK</dd>
            </div>
            <div>
              <dt>Risk</dt>
              <dd>{(detail.metrics.risk_pct * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt>DOS</dt>
              <dd>{formatNumber(detail.metrics.target_dos)}</dd>
            </div>
            <div>
              <dt>Shipping</dt>
              <dd>{formatNumber(detail.metrics.shipping_cost)} ISK</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
}
