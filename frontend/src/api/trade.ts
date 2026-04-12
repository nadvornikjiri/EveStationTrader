import { apiDelete, apiGet, apiPost } from "./client";

export type TargetLocation = {
  location_id: number;
  name: string;
  location_type: string;
  region_name: string;
  system_name: string;
};

export type SourceSummary = {
  source_location_id: number;
  source_market_name: string;
  source_security_status: number;
  purchase_units_total: number;
  source_units_available_total: number;
  target_demand_day_total: number;
  target_supply_units_total: number;
  target_dos_weighted: number;
  in_transit_units: number;
  assets_units: number;
  active_sell_orders_units: number;
  source_avg_price_weighted: number;
  target_now_price_weighted: number;
  target_period_avg_price_weighted: number;
  target_now_profit_weighted: number;
  target_period_profit_weighted: number;
  capital_required_total: number;
  roi_now_weighted: number;
  roi_period_weighted: number;
  total_item_volume_m3: number;
  shipping_cost_total: number;
  demand_source_summary: string;
  esi_demand_day_total: number;
};

export type OpportunityItem = {
  type_id: number;
  item_name: string;
  source_security_status: number;
  purchase_units: number;
  source_units_available: number;
  target_demand_day: number;
  target_supply_units: number;
  target_dos: number;
  in_transit_units_item: number;
  assets_units_item: number;
  active_sell_orders_units_item: number;
  source_station_sell_price: number;
  target_station_sell_price: number;
  target_period_avg_price: number;
  target_now_profit: number;
  target_period_profit: number;
  capital_required: number;
  roi_now: number;
  roi_period: number;
  item_volume_m3: number;
  shipping_cost: number;
  demand_source: string;
  esi_demand_day: number;
};

export type TargetOpportunityItem = OpportunityItem & {
  source_location_id: number;
};

export type TradeFilters = {
  itemSearch: string;
  minProfit: string;
  minRoiNowPct: string;
  minDemandDay: string;
  maxDos: string;
  sourceType: string;
  minSecurity: string;
  demandSource: string;
  minEsiDemandDay: string;
};

export type ItemOrderRow = {
  price: number;
  volume: number;
  order_value: number;
  cumulative_volume?: number | null;
};

export type OpportunityItemDetail = {
  type_id: number;
  item_name: string;
  target_market_sell_orders: ItemOrderRow[];
  source_market_sell_orders: ItemOrderRow[];
  source_market_buy_orders: ItemOrderRow[];
  metrics: OpportunityItem;
};

export type TradeRefreshState = {
  last_refresh_at: string;
};

export type InTransitAssetRecord = {
  id: number;
  source_location_id: number;
  source_market_name: string;
  target_location_id: number;
  target_market_name: string;
  type_id: number;
  item_name: string;
  quantity: number;
  note: string | null;
  created_at: string;
  updated_at: string;
};

export async function getTargets(): Promise<TargetLocation[]> {
  return apiGet<TargetLocation[]>("/targets");
}

export async function getTargetOptions(): Promise<TargetLocation[]> {
  return apiGet<TargetLocation[]>("/targets/options");
}

export async function getSources(targetLocationId: number, periodDays: number): Promise<TargetLocation[]> {
  return apiGet<TargetLocation[]>(`/sources?target_location_id=${targetLocationId}&period_days=${periodDays}`);
}

export async function getSourceSummaries(
  targetLocationId: number,
  periodDays: number,
  filters: TradeFilters,
): Promise<SourceSummary[]> {
  const params = new URLSearchParams({
    target_location_id: `${targetLocationId}`,
    period_days: `${periodDays}`,
    source_type: filters.sourceType,
    min_security: filters.minSecurity,
    demand_source: filters.demandSource,
  });
  if (filters.itemSearch.trim().length > 0) {
    params.set("item_search", filters.itemSearch);
  }
  if (filters.minProfit.trim().length > 0) {
    params.set("min_profit", filters.minProfit);
  }
  if (filters.minRoiNowPct.trim().length > 0) {
    params.set("min_roi_now_pct", filters.minRoiNowPct);
  }
  if (filters.minDemandDay.trim().length > 0) {
    params.set("min_demand_day", filters.minDemandDay);
  }
  if (filters.maxDos.trim().length > 0) {
    params.set("max_dos", filters.maxDos);
  }
  if (filters.minEsiDemandDay.trim().length > 0) {
    params.set("min_esi_demand_day", filters.minEsiDemandDay);
  }
  return apiGet<SourceSummary[]>(
    `/opportunities/source-summaries?${params.toString()}`,
  );
}

export async function getOpportunityItems(
  targetLocationId: number,
  sourceLocationId: number,
  periodDays: number,
  filters: TradeFilters,
): Promise<OpportunityItem[]> {
  const params = new URLSearchParams({
    target_location_id: `${targetLocationId}`,
    source_location_id: `${sourceLocationId}`,
    period_days: `${periodDays}`,
    source_type: filters.sourceType,
    min_security: filters.minSecurity,
    demand_source: filters.demandSource,
  });
  if (filters.itemSearch.trim().length > 0) {
    params.set("item_search", filters.itemSearch);
  }
  if (filters.minProfit.trim().length > 0) {
    params.set("min_profit", filters.minProfit);
  }
  if (filters.minRoiNowPct.trim().length > 0) {
    params.set("min_roi_now_pct", filters.minRoiNowPct);
  }
  if (filters.minDemandDay.trim().length > 0) {
    params.set("min_demand_day", filters.minDemandDay);
  }
  if (filters.maxDos.trim().length > 0) {
    params.set("max_dos", filters.maxDos);
  }
  if (filters.minEsiDemandDay.trim().length > 0) {
    params.set("min_esi_demand_day", filters.minEsiDemandDay);
  }
  return apiGet<OpportunityItem[]>(
    `/opportunities/items?${params.toString()}`,
  );
}

export async function getTargetOpportunityItems(
  targetLocationId: number,
  periodDays: number,
): Promise<TargetOpportunityItem[]> {
  return apiGet<TargetOpportunityItem[]>(
    `/opportunities/target-items?target_location_id=${targetLocationId}&period_days=${periodDays}`,
  );
}

export async function getOpportunityItemDetail(
  targetLocationId: number,
  sourceLocationId: number,
  typeId: number,
  periodDays: number,
): Promise<OpportunityItemDetail> {
  return apiGet<OpportunityItemDetail>(
    `/opportunities/item-detail?target_location_id=${targetLocationId}&source_location_id=${sourceLocationId}&type_id=${typeId}&period_days=${periodDays}`,
  );
}

export async function refreshTradeOpportunities(
  targetLocationId: number,
  periodDays: number,
): Promise<TradeRefreshState> {
  return apiPost<TradeRefreshState>(
    `/opportunities/refresh?target_location_id=${targetLocationId}&period_days=${periodDays}`,
  );
}

export async function getInTransitAssets(targetLocationId: number): Promise<InTransitAssetRecord[]> {
  return apiGet<InTransitAssetRecord[]>(`/opportunities/in-transit?target_location_id=${targetLocationId}`);
}

export async function upsertInTransitAsset(body: {
  source_location_id: number;
  target_location_id: number;
  type_id: number;
  quantity: number;
  note?: string;
}): Promise<InTransitAssetRecord> {
  return apiPost<InTransitAssetRecord>("/opportunities/in-transit", body);
}

export async function deleteInTransitAsset(entryId: number): Promise<void> {
  return apiDelete(`/opportunities/in-transit/${entryId}`);
}
