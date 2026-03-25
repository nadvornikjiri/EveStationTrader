from datetime import datetime

from pydantic import BaseModel


class TargetLocation(BaseModel):
    location_id: int
    name: str
    location_type: str
    region_name: str
    system_name: str


class SourceSummary(BaseModel):
    source_location_id: int
    source_market_name: str
    source_security_status: float
    purchase_units_total: float
    source_units_available_total: float
    target_demand_day_total: float
    target_supply_units_total: float
    target_dos_weighted: float
    in_transit_units: float
    assets_units: float
    active_sell_orders_units: float
    source_avg_price_weighted: float
    target_now_price_weighted: float
    target_period_avg_price_weighted: float
    target_now_profit_weighted: float
    target_period_profit_weighted: float
    capital_required_total: float
    roi_now_weighted: float
    roi_period_weighted: float
    total_item_volume_m3: float
    shipping_cost_total: float
    demand_source_summary: str
    confidence_score_summary: float


class OpportunityItemRow(BaseModel):
    type_id: int
    item_name: str
    source_security_status: float
    purchase_units: float
    source_units_available: float
    target_demand_day: float
    target_supply_units: float
    target_dos: float
    in_transit_units_item: float
    assets_units_item: float
    active_sell_orders_units_item: float
    source_station_sell_price: float
    target_station_sell_price: float
    target_period_avg_price: float
    target_now_profit: float
    target_period_profit: float
    capital_required: float
    roi_now: float
    roi_period: float
    item_volume_m3: float
    shipping_cost: float
    demand_source: str
    confidence_score: float


class ItemOrderRow(BaseModel):
    price: float
    volume: int
    order_value: float
    cumulative_volume: int | None = None


class OpportunityItemDetail(BaseModel):
    type_id: int
    item_name: str
    target_market_sell_orders: list[ItemOrderRow]
    source_market_sell_orders: list[ItemOrderRow]
    source_market_buy_orders: list[ItemOrderRow]
    metrics: OpportunityItemRow


class TradeRefreshState(BaseModel):
    last_refresh_at: datetime
