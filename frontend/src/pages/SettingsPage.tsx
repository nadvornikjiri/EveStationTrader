import { FormEvent, useEffect, useState } from "react";

import type { UserSettings } from "../api/settings";
import { useTargetOptions } from "../hooks/useTradeData";
import { useSettings, useUpdateSettings } from "../hooks/useSettingsData";

const KNOWN_SOURCE_REGIONS = [
  { region_id: 10000002, name: "The Forge" },
  { region_id: 10000043, name: "Domain" },
  { region_id: 10000032, name: "Sinq Laison" },
  { region_id: 10000042, name: "Metropolis" },
  { region_id: 10000030, name: "Heimatar" },
] as const;

const DEFAULT_SETTINGS: UserSettings = {
  default_analysis_period_days: 14,
  trade_groups_page_size: 20,
  debug_enabled: false,
  sales_tax_rate: 0.036,
  broker_fee_rate: 0.03,
  default_user_structure_poll_interval_minutes: 30,
  snapshot_retention_days: 30,
  fallback_policy: "regional_fallback",
  shipping_cost_per_m3: 350,
  target_market_location_ids: [],
  source_region_ids: [],
  default_filters: {
    min_item_profit: 15_000_000,
    roi_now: 0.20,
    target_demand_day: 1,
  },
};

type DefaultFilters = {
  min_item_profit: number;
  roi_now: number;
  target_demand_day: number;
};

function parseFilters(raw: Record<string, unknown>): DefaultFilters {
  return {
    min_item_profit: Number(raw.min_item_profit) || 15_000_000,
    roi_now: Number(raw.roi_now) || 0.20,
    target_demand_day: Number(raw.target_demand_day) || 1,
  };
}

function numericSetter(
  setFormState: React.Dispatch<React.SetStateAction<UserSettings>>,
  key: keyof UserSettings,
  setHasLocalEdits: React.Dispatch<React.SetStateAction<boolean>>,
  min?: number,
) {
  return (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = Number(event.target.value);
    const clamped = min !== undefined ? Math.max(value, min) : value;
    setHasLocalEdits(true);
    setFormState((current) => ({ ...current, [key]: Number.isFinite(clamped) ? clamped : current[key] }));
  };
}

export function SettingsPage() {
  const settings = useSettings();
  const updateSettings = useUpdateSettings();
  const targetOptions = useTargetOptions();
  const [formState, setFormState] = useState<UserSettings>(DEFAULT_SETTINGS);
  const [hasLocalEdits, setHasLocalEdits] = useState(false);

  useEffect(() => {
    if (settings.data && !hasLocalEdits) {
      setFormState(settings.data);
    }
  }, [hasLocalEdits, settings.data]);

  const filters = parseFilters(formState.default_filters);

  function updateFilter(key: keyof DefaultFilters, value: number) {
    setHasLocalEdits(true);
    setFormState((current) => ({
      ...current,
      default_filters: { ...current.default_filters, [key]: value },
    }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updateSettings.mutate(formState, {
      onSuccess: (nextSettings) => {
        setFormState(nextSettings);
        setHasLocalEdits(false);
      },
    });
  }

  function toggleTargetLocation(locationId: number) {
    setHasLocalEdits(true);
    setFormState((current) => {
      const selectedIds = current.target_market_location_ids.includes(locationId)
        ? current.target_market_location_ids.filter((id) => id !== locationId)
        : [...current.target_market_location_ids, locationId];
      return { ...current, target_market_location_ids: selectedIds };
    });
  }

  function toggleSourceRegion(regionId: number) {
    setHasLocalEdits(true);
    setFormState((current) => {
      const selectedIds = current.source_region_ids.includes(regionId)
        ? current.source_region_ids.filter((id) => id !== regionId)
        : [...current.source_region_ids, regionId];
      return { ...current, source_region_ids: selectedIds };
    });
  }

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Settings</span>
          <h1>Trading Defaults</h1>
        </div>
      </header>
      <form className="panel settings-form" onSubmit={handleSubmit}>
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
              {
                setHasLocalEdits(true);
                setFormState((current) => ({
                  ...current,
                  debug_enabled: event.target.checked,
                }));
              }
            }
          />
        </label>
        <div className="settings-sections">
          <section className="settings-card">
            <div className="settings-card-header">
              <h2>Operational Defaults</h2>
              <p>Core runtime and sync behavior.</p>
            </div>
            <div className="controls-grid settings-controls-grid">
              <label>
                <span>Default Analysis Period (days)</span>
                <input
                  aria-label="Default Analysis Period"
                  type="number"
                  min={1}
                  step={1}
                  value={formState.default_analysis_period_days}
                  onChange={numericSetter(setFormState, "default_analysis_period_days", setHasLocalEdits, 1)}
                />
              </label>
              <label>
                <span>Trade Groups per Page</span>
                <input
                  aria-label="Trade Groups per Page"
                  type="number"
                  min={1}
                  step={1}
                  value={formState.trade_groups_page_size}
                  onChange={numericSetter(setFormState, "trade_groups_page_size", setHasLocalEdits, 1)}
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
                  onChange={numericSetter(setFormState, "sales_tax_rate", setHasLocalEdits, 0)}
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
                  onChange={numericSetter(setFormState, "broker_fee_rate", setHasLocalEdits, 0)}
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
                  onChange={numericSetter(setFormState, "default_user_structure_poll_interval_minutes", setHasLocalEdits, 5)}
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
                  onChange={numericSetter(setFormState, "snapshot_retention_days", setHasLocalEdits, 1)}
                />
              </label>
              <label>
                <span>Fallback Policy</span>
                <select
                  aria-label="Fallback Policy"
                  value={formState.fallback_policy}
                  onChange={(event) => {
                    setHasLocalEdits(true);
                    setFormState((current) => ({ ...current, fallback_policy: event.target.value }));
                  }}
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
                  onChange={numericSetter(setFormState, "shipping_cost_per_m3", setHasLocalEdits, 0)}
                />
              </label>
            </div>
          </section>

          <section className="settings-card">
            <div className="settings-card-header">
              <h2>Target Market Hubs</h2>
              <p>Select the markets that should appear as destination hubs on the trade page.</p>
            </div>
            <div className="settings-checkbox-list" role="group" aria-label="Target Market Hubs">
              {(targetOptions.data ?? []).map((location) => (
                <label key={location.location_id} className="settings-toggle">
                  <div>
                    <span>{location.name}</span>
                    <p>
                      {location.system_name}, {location.region_name}
                    </p>
                  </div>
                  <input
                    aria-label={location.name}
                    type="checkbox"
                    checked={formState.target_market_location_ids.includes(location.location_id)}
                    onChange={() => toggleTargetLocation(location.location_id)}
                  />
                </label>
              ))}
            </div>
          </section>

          <section className="settings-card">
            <div className="settings-card-header">
              <h2>Source Regions</h2>
              <p>Select which EVE regions are scanned when syncing market orders.</p>
            </div>
            <div className="settings-checkbox-list" role="group" aria-label="Source Regions">
              {KNOWN_SOURCE_REGIONS.map((region) => (
                <label key={region.region_id} className="settings-toggle">
                  <div>
                    <span>{region.name}</span>
                  </div>
                  <input
                    aria-label={region.name}
                    type="checkbox"
                    checked={formState.source_region_ids.includes(region.region_id)}
                    onChange={() => toggleSourceRegion(region.region_id)}
                  />
                </label>
              ))}
            </div>
          </section>

          <fieldset className="settings-fieldset">
            <legend>Default Trade Filters</legend>
            <div className="controls-grid settings-controls-grid">
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
                <span>Min ROI Now %</span>
                <input
                  aria-label="Default Min ROI Now"
                  type="number"
                  min={0}
                  step={5}
                  value={filters.roi_now * 100}
                  onChange={(e) => updateFilter("roi_now", Math.max(0, Number(e.target.value) || 0) / 100)}
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
            </div>
          </fieldset>
        </div>

        <div className="settings-actions">
          <p className="settings-status">
            {hasLocalEdits ? "Unsaved changes" : "All settings saved"}
          </p>
          <button
            className="primary-button"
            disabled={updateSettings.isPending}
            type="submit"
          >
            {updateSettings.isPending ? "Saving..." : "Save Settings"}
          </button>
        </div>
      </form>
    </div>
  );
}
