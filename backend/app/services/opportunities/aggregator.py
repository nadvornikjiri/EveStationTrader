from app.api.schemas.trade import OpportunityItemRow, SourceSummary


def aggregate_source_summary(source_location_id: int, source_market_name: str, items: list[OpportunityItemRow]) -> SourceSummary:
    total_purchase_units = sum(item.purchase_units for item in items)
    if not items:
        raise ValueError("items cannot be empty")
    total_weight = sum(max(item.purchase_units, 1.0) for item in items)

    def weighted(attr: str) -> float:
        return sum(getattr(item, attr) * max(item.purchase_units, 1.0) for item in items) / total_weight

    return SourceSummary(
        source_location_id=source_location_id,
        source_market_name=source_market_name,
        source_security_status=weighted("source_security_status"),
        purchase_units_total=total_purchase_units,
        source_units_available_total=sum(item.source_units_available for item in items),
        target_demand_day_total=sum(item.target_demand_day for item in items),
        target_supply_units_total=sum(item.target_supply_units for item in items),
        target_dos_weighted=weighted("target_dos"),
        in_transit_units=sum(item.in_transit_units_item for item in items),
        assets_units=sum(item.assets_units_item for item in items),
        active_sell_orders_units=sum(item.active_sell_orders_units_item for item in items),
        source_avg_price_weighted=weighted("source_station_sell_price"),
        target_now_price_weighted=weighted("target_station_sell_price"),
        target_period_avg_price_weighted=weighted("target_period_avg_price"),
        target_now_profit_weighted=weighted("target_now_profit"),
        target_period_profit_weighted=weighted("target_period_profit"),
        capital_required_total=sum(item.capital_required for item in items),
        roi_now_weighted=weighted("roi_now"),
        roi_period_weighted=weighted("roi_period"),
        total_item_volume_m3=sum(item.item_volume_m3 * item.purchase_units for item in items),
        shipping_cost_total=sum(item.shipping_cost for item in items),
        demand_source_summary=items[0].demand_source if len({item.demand_source for item in items}) == 1 else "Mixed",
        confidence_score_summary=min(item.confidence_score for item in items),
    )
