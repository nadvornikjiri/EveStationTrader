export function TradeControls() {
  return (
    <section className="panel controls-grid">
      <label>
        <span>Target Market</span>
        <select defaultValue="jita">
          <option value="jita">Jita IV - Moon 4</option>
          <option value="perimeter">Perimeter Market Keepstar</option>
        </select>
      </label>
      <label>
        <span>Source Regions</span>
        <select defaultValue="major">
          <option value="major">Major Trade Hub Regions</option>
          <option value="all">All Regions</option>
        </select>
      </label>
      <label>
        <span>Analysis Period</span>
        <select defaultValue="14">
          <option value="3">3 days</option>
          <option value="7">7 days</option>
          <option value="14">14 days</option>
          <option value="30">30 days</option>
        </select>
      </label>
      <label>
        <span>Item Search</span>
        <input placeholder="Search items" />
      </label>
      <label>
        <span>Min ROI</span>
        <input defaultValue="0.05" />
      </label>
      <label>
        <span>Warning Threshold</span>
        <input defaultValue="50" />
      </label>
    </section>
  );
}
