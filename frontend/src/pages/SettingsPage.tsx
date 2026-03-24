import { FormEvent, useEffect, useState } from "react";

import type { UserSettings } from "../api/settings";
import { useSettings, useUpdateSettings } from "../hooks/useSettingsData";

const DEFAULT_SETTINGS: UserSettings = {
  default_analysis_period_days: 14,
  warning_threshold_pct: 0.5,
  warning_enabled: true,
  debug_enabled: false,
  sales_tax_rate: 0.036,
  broker_fee_rate: 0.03,
  min_confidence_for_local_structure_demand: 0.75,
  default_user_structure_poll_interval_minutes: 30,
  snapshot_retention_days: 30,
  fallback_policy: "regional_fallback",
  shipping_cost_per_m3: 350,
  default_filters: {
    min_item_profit: 15_000_000,
    min_order_margin_pct: 0.2,
    roi_now: 0.05,
    target_demand_day: 1,
  },
};

export function SettingsPage() {
  const settings = useSettings();
  const updateSettings = useUpdateSettings();
  const [formState, setFormState] = useState<UserSettings>(DEFAULT_SETTINGS);

  useEffect(() => {
    if (settings.data) {
      setFormState(settings.data);
    }
  }, [settings.data]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updateSettings.mutate(formState);
  }

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Settings</span>
          <h1>Trading Defaults</h1>
        </div>
      </header>
      <form className="panel controls-grid" onSubmit={handleSubmit}>
        <label className="settings-toggle">
          <div>
            <span>Debug Mode</span>
            <p>
              Enable verbose logging and limit sync processing to 1 region for faster iteration.
            </p>
          </div>
          <input
            aria-label="Debug Mode"
            checked={formState.debug_enabled}
            type="checkbox"
            onChange={(event) =>
              setFormState((current) => ({
                ...current,
                debug_enabled: event.target.checked,
              }))
            }
          />
        </label>
        <label>
          <span>Default Analysis Period</span>
          <input
            value={formState.default_analysis_period_days}
            onChange={(event) =>
              setFormState((current) => ({
                ...current,
                default_analysis_period_days: Number(event.target.value),
              }))
            }
          />
        </label>
        <label>
          <span>Warning Threshold %</span>
          <input
            value={formState.warning_threshold_pct}
            onChange={(event) =>
              setFormState((current) => ({
                ...current,
                warning_threshold_pct: Number(event.target.value),
              }))
            }
          />
        </label>
        <label>
          <span>Sales Tax Rate</span>
          <input
            value={formState.sales_tax_rate}
            onChange={(event) =>
              setFormState((current) => ({
                ...current,
                sales_tax_rate: Number(event.target.value),
              }))
            }
          />
        </label>
        <label>
          <span>Broker Fee Rate</span>
          <input
            value={formState.broker_fee_rate}
            onChange={(event) =>
              setFormState((current) => ({
                ...current,
                broker_fee_rate: Number(event.target.value),
              }))
            }
          />
        </label>
        <button disabled={updateSettings.isPending || settings.isLoading} type="submit">
          {updateSettings.isPending ? "Saving..." : "Save Settings"}
        </button>
      </form>
    </div>
  );
}
