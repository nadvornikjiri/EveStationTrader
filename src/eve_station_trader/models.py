from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Hub:
    key: str
    name: str
    region_id: int
    location_id: int


@dataclass(frozen=True)
class MarketOrder:
    type_id: int
    location_id: int
    is_buy_order: bool
    price: float
    volume_remain: int
    min_volume: int
    range: str


@dataclass(frozen=True)
class BestOrders:
    best_sell_price: float | None
    best_sell_volume: int
    best_buy_price: float | None
    best_buy_volume: int


@dataclass(frozen=True)
class Opportunity:
    type_id: int
    item_name: str
    source_hub: str
    destination_hub: str
    source_buy_price: float
    destination_sell_price: float
    destination_buy_price: float | None
    tradable_units: int
    spread_per_unit: float
    net_profit_per_unit: float
    estimated_profit: float
    roi_percent: float
    profit_per_m3: float | None
    strategy: str
