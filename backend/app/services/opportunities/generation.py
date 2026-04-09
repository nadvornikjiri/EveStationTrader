from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Float, case, cast, delete, func, select
from sqlalchemy.orm import Session

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
    NpcStationDemandPeriod,
    OpportunityItem,
    OpportunitySourceSummary,
    System,
)


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

        generated_count = 0
        all_location_ids = [target_location_id] + normalized_source_ids

        for type_id in normalized_type_ids:
            item = session.get(Item, type_id)
            demand = session.scalar(
                select(MarketDemandResolved).where(
                    MarketDemandResolved.location_id == target_location_id,
                    MarketDemandResolved.type_id == type_id,
                    MarketDemandResolved.period_days == period_days,
                )
            )
            if item is None or demand is None:
                continue
            if demand.buy_from_sell_yesterday <= 0:
                continue

            # Compute ESI traded volume (daily average) for this item at the target
            esi_demand_period = session.scalar(
                select(NpcStationDemandPeriod).where(
                    NpcStationDemandPeriod.location_id == target_location_id,
                    NpcStationDemandPeriod.type_id == type_id,
                    NpcStationDemandPeriod.period_days == period_days,
                )
            )
            esi_demand_day = 0.0
            if esi_demand_period is not None:
                esi_total = esi_demand_period.buy_from_sell_period + esi_demand_period.sell_to_buy_period
                esi_demand_day = esi_total / normalized_period_days

            target_price = session.scalar(
                select(MarketPricePeriod).where(
                    MarketPricePeriod.location_id == target_location_id,
                    MarketPricePeriod.type_id == type_id,
                    MarketPricePeriod.period_days == period_days,
                )
            )
            sell_volume_rows = session.execute(
                select(
                    EsiMarketOrder.location_id,
                    func.sum(EsiMarketOrder.volume_remain),
                )
                .where(
                    EsiMarketOrder.location_id.in_(all_location_ids),
                    EsiMarketOrder.type_id == type_id,
                    EsiMarketOrder.is_buy_order.is_(False),
                )
                .group_by(EsiMarketOrder.location_id)
            ).all()
            sell_volume = {
                location_id: float(volume)
                for location_id, volume in sell_volume_rows
                if volume is not None
            }
            target_now_price = session.scalar(
                select(func.min(EsiMarketOrder.price)).where(
                    EsiMarketOrder.location_id == target_location_id,
                    EsiMarketOrder.type_id == type_id,
                    EsiMarketOrder.is_buy_order.is_(False),
                )
            )
            if target_now_price is None:
                continue

            partition_by_location_type = (EsiMarketOrder.location_id, EsiMarketOrder.type_id)
            total_source_volume = func.sum(EsiMarketOrder.volume_remain).over(partition_by=partition_by_location_type)
            running_source_volume = func.sum(EsiMarketOrder.volume_remain).over(
                partition_by=partition_by_location_type,
                order_by=(EsiMarketOrder.price.asc(), EsiMarketOrder.issued.asc(), EsiMarketOrder.order_id.asc()),
            )
            purchase_units_expr = func.least(cast(total_source_volume, Float), demand.buy_from_sell_yesterday)
            volume_before_expr = cast(running_source_volume - EsiMarketOrder.volume_remain, Float)
            consumed_volume_expr = func.least(
                cast(EsiMarketOrder.volume_remain, Float),
                func.greatest(purchase_units_expr - volume_before_expr, 0.0),
            )
            source_price_stage = (
                select(
                    EsiMarketOrder.location_id.label("location_id"),
                    purchase_units_expr.label("purchase_units"),
                    EsiMarketOrder.price.label("price"),
                    consumed_volume_expr.label("consumed_volume"),
                )
                .where(
                    EsiMarketOrder.location_id.in_(normalized_source_ids),
                    EsiMarketOrder.type_id == type_id,
                    EsiMarketOrder.is_buy_order.is_(False),
                )
            ).subquery()
            source_effective_price_rows = session.execute(
                select(
                    source_price_stage.c.location_id,
                    (
                        func.sum(source_price_stage.c.price * source_price_stage.c.consumed_volume)
                        / func.max(source_price_stage.c.purchase_units)
                    ).label("effective_price"),
                )
                .where(source_price_stage.c.consumed_volume > 0)
                .group_by(source_price_stage.c.location_id)
            ).all()
            source_effective_price = {
                location_id: float(effective_price)
                for location_id, effective_price in source_effective_price_rows
                if effective_price is not None
            }
            actual_source_ids = sorted(source_effective_price)
            if not actual_source_ids:
                continue
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

            for source_location_id, source_now_price in source_effective_price.items():
                source_location = source_locations.get(source_location_id)
                if source_location is None:
                    continue
                source_system = systems.get(source_location.system_id)
                source_security_status = source_system.security_status if source_system is not None else 0.0
                source_units_available = sell_volume.get(source_location_id, 0.0)
                target_supply_units = sell_volume.get(target_location_id, 0.0)
                purchase_units = calculate_purchase_units(source_units_available, demand.buy_from_sell_yesterday)
                shipping_cost = item.volume_m3 * purchase_units * shipping_cost_per_m3
                target_period_avg_price = (
                    target_price.period_avg_price if target_price is not None else float(target_now_price)
                )
                target_demand_day = demand.buy_from_sell_period / normalized_period_days
                target_now_profit = calculate_target_now_profit(float(target_now_price), source_now_price)
                target_period_profit = calculate_target_period_profit(target_period_avg_price, source_now_price)
                capital_required = calculate_capital_required(source_now_price, purchase_units)
                roi_now = calculate_roi(target_now_profit, source_now_price)
                roi_period = calculate_roi(target_period_profit, source_now_price)
                target_dos = calculate_target_dos(target_supply_units, target_demand_day)

                session.add(
                    OpportunityItem(
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
                        target_station_sell_price=float(target_now_price),
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
                        esi_demand_day=esi_demand_day,
                        computed_at=computed_at,
                    )
                )
                generated_count += 1

        session.flush()
        summary_rows = self._summaries_for_sources(
            session,
            target_location_id=target_location_id,
            source_location_ids=normalized_source_ids,
            period_days=period_days,
            computed_at=computed_at,
        )
        for summary_row in summary_rows:
            session.add(summary_row)

        session.commit()
        return OpportunityGenerationResult(item_count=generated_count, summary_count=len(summary_rows))

    def _summaries_for_sources(
        self,
        session: Session,
        *,
        target_location_id: int,
        source_location_ids: list[int],
        period_days: int,
        computed_at: datetime,
    ) -> list[OpportunitySourceSummary]:
        if not source_location_ids:
            return []

        weight = case((OpportunityItem.purchase_units > 1.0, OpportunityItem.purchase_units), else_=1.0)
        summary_query = (
            select(
                OpportunityItem.source_location_id,
                (func.sum(OpportunityItem.source_security_status * weight) / func.sum(weight)).label("source_security_status"),
                func.sum(OpportunityItem.purchase_units).label("purchase_units_total"),
                func.sum(OpportunityItem.source_units_available).label("source_units_available_total"),
                func.sum(OpportunityItem.target_demand_day).label("target_demand_day_total"),
                func.sum(OpportunityItem.target_supply_units).label("target_supply_units_total"),
                (func.sum(OpportunityItem.target_dos * weight) / func.sum(weight)).label("target_dos_weighted"),
                func.sum(OpportunityItem.in_transit_units).label("in_transit_units"),
                func.sum(OpportunityItem.assets_units).label("assets_units"),
                func.sum(OpportunityItem.active_sell_orders_units).label("active_sell_orders_units"),
                (func.sum(OpportunityItem.source_station_sell_price * weight) / func.sum(weight)).label("source_avg_price_weighted"),
                (func.sum(OpportunityItem.target_station_sell_price * weight) / func.sum(weight)).label("target_now_price_weighted"),
                (func.sum(OpportunityItem.target_period_avg_price * weight) / func.sum(weight)).label("target_period_avg_price_weighted"),
                func.sum(OpportunityItem.target_now_profit * OpportunityItem.purchase_units).label("target_now_profit_weighted"),
                func.sum(OpportunityItem.target_period_profit * OpportunityItem.purchase_units).label("target_period_profit_weighted"),
                func.sum(OpportunityItem.capital_required).label("capital_required_total"),
                (func.sum(OpportunityItem.roi_now * weight) / func.sum(weight)).label("roi_now_weighted"),
                (func.sum(OpportunityItem.roi_period * weight) / func.sum(weight)).label("roi_period_weighted"),
                func.sum(OpportunityItem.item_volume_m3 * OpportunityItem.purchase_units).label("total_item_volume_m3"),
                func.sum(OpportunityItem.shipping_cost).label("shipping_cost_total"),
                case(
                    (func.count(func.distinct(OpportunityItem.demand_source)) == 1, func.min(OpportunityItem.demand_source)),
                    else_="Mixed",
                ).label("demand_source_summary"),
                func.sum(OpportunityItem.esi_demand_day).label("esi_demand_day_total"),
            )
            .where(
                OpportunityItem.target_location_id == target_location_id,
                OpportunityItem.source_location_id.in_(source_location_ids),
                OpportunityItem.period_days == period_days,
            )
            .group_by(OpportunityItem.source_location_id)
        )
        rows = session.execute(summary_query).all()
        return [
            OpportunitySourceSummary(
                target_location_id=target_location_id,
                source_location_id=source_location_id,
                source_security_status=float(source_security_status),
                period_days=period_days,
                purchase_units_total=float(purchase_units_total),
                source_units_available_total=float(source_units_available_total),
                target_demand_day_total=float(target_demand_day_total),
                target_supply_units_total=float(target_supply_units_total),
                target_dos_weighted=float(target_dos_weighted),
                in_transit_units=float(in_transit_units),
                assets_units=float(assets_units),
                active_sell_orders_units=float(active_sell_orders_units),
                source_avg_price_weighted=float(source_avg_price_weighted),
                target_now_price_weighted=float(target_now_price_weighted),
                target_period_avg_price_weighted=float(target_period_avg_price_weighted),
                target_now_profit_weighted=float(target_now_profit_weighted),
                target_period_profit_weighted=float(target_period_profit_weighted),
                capital_required_total=float(capital_required_total),
                roi_now_weighted=float(roi_now_weighted),
                roi_period_weighted=float(roi_period_weighted),
                total_item_volume_m3=float(total_item_volume_m3),
                shipping_cost_total=float(shipping_cost_total),
                demand_source_summary=str(demand_source_summary),
                esi_demand_day_total=float(esi_demand_day_total),
                computed_at=computed_at,
            )
            for (
                source_location_id,
                source_security_status,
                purchase_units_total,
                source_units_available_total,
                target_demand_day_total,
                target_supply_units_total,
                target_dos_weighted,
                in_transit_units,
                assets_units,
                active_sell_orders_units,
                source_avg_price_weighted,
                target_now_price_weighted,
                target_period_avg_price_weighted,
                target_now_profit_weighted,
                target_period_profit_weighted,
                capital_required_total,
                roi_now_weighted,
                roi_period_weighted,
                total_item_volume_m3,
                shipping_cost_total,
                demand_source_summary,
                esi_demand_day_total,
            ) in rows
        ]
