import { apiGet, apiPut } from "./client";

export type UserSettings = {
  default_analysis_period_days: number;
  debug_enabled: boolean;
  sales_tax_rate: number;
  broker_fee_rate: number;
  min_confidence_for_local_structure_demand: number;
  default_user_structure_poll_interval_minutes: number;
  snapshot_retention_days: number;
  fallback_policy: string;
  shipping_cost_per_m3: number;
  default_filters: Record<string, unknown>;
};

export function getSettings() {
  return apiGet<UserSettings>("/settings");
}

export function updateSettings(settings: UserSettings) {
  return apiPut<UserSettings>("/settings", settings);
}
