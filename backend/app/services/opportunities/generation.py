from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Float, cast, delete, func, select
from sqlalchemy.orm import Session

from app.api.schemas.trade import OpportunityItemRow
from app.domain.rules import (
    calculate_capital_required,
    calculate_purchase_units,
    calculate_roi,
    calculate_target_dos,
    calculate_target_now_profit,
    calculate_target_period_profit,
)
from app.models.all_models import (
    EsiMarketOrder,
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
        replace_entire_target_scope: bool = False,
        sales_tax_rate: float = 0.036,
        broker_fee_rate: float = 0.03,
        shipping_cost_per_m3: float = 0.0,
    ) -> OpportunityGenerationResult:
        if not source_location_ids or not type_ids:
            return OpportunityGenerationResult(item_count=0, summary_count=0)

        normalized_source_ids = list(dict.fromkeys(source_location_ids))
        normalized_type_ids = list(dict.fromkeys(type_ids))
        computed_at = datetime.now(UTC)
        normalized_period_days = max(period_days, 1)

        if replace_entire_target_scope:
            session.execute(
                delete(OpportunityItem).where(
                    OpportunityItem.target_location_id == target_location_id,
                    OpportunityItem.period_days == period_days,
                )
            )
            session.execute(
                delete(OpportunitySourceSummary).where(
                    OpportunitySourceSummary.target_location_id == target_location_id,
                    OpportunitySourceSummary.period_days == period_days,
                )
            )
        else:
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
        # Aggregate sell-side volume from live market orders per (location, type)
        all_location_ids = [target_location_id] + normalized_source_ids
        sell_volume_rows = session.execute(
            select(
                EsiMarketOrder.location_id,
                EsiMarketOrder.type_id,
                func.sum(EsiMarketOrder.volume_remain),
            )
            .where(
                EsiMarketOrder.location_id.in_(all_location_ids),
                EsiMarketOrder.type_id.in_(normalized_type_ids),
                EsiMarketOrder.is_buy_order.is_(False),
            )
            .group_by(EsiMarketOrder.location_id, EsiMarketOrder.type_id)
        ).all()
        sell_volume: dict[tuple[int, int], float] = {
            (row[0], row[1]): float(row[2]) for row in sell_volume_rows
        }
        target_lowest_sell_price_rows = session.execute(
            select(
                EsiMarketOrder.type_id,
                func.min(EsiMarketOrder.price),
            )
            .where(
                EsiMarketOrder.location_id == target_location_id,
                EsiMarketOrder.type_id.in_(normalized_type_ids),
                EsiMarketOrder.is_buy_order.is_(False),
            )
            .group_by(EsiMarketOrder.type_id)
        ).all()
        target_lowest_sell_price: dict[int, float] = {
            row[0]: float(row[1]) for row in target_lowest_sell_price_rows if row[1] is not None
        }
        partition_by_location_type = (EsiMarketOrder.location_id, EsiMarketOrder.type_id)
        total_source_volume = func.sum(EsiMarketOrder.volume_remain).over(partition_by=partition_by_location_type)
        running_source_volume = func.sum(EsiMarketOrder.volume_remain).over(
            partition_by=partition_by_location_type,
            order_by=(EsiMarketOrder.price.asc(), EsiMarketOrder.issued.asc(), EsiMarketOrder.order_id.asc()),
        )
        purchase_units_expr = func.least(cast(total_source_volume, Float), MarketDemandResolved.buy_from_sell_yesterday)
        volume_before_expr = cast(running_source_volume - EsiMarketOrder.volume_remain, Float)
        consumed_volume_expr = func.least(
            cast(EsiMarketOrder.volume_remain, Float),
            func.greatest(purchase_units_expr - volume_before_expr, 0.0),
        )
        source_price_stage = (
            select(
                EsiMarketOrder.location_id.label("location_id"),
                EsiMarketOrder.type_id.label("type_id"),
                purchase_units_expr.label("purchase_units"),
                EsiMarketOrder.price.label("price"),
                consumed_volume_expr.label("consumed_volume"),
            )
            .join(
                MarketDemandResolved,
                (MarketDemandResolved.type_id == EsiMarketOrder.type_id)
                & (MarketDemandResolved.location_id == target_location_id)
                & (MarketDemandResolved.period_days == period_days),
            )
            .where(
                EsiMarketOrder.location_id.in_(normalized_source_ids),
                EsiMarketOrder.type_id.in_(normalized_type_ids),
                EsiMarketOrder.is_buy_order.is_(False),
                MarketDemandResolved.buy_from_sell_yesterday > 0,
            )
        ).subquery()
        source_effective_price_rows = session.execute(
            select(
                source_price_stage.c.location_id,
                source_price_stage.c.type_id,
                (
                    func.sum(source_price_stage.c.price * source_price_stage.c.consumed_volume)
                    / func.max(source_price_stage.c.purchase_units)
                ).label("effective_price"),
            )
            .where(source_price_stage.c.consumed_volume > 0)
            .group_by(source_price_stage.c.location_id, source_price_stage.c.type_id)
        ).all()
        source_effective_price: dict[tuple[int, int], float] = {
            (row[0], row[1]): float(row[2]) for row in source_effective_price_rows if row[2] is not None
        }
        source_keys = sorted(source_effective_price)
        actual_source_ids = sorted({location_id for location_id, _type_id in source_keys})
        source_locations = {
            row.id: row
            for row in session.scalars(select(Location).where(Location.id.in_(actual_source_ids))).all()
        }
        systems = {
            row.id: row
            for row in session.scalars(
                select(System).where(System.id.in_([location.system_id for location in source_locations.values()]))
            ).all()
        }

        generated_items: list[OpportunityItem] = []
        source_rows: dict[int, list[OpportunityItemRow]] = {}

        for source_location_id, type_id in source_keys:
            source_location = source_locations.get(source_location_id)
            if source_location is None:
                continue
            source_system = systems.get(source_location.system_id)
            source_security_status = source_system.security_status if source_system is not None else 0.0

            item = items.get(type_id)
            target_price = target_prices.get(type_id)
            demand = demands.get(type_id)
            source_now_price = source_effective_price.get((source_location_id, type_id))
            target_now_price = target_lowest_sell_price.get(type_id)
            if item is None or source_now_price is None or target_now_price is None or demand is None:
                continue

            target_demand_day = demand.buy_from_sell_period / normalized_period_days
            source_units_available = sell_volume.get((source_location_id, type_id), 0.0)
            target_supply_units = sell_volume.get((target_location_id, type_id), 0.0)
            purchase_units = calculate_purchase_units(source_units_available, demand.buy_from_sell_yesterday)
            shipping_cost = item.volume_m3 * purchase_units * shipping_cost_per_m3
            target_period_avg_price = (
                target_price.period_avg_price if target_price is not None else target_now_price
            )
            target_now_profit = calculate_target_now_profit(target_now_price, source_now_price)
            target_period_profit = calculate_target_period_profit(target_period_avg_price, source_now_price)
            capital_required = calculate_capital_required(source_now_price, purchase_units)
            roi_now = calculate_roi(target_now_profit, source_now_price)
            roi_period = calculate_roi(target_period_profit, source_now_price)
            target_dos = calculate_target_dos(target_supply_units, target_demand_day)

            generated_item = OpportunityItem(
                target_location_id=target_location_id,
                source_location_id=source_location_id,
                type_id=type_id,
                period_days=period_days,
                purchase_units=purchase_units,
                source_units_available=source_units_available,
                target_demand_day=target_demand_day,
                target_supply_units=target_supply_units,
                target_dos=target_dos,
                in_transit_units=0.0,
                assets_units=0.0,
                active_sell_orders_units=0.0,
                source_station_sell_price=source_now_price,
                target_station_sell_price=target_now_price,
                target_period_avg_price=target_period_avg_price,
                target_now_profit=target_now_profit,
                target_period_profit=target_period_profit,
                capital_required=capital_required,
                roi_now=roi_now,
                roi_period=roi_period,
                source_security_status=source_security_status,
                item_volume_m3=item.volume_m3,
                shipping_cost=shipping_cost,
                demand_source=demand.demand_source,
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
                    target_demand_day=target_demand_day,
                    target_supply_units=target_supply_units,
                    target_dos=target_dos,
                    in_transit_units_item=0.0,
                    assets_units_item=0.0,
                    active_sell_orders_units_item=0.0,
                    source_station_sell_price=source_now_price,
                    target_station_sell_price=target_now_price,
                    target_period_avg_price=target_period_avg_price,
                    target_now_profit=target_now_profit,
                    target_period_profit=target_period_profit,
                    capital_required=capital_required,
                    roi_now=roi_now,
                    roi_period=roi_period,
                    item_volume_m3=item.volume_m3,
                    shipping_cost=shipping_cost,
                    demand_source=demand.demand_source,
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
                    target_now_profit_weighted=summary.target_now_profit_weighted,
                    target_period_profit_weighted=summary.target_period_profit_weighted,
                    capital_required_total=summary.capital_required_total,
                    roi_now_weighted=summary.roi_now_weighted,
                    roi_period_weighted=summary.roi_period_weighted,
                    total_item_volume_m3=summary.total_item_volume_m3,
                    shipping_cost_total=summary.shipping_cost_total,
                    demand_source_summary=summary.demand_source_summary,
                    computed_at=computed_at,
                )
            )
            summary_count += 1

        session.commit()
        return OpportunityGenerationResult(item_count=len(generated_items), summary_count=summary_count)
