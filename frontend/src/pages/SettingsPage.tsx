export function SettingsPage() {
  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Settings</span>
          <h1>Trading Defaults</h1>
        </div>
      </header>
      <section className="panel controls-grid">
        <label>
          <span>Default Analysis Period</span>
          <input defaultValue="14" />
        </label>
        <label>
          <span>Warning Threshold %</span>
          <input defaultValue="50" />
        </label>
        <label>
          <span>Sales Tax Rate</span>
          <input defaultValue="0.036" />
        </label>
        <label>
          <span>Broker Fee Rate</span>
          <input defaultValue="0.03" />
        </label>
      </section>
    </div>
  );
}
