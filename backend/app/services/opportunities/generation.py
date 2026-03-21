from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.schemas.trade import OpportunityItemRow
from app.domain.rules import (
    calculate_capital_required,
    calculate_purchase_units,
    calculate_risk_pct,
    calculate_roi,
    calculate_target_dos,
    calculate_target_now_profit,
    calculate_target_period_profit,
    calculate_warning_flag,
)
from app.models.all_models import (
    Item,
    Location,
    MarketDemandResolved,
    MarketPricePeriod,
    OpportunityItem,
    OpportunitySourceSummary,
    System,
)
from app.services.opportunities.aggregator import aggregate_source_summary


@dataclass
class OpportunityGenerationResult:
    item_count: int
    summary_count: int


class OpportunityGenerationService:
    def generate_for_target(
        self,
        session: Session,
        *,
        target_location_id: int,
        source_location_ids: list[int],
        type_ids: list[int],
        period_days: int,
        sales_tax_rate: float = 0.036,
        broker_fee_rate: float = 0.03,
        warning_threshold: float = 0.5,
        shipping_cost_per_m3: float = 0.0,
    ) -> OpportunityGenerationResult:
        if not source_location_ids or not type_ids:
            return OpportunityGenerationResult(item_count=0, summary_count=0)

        normalized_source_ids = list(dict.fromkeys(source_location_ids))
        normalized_type_ids = list(dict.fromkeys(type_ids))
        computed_at = datetime.now(UTC)

        session.execute(
            delete(OpportunityItem).where(
                OpportunityItem.target_location_id == target_location_id,
                OpportunityItem.source_location_id.in_(normalized_source_ids),
                OpportunityItem.type_id.in_(normalized_type_ids),
                OpportunityItem.period_days == period_days,
            )
        )
        session.execute(
            delete(OpportunitySourceSummary).where(
                OpportunitySourceSummary.target_location_id == target_location_id,
                OpportunitySourceSummary.source_location_id.in_(normalized_source_ids),
                OpportunitySourceSummary.period_days == period_days,
            )
        )

        items = {
            row.id: row
            for row in session.scalars(select(Item).where(Item.id.in_(normalized_type_ids))).all()
        }
        target_prices = {
            row.type_id: row
            for row in session.scalars(
                select(MarketPricePeriod).where(
                    MarketPricePeriod.location_id == target_location_id,
                    MarketPricePeriod.type_id.in_(normalized_type_ids),
                    MarketPricePeriod.period_days == period_days,
                )
            ).all()
        }
        demands = {
            row.type_id: row
            for row in session.scalars(
                select(MarketDemandResolved).where(
                    MarketDemandResolved.location_id == target_location_id,
                    MarketDemandResolved.type_id.in_(normalized_type_ids),
                    MarketDemandResolved.period_days == period_days,
                )
            ).all()
        }
        source_prices = {
            (row.location_id, row.type_id): row
            for row in session.scalars(
                select(MarketPricePeriod).where(
                    MarketPricePeriod.location_id.in_(normalized_source_ids),
                    MarketPricePeriod.type_id.in_(normalized_type_ids),
                    MarketPricePeriod.period_days == period_days,
                )
            ).all()
        }
        source_locations = {
            row.id: row
            for row in session.scalars(
                select(Location).where(Location.id.in_(normalized_source_ids))
            ).all()
        }
        systems = {
            row.id: row
            for row in session.scalars(
                select(System).where(System.id.in_([location.system_id for location in source_locations.values()]))
            ).all()
        }

        generated_items: list[OpportunityItem] = []
        source_rows: dict[int, list[OpportunityItemRow]] = {}

        for source_location_id in normalized_source_ids:
            source_location = source_locations.get(source_location_id)
            if source_location is None:
                continue
            source_system = systems.get(source_location.system_id)
            source_security_status = source_system.security_status if source_system is not None else 0.0

            for type_id in normalized_type_ids:
                item = items.get(type_id)
                source_price = source_prices.get((source_location_id, type_id))
                target_price = target_prices.get(type_id)
                demand = demands.get(type_id)
                if item is None or source_price is None or target_price is None or demand is None:
                    continue

                source_units_available = 0.0
                target_supply_units = 0.0
                purchase_units = calculate_purchase_units(source_units_available, demand.demand_day)
                shipping_cost = item.volume_m3 * purchase_units * shipping_cost_per_m3
                risk_pct = calculate_risk_pct(target_price.period_avg_price, target_price.current_price)
                warning_flag = calculate_warning_flag(risk_pct, warning_threshold)
                target_now_profit = calculate_target_now_profit(
                    target_price.current_price,
                    source_price.current_price,
                    sales_tax_rate,
                    broker_fee_rate,
                )
                target_period_profit = calculate_target_period_profit(
                    target_price.period_avg_price,
                    source_price.current_price,
                    sales_tax_rate,
                    broker_fee_rate,
                )
                capital_required = calculate_capital_required(source_price.current_price, demand.demand_day)
                roi_now = calculate_roi(target_now_profit, source_price.current_price)
                roi_period = calculate_roi(target_period_profit, source_price.current_price)
                target_dos = calculate_target_dos(target_supply_units, demand.demand_day)

                generated_item = OpportunityItem(
                    target_location_id=target_location_id,
                    source_location_id=source_location_id,
                    type_id=type_id,
                    period_days=period_days,
                    purchase_units=purchase_units,
                    source_units_available=source_units_available,
                    target_demand_day=demand.demand_day,
                    target_supply_units=target_supply_units,
                    target_dos=target_dos,
                    in_transit_units=0.0,
                    assets_units=0.0,
                    active_sell_orders_units=0.0,
                    source_station_sell_price=source_price.current_price,
                    target_station_sell_price=target_price.current_price,
                    target_period_avg_price=target_price.period_avg_price,
                    risk_pct=risk_pct,
                    warning_flag=warning_flag,
                    target_now_profit=target_now_profit,
                    target_period_profit=target_period_profit,
                    capital_required=capital_required,
                    roi_now=roi_now,
                    roi_period=roi_period,
                    source_security_status=source_security_status,
                    item_volume_m3=item.volume_m3,
                    shipping_cost=shipping_cost,
                    demand_source=demand.demand_source,
                    confidence_score=demand.confidence_score,
                    computed_at=computed_at,
                )
                session.add(generated_item)
                generated_items.append(generated_item)

                source_rows.setdefault(source_location_id, []).append(
                    OpportunityItemRow(
                        type_id=item.type_id,
                        item_name=item.name,
                        source_security_status=source_security_status,
                        purchase_units=purchase_units,
                        source_units_available=source_units_available,
                        target_demand_day=demand.demand_day,
                        target_supply_units=target_supply_units,
                        target_dos=target_dos,
                        in_transit_units_item=0.0,
                        assets_units_item=0.0,
                        active_sell_orders_units_item=0.0,
                        source_station_sell_price=source_price.current_price,
                        target_station_sell_price=target_price.current_price,
                        target_period_avg_price=target_price.period_avg_price,
                        risk_pct=risk_pct,
                        warning_flag=warning_flag,
                        target_now_profit=target_now_profit,
                        target_period_profit=target_period_profit,
                        capital_required=capital_required,
                        roi_now=roi_now,
                        roi_period=roi_period,
                        item_volume_m3=item.volume_m3,
                        shipping_cost=shipping_cost,
                        demand_source=demand.demand_source,
                        confidence_score=demand.confidence_score,
                    )
                )

        summary_count = 0
        for source_location_id, rows in source_rows.items():
            source_location = source_locations[source_location_id]
            summary = aggregate_source_summary(source_location_id, source_location.name, rows)
            session.add(
                OpportunitySourceSummary(
                    target_location_id=target_location_id,
                    source_location_id=source_location_id,
                    source_security_status=summary.source_security_status,
                    period_days=period_days,
                    purchase_units_total=summary.purchase_units_total,
                    source_units_available_total=summary.source_units_available_total,
                    target_demand_day_total=summary.target_demand_day_total,
                    target_supply_units_total=summary.target_supply_units_total,
                    target_dos_weighted=summary.target_dos_weighted,
                    in_transit_units=summary.in_transit_units,
                    assets_units=summary.assets_units,
                    active_sell_orders_units=summary.active_sell_orders_units,
                    source_avg_price_weighted=summary.source_avg_price_weighted,
                    target_now_price_weighted=summary.target_now_price_weighted,
                    target_period_avg_price_weighted=summary.target_period_avg_price_weighted,
                    risk_pct_weighted=summary.risk_pct_weighted,
                    warning_count=summary.warning_count,
                    target_now_profit_weighted=summary.target_now_profit_weighted,
                    target_period_profit_weighted=summary.target_period_profit_weighted,
                    capital_required_total=summary.capital_required_total,
                    roi_now_weighted=summary.roi_now_weighted,
                    roi_period_weighted=summary.roi_period_weighted,
                    total_item_volume_m3=summary.total_item_volume_m3,
                    shipping_cost_total=summary.shipping_cost_total,
                    demand_source_summary=summary.demand_source_summary,
                    confidence_score_summary=summary.confidence_score_summary,
                    computed_at=computed_at,
                )
            )
            summary_count += 1

        session.commit()
        return OpportunityGenerationResult(item_count=len(generated_items), summary_count=summary_count)
