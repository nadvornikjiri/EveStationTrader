import { FormEvent, useEffect, useState } from "react";

import type { UserSettings } from "../api/settings";
import { useSettings, useUpdateSettings } from "../hooks/useSettingsData";

const DEFAULT_SETTINGS: UserSettings = {
  default_analysis_period_days: 14,
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

type DefaultFilters = {
  min_item_profit: number;
  min_order_margin_pct: number;
  roi_now: number;
  target_demand_day: number;
};

function parseFilters(raw: Record<string, unknown>): DefaultFilters {
  return {
    min_item_profit: Number(raw.min_item_profit) || 15_000_000,
    min_order_margin_pct: Number(raw.min_order_margin_pct) || 0.2,
    roi_now: Number(raw.roi_now) || 0.05,
    target_demand_day: Number(raw.target_demand_day) || 1,
  };
}

function numericSetter(
  setFormState: React.Dispatch<React.SetStateAction<UserSettings>>,
  key: keyof UserSettings,
  min?: number,
) {
  return (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = Number(event.target.value);
    const clamped = min !== undefined ? Math.max(value, min) : value;
    setFormState((current) => ({ ...current, [key]: Number.isFinite(clamped) ? clamped : current[key] }));
  };
}

export function SettingsPage() {
  const settings = useSettings();
  const updateSettings = useUpdateSettings();
  const [formState, setFormState] = useState<UserSettings>(DEFAULT_SETTINGS);

  useEffect(() => {
    if (settings.data) {
      setFormState(settings.data);
    }
  }, [settings.data]);

  const filters = parseFilters(formState.default_filters);

  function updateFilter(key: keyof DefaultFilters, value: number) {
    setFormState((current) => ({
      ...current,
      default_filters: { ...current.default_filters, [key]: value },
    }));
  }

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
          <span>Default Analysis Period (days)</span>
          <input
            aria-label="Default Analysis Period"
            type="number"
            min={1}
            step={1}
            value={formState.default_analysis_period_days}
            onChange={numericSetter(setFormState, "default_analysis_period_days", 1)}
          />
        </label>
        <label>
          <span>Sales Tax Rate</span>
          <input
            aria-label="Sales Tax Rate"
            type="number"
            min={0}
            max={1}
            step={0.001}
            value={formState.sales_tax_rate}
            onChange={numericSetter(setFormState, "sales_tax_rate", 0)}
          />
        </label>
        <label>
          <span>Broker Fee Rate</span>
          <input
            aria-label="Broker Fee Rate"
            type="number"
            min={0}
            max={1}
            step={0.001}
            value={formState.broker_fee_rate}
            onChange={numericSetter(setFormState, "broker_fee_rate", 0)}
          />
        </label>
        <label>
          <span>Min Confidence for Local Demand</span>
          <input
            aria-label="Min Confidence"
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={formState.min_confidence_for_local_structure_demand}
            onChange={numericSetter(setFormState, "min_confidence_for_local_structure_demand", 0)}
          />
        </label>
        <label>
          <span>Structure Poll Interval (min)</span>
          <input
            aria-label="Poll Interval"
            type="number"
            min={5}
            step={5}
            value={formState.default_user_structure_poll_interval_minutes}
            onChange={numericSetter(setFormState, "default_user_structure_poll_interval_minutes", 5)}
          />
        </label>
        <label>
          <span>Snapshot Retention (days)</span>
          <input
            aria-label="Retention Days"
            type="number"
            min={1}
            step={1}
            value={formState.snapshot_retention_days}
            onChange={numericSetter(setFormState, "snapshot_retention_days", 1)}
          />
        </label>
        <label>
          <span>Fallback Policy</span>
          <select
            aria-label="Fallback Policy"
            value={formState.fallback_policy}
            onChange={(event) =>
              setFormState((current) => ({ ...current, fallback_policy: event.target.value }))
            }
          >
            <option value="regional_fallback">Regional Fallback</option>
            <option value="zero">Zero (No Fallback)</option>
          </select>
        </label>
        <label>
          <span>Shipping Cost per m3 (ISK)</span>
          <input
            aria-label="Shipping Cost"
            type="number"
            min={0}
            step={50}
            value={formState.shipping_cost_per_m3}
            onChange={numericSetter(setFormState, "shipping_cost_per_m3", 0)}
          />
        </label>

        <fieldset className="settings-fieldset">
          <legend>Default Trade Filters</legend>
          <label>
            <span>Min Item Profit (ISK)</span>
            <input
              aria-label="Default Min Profit"
              type="number"
              min={0}
              step={1_000_000}
              value={filters.min_item_profit}
              onChange={(e) => updateFilter("min_item_profit", Math.max(0, Number(e.target.value) || 0))}
            />
          </label>
          <label>
            <span>Min Order Margin %</span>
            <input
              aria-label="Default Min Margin"
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={filters.min_order_margin_pct}
              onChange={(e) => updateFilter("min_order_margin_pct", Math.max(0, Number(e.target.value) || 0))}
            />
          </label>
          <label>
            <span>Min ROI</span>
            <input
              aria-label="Default Min ROI"
              type="number"
              min={0}
              step={0.01}
              value={filters.roi_now}
              onChange={(e) => updateFilter("roi_now", Math.max(0, Number(e.target.value) || 0))}
            />
          </label>
          <label>
            <span>Min Demand / Day</span>
            <input
              aria-label="Default Min Demand"
              type="number"
              min={0}
              step={1}
              value={filters.target_demand_day}
              onChange={(e) => updateFilter("target_demand_day", Math.max(0, Number(e.target.value) || 0))}
            />
          </label>
        </fieldset>

        <button disabled={updateSettings.isPending || settings.isLoading} type="submit">
          {updateSettings.isPending ? "Saving..." : "Save Settings"}
        </button>
      </form>
    </div>
  );
}
