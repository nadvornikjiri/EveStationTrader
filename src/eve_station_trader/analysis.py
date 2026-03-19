from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .models import BestOrders, Hub, MarketOrder, Opportunity


@dataclass(frozen=True)
class AnalysisSettings:
    sales_tax: float
    destination_broker_fee: float
    minimum_profit: float
    minimum_roi_percent: float
    top_n: int
    strategy: str
    cargo_volume_by_type: dict[int, float] | None = None


def summarize_hub_orders(orders: list[MarketOrder], hub: Hub) -> dict[int, BestOrders]:
    per_type: dict[int, dict[str, float | int | None]] = defaultdict(
        lambda: {
            "best_sell_price": None,
            "best_sell_volume": 0,
            "best_buy_price": None,
            "best_buy_volume": 0,
        }
    )

    for order in orders:
        if order.location_id != hub.location_id or order.volume_remain <= 0:
            continue

        slot = per_type[order.type_id]
        if order.is_buy_order:
            current = slot["best_buy_price"]
            if current is None or order.price > current:
                slot["best_buy_price"] = order.price
                slot["best_buy_volume"] = order.volume_remain
            elif order.price == current:
                slot["best_buy_volume"] = int(slot["best_buy_volume"]) + order.volume_remain
        else:
            current = slot["best_sell_price"]
            if current is None or order.price < current:
                slot["best_sell_price"] = order.price
                slot["best_sell_volume"] = order.volume_remain
            elif order.price == current:
                slot["best_sell_volume"] = int(slot["best_sell_volume"]) + order.volume_remain

    return {
        type_id: BestOrders(
            best_sell_price=values["best_sell_price"],
            best_sell_volume=int(values["best_sell_volume"]),
            best_buy_price=values["best_buy_price"],
            best_buy_volume=int(values["best_buy_volume"]),
        )
        for type_id, values in per_type.items()
    }


def find_opportunities(
    source_hub: Hub,
    destination_hub: Hub,
    source_orders: dict[int, BestOrders],
    destination_orders: dict[int, BestOrders],
    item_names: dict[int, str],
    settings: AnalysisSettings,
) -> list[Opportunity]:
    results: list[Opportunity] = []
    shared_type_ids = sorted(set(source_orders) & set(destination_orders))

    for type_id in shared_type_ids:
        source = source_orders[type_id]
        destination = destination_orders[type_id]
        if source.best_sell_price is None or source.best_sell_volume <= 0:
            continue

        destination_price = _destination_reference_price(destination, settings.strategy)
        if destination_price is None:
            continue

        tradable_units = min(source.best_sell_volume, _destination_volume(destination, settings.strategy))
        if tradable_units <= 0:
            continue

        revenue_per_unit = destination_price * (1 - settings.sales_tax)
        if settings.strategy == "relist":
            revenue_per_unit -= destination_price * settings.destination_broker_fee

        source_buy_price = source.best_sell_price
        spread_per_unit = destination_price - source_buy_price
        net_profit_per_unit = revenue_per_unit - source_buy_price
        estimated_profit = net_profit_per_unit * tradable_units
        roi_percent = (net_profit_per_unit / source_buy_price) * 100 if source_buy_price else 0.0

        if estimated_profit < settings.minimum_profit or roi_percent < settings.minimum_roi_percent:
            continue

        cargo_volume = None
        profit_per_m3 = None
        if settings.cargo_volume_by_type:
            cargo_volume = settings.cargo_volume_by_type.get(type_id)
            if cargo_volume and cargo_volume > 0:
                profit_per_m3 = net_profit_per_unit / cargo_volume

        results.append(
            Opportunity(
                type_id=type_id,
                item_name=item_names.get(type_id, f"Type {type_id}"),
                source_hub=source_hub.name,
                destination_hub=destination_hub.name,
                source_buy_price=source_buy_price,
                destination_sell_price=destination.best_sell_price or 0.0,
                destination_buy_price=destination.best_buy_price,
                tradable_units=tradable_units,
                spread_per_unit=spread_per_unit,
                net_profit_per_unit=net_profit_per_unit,
                estimated_profit=estimated_profit,
                roi_percent=roi_percent,
                profit_per_m3=profit_per_m3,
                strategy=settings.strategy,
            )
        )

    results.sort(key=lambda item: (item.estimated_profit, item.roi_percent), reverse=True)
    return results[: settings.top_n]


def _destination_reference_price(destination: BestOrders, strategy: str) -> float | None:
    if strategy == "instant":
        return destination.best_buy_price
    return destination.best_sell_price


def _destination_volume(destination: BestOrders, strategy: str) -> int:
    if strategy == "instant":
        return destination.best_buy_volume
    return destination.best_sell_volume
