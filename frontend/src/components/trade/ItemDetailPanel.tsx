export function ItemDetailPanel() {
  return (
    <section className="panel detail-panel">
      <div className="panel-header">
        <h2>Execution Context</h2>
        <span>Order-book detail scaffold</span>
      </div>
      <div className="detail-grid">
        <div>
          <h3>Target Market Sell Orders</h3>
          <p>Best ask stack, cumulative volume, and order value will render here.</p>
        </div>
        <div>
          <h3>Source Market Sell Orders</h3>
          <p>Source acquisition ladder and weighted basis will render here.</p>
        </div>
        <div>
          <h3>Source Market Buy Orders</h3>
          <p>Fallback liquidation context for adverse fills will render here.</p>
        </div>
        <div>
          <h3>Trade Metrics Summary</h3>
          <p>Spread, DOS, demand source, warning flag, ROI, and shipping context.</p>
        </div>
      </div>
    </section>
  );
}
