from app.domain.constants import EPSILON


def calculate_risk_pct(target_period_avg_price: float, target_station_sell_price: float) -> float:
    if abs(target_station_sell_price) < EPSILON:
        return 0.0
    return (target_period_avg_price - target_station_sell_price) / target_station_sell_price


def calculate_warning_flag(risk_pct: float, threshold: float) -> bool:
    return abs(risk_pct) > threshold


def calculate_target_now_profit(
    target_station_sell_price: float,
    source_station_sell_price: float,
    sales_tax_rate: float,
    broker_fee_rate: float,
) -> float:
    return target_station_sell_price * (1 - sales_tax_rate - broker_fee_rate) - source_station_sell_price


def calculate_target_period_profit(
    target_period_avg_price: float,
    source_station_sell_price: float,
    sales_tax_rate: float,
    broker_fee_rate: float,
) -> float:
    return target_period_avg_price * (1 - sales_tax_rate - broker_fee_rate) - source_station_sell_price


def calculate_capital_required(source_station_sell_price: float, target_demand_day: float) -> float:
    return source_station_sell_price * target_demand_day


def calculate_roi(profit: float, source_station_sell_price: float) -> float:
    if abs(source_station_sell_price) < EPSILON:
        return 0.0
    return profit / source_station_sell_price


def calculate_target_dos(target_supply_units: float, target_demand_day: float) -> float:
    return target_supply_units / max(target_demand_day, EPSILON)


def calculate_purchase_units(source_units_available: float, target_demand_day: float) -> float:
    return min(source_units_available, target_demand_day)
