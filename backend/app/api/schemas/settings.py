from pydantic import BaseModel


class UserSettingsResponse(BaseModel):
    default_analysis_period_days: int = 14
    trade_groups_page_size: int = 20
    debug_enabled: bool = False
    sales_tax_rate: float = 0.036
    broker_fee_rate: float = 0.03
    default_user_structure_poll_interval_minutes: int = 30
    snapshot_retention_days: int = 30
    fallback_policy: str = "regional_fallback"
    shipping_cost_per_m3: float = 350.0
    target_market_location_ids: list[int] = []
    source_region_ids: list[int] = []
    default_filters: dict = {}


class UserSettingsUpdate(UserSettingsResponse):
    pass


class RegionOption(BaseModel):
    region_id: int
    name: str
