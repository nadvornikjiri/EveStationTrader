import math

from app.domain.rules import (
    calculate_capital_required,
    calculate_net_purchase_units,
    calculate_purchase_units,
    calculate_roi,
    calculate_target_dos,
    calculate_target_now_profit,
    calculate_target_period_profit,
)


def test_profit_formulas() -> None:
    assert math.isclose(calculate_target_now_profit(100, 80), 20)
    assert math.isclose(calculate_target_period_profit(110, 80), 30)


def test_capital_required_and_roi_and_purchase_units() -> None:
    profit = calculate_target_now_profit(125, 100)
    assert calculate_capital_required(100, 7) == 700
    assert math.isclose(calculate_roi(profit, 100), 0.25)
    assert calculate_purchase_units(15, 8) == 8
    assert calculate_purchase_units(2, 8) == 2


def test_net_purchase_units_subtracts_inventory() -> None:
    assert calculate_net_purchase_units(50, 10, 5, 3) == 32  # 50 - 10 - 5 - 3
    assert calculate_net_purchase_units(10, 5, 5, 5) == 0.0  # floor at zero
    assert calculate_net_purchase_units(100, 0, 0, 0) == 100  # no inventory


def test_target_dos_handles_tiny_demand() -> None:
    assert calculate_target_dos(100, 0) > 1_000_000
    assert calculate_roi(10, 0) == 0.0
