import math

from app.domain.rules import (
    calculate_capital_required,
    calculate_purchase_units,
    calculate_roi,
    calculate_target_dos,
    calculate_target_now_profit,
    calculate_target_period_profit,
)


def test_profit_formulas() -> None:
    assert math.isclose(calculate_target_now_profit(100, 80, 0.036, 0.03), 13.4)
    assert math.isclose(calculate_target_period_profit(110, 80, 0.036, 0.03), 22.74)


def test_capital_required_and_roi_and_purchase_units() -> None:
    profit = calculate_target_now_profit(125, 100, 0.036, 0.03)
    assert calculate_capital_required(100, 7) == 700
    assert math.isclose(calculate_roi(profit, 100), 0.1675)
    assert calculate_purchase_units(15, 8) == 8
    assert calculate_purchase_units(2, 8) == 2


def test_target_dos_handles_tiny_demand() -> None:
    assert calculate_target_dos(100, 0) > 1_000_000
    assert calculate_roi(10, 0) == 0.0
