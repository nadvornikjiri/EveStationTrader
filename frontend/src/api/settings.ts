import { apiGet, apiPut } from "./client";

export type UserSettings = {
  default_analysis_period_days: number;
  trade_groups_page_size: number;
  debug_enabled: boolean;
  sales_tax_rate: number;
  broker_fee_rate: number;
  default_user_structure_poll_interval_minutes: number;
  snapshot_retention_days: number;
  fallback_policy: string;
  shipping_cost_per_m3: number;
  target_market_location_ids: number[];
  source_region_ids: number[];
  default_filters: Record<string, unknown>;
};

export type RegionOption = {
  region_id: number;
  name: string;
};

export function getSettings() {
  return apiGet<UserSettings>("/settings");
}

export function getSourceRegionOptions() {
  return apiGet<RegionOption[]>("/settings/source-regions");
}

export function updateSettings(settings: UserSettings) {
  return apiPut<UserSettings>("/settings", settings);
}
