from __future__ import annotations

from .models import Hub, Opportunity


def render_table(source_hub: Hub, destination_hub: Hub, opportunities: list[Opportunity]) -> str:
    if not opportunities:
        return (
            f"No opportunities matched the current filters for {source_hub.key} -> {destination_hub.key}. "
            "Try lowering the profit or ROI threshold."
        )

    lines = [
        f"Opportunities from {source_hub.name} to {destination_hub.name}",
        "",
        "Item | Strategy | Buy | Sell Ref | Net/Unit | ROI % | Units | Profit",
        "--- | --- | ---: | ---: | ---: | ---: | ---: | ---:",
    ]

    for item in opportunities:
        sell_ref = item.destination_buy_price if item.strategy == "instant" else item.destination_sell_price
        lines.append(
            " | ".join(
                [
                    item.item_name,
                    item.strategy,
                    f"{item.source_buy_price:,.2f}",
                    f"{sell_ref:,.2f}" if sell_ref is not None else "-",
                    f"{item.net_profit_per_unit:,.2f}",
                    f"{item.roi_percent:,.2f}",
                    f"{item.tradable_units:,}",
                    f"{item.estimated_profit:,.2f}",
                ]
            )
        )

    return "\n".join(lines)
