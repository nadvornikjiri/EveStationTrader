import { apiGet } from "./client";

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
  confidence_score_summary: number;
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
  confidence_score: number;
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

export async function getTargets(): Promise<TargetLocation[]> {
  return apiGet<TargetLocation[]>("/targets");
}

export async function getSourceSummaries(
  targetLocationId: number,
  periodDays: number,
): Promise<SourceSummary[]> {
  return apiGet<SourceSummary[]>(
    `/opportunities/source-summaries?target_location_id=${targetLocationId}&period_days=${periodDays}`,
  );
}

export async function getOpportunityItems(
  targetLocationId: number,
  sourceLocationId: number,
  periodDays: number,
): Promise<OpportunityItem[]> {
  return apiGet<OpportunityItem[]>(
    `/opportunities/items?target_location_id=${targetLocationId}&source_location_id=${sourceLocationId}&period_days=${periodDays}`,
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
