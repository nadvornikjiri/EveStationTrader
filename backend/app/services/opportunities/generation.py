from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from time import perf_counter
from typing import Callable

from sqlalchemy import Float, bindparam, case, cast, delete, func, insert, select
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
    CharacterAsset,
    CharacterOrder,
    EsiHistoryDaily,
    EsiMarketOrder,
    EsiCharacter,
    InTransitAsset,
    Item,
    Location,
    MarketDemandResolved,
    MarketPricePeriod,
    OpportunityItem,
    OpportunitySourceSummary,
    System,
)


@dataclass
class OpportunityGenerationResult:
    item_count: int
    summary_count: int


def _chunked_in(ids: list[int], chunk_size: int = 5000) -> list[list[int]]:
    return [ids[index : index + chunk_size] for index in range(0, len(ids), chunk_size)]


def _insert_rows_in_batches(
    session: Session,
    *,
    model,
    rows: list[dict[str, object]],
    batch_size: int = 5000,
) -> None:
    for index in range(0, len(rows), batch_size):
        session.execute(insert(model), rows[index : index + batch_size])


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
        cancellation_check: Callable[[], None] | None = None,
        stage_callback: Callable[[str, float, dict[str, object]], None] | None = None,
    ) -> OpportunityGenerationResult:
        def record_stage(stage_key: str, started_at: float, **metrics: object) -> None:
            if stage_callback is not None:
                stage_callback(stage_key, started_at, {key: value for key, value in metrics.items() if value is not None})

        if not source_location_ids or not type_ids:
            return OpportunityGenerationResult(item_count=0, summary_count=0)

        normalized_source_ids = list(dict.fromkeys(source_location_ids))
        normalized_type_ids = list(dict.fromkeys(type_ids))
        computed_at = datetime.now(UTC)
        normalized_period_days = max(period_days, 1)
        target_location = session.get(Location, target_location_id)
        if target_location is None:
            return OpportunityGenerationResult(item_count=0, summary_count=0)

        delete_started_at = perf_counter()
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
        record_stage(
            "delete_existing_rows",
            delete_started_at,
            replace_entire_target_scope=replace_entire_target_scope,
            source_count=len(normalized_source_ids),
            type_count=len(normalized_type_ids),
        )

        generated_count = 0
        all_location_ids = [target_location_id] + normalized_source_ids
        type_loop_started_at = perf_counter()
        asset_totals_by_type = {
            type_id: float(quantity)
            for type_id, quantity in session.execute(
                select(CharacterAsset.type_id, func.sum(CharacterAsset.quantity))
                .join(EsiCharacter, EsiCharacter.id == CharacterAsset.character_id)
                .where(
                    EsiCharacter.sync_enabled.is_(True),
                    CharacterAsset.type_id.in_(normalized_type_ids),
                )
                .group_by(CharacterAsset.type_id)
            ).all()
            if quantity is not None
        }
        target_order_totals_by_type = {
            type_id: float(quantity)
            for type_id, quantity in session.execute(
                select(CharacterOrder.type_id, func.sum(CharacterOrder.volume_remain))
                .join(EsiCharacter, EsiCharacter.id == CharacterOrder.character_id)
                .where(
                    EsiCharacter.sync_enabled.is_(True),
                    CharacterOrder.type_id.in_(normalized_type_ids),
                    CharacterOrder.is_buy_order.is_(False),
                    CharacterOrder.resolved_location_id == target_location_id,
                )
                .group_by(CharacterOrder.type_id)
            ).all()
            if quantity is not None
        }
        in_transit_totals_by_pair = {
            (source_location_id, type_id): float(quantity)
            for source_location_id, type_id, quantity in session.execute(
                select(InTransitAsset.source_location_id, InTransitAsset.type_id, func.sum(InTransitAsset.quantity))
                .where(
                    InTransitAsset.target_location_id == target_location_id,
                    InTransitAsset.source_location_id.in_(normalized_source_ids),
                    InTransitAsset.type_id.in_(normalized_type_ids),
                )
                .group_by(InTransitAsset.source_location_id, InTransitAsset.type_id)
            ).all()
            if quantity is not None
        }
        type_id_chunks = _chunked_in(normalized_type_ids)
        items_by_id: dict[int, Item] = {}
        for type_id_chunk in type_id_chunks:
            items_by_id.update(
                {
                    item.id: item
                    for item in session.scalars(select(Item).where(Item.id.in_(type_id_chunk))).all()
                }
            )

        demands_by_type: dict[int, MarketDemandResolved] = {}
        for type_id_chunk in type_id_chunks:
            demands_by_type.update(
                {
                    demand.type_id: demand
                    for demand in session.scalars(
                        select(MarketDemandResolved).where(
                            MarketDemandResolved.location_id == target_location_id,
                            MarketDemandResolved.type_id.in_(type_id_chunk),
                            MarketDemandResolved.period_days == normalized_period_days,
                        )
                    ).all()
                }
            )

        cutoff: date = computed_at.date() - timedelta(days=normalized_period_days)
        esi_history_avg_by_type: dict[int, float] = {}
        for type_id_chunk in type_id_chunks:
            esi_history_avg_by_type.update(
                {
                    type_id: float(avg_volume)
                    for type_id, avg_volume in session.execute(
                        select(
                            EsiHistoryDaily.type_id,
                            (
                                cast(func.sum(EsiHistoryDaily.volume), Float)
                                / normalized_period_days
                            ).label("avg_volume"),
                        )
                        .where(
                            EsiHistoryDaily.region_id == target_location.region_id,
                            EsiHistoryDaily.type_id.in_(type_id_chunk),
                            EsiHistoryDaily.date >= cutoff,
                        )
                        .group_by(EsiHistoryDaily.type_id)
                    ).all()
                    if avg_volume is not None
                }
            )

        target_prices_by_type: dict[int, MarketPricePeriod] = {}
        for type_id_chunk in type_id_chunks:
            target_prices_by_type.update(
                {
                    price_period.type_id: price_period
                    for price_period in session.scalars(
                        select(MarketPricePeriod).where(
                            MarketPricePeriod.location_id == target_location_id,
                            MarketPricePeriod.type_id.in_(type_id_chunk),
                            MarketPricePeriod.period_days == normalized_period_days,
                        )
                    ).all()
                }
            )

        sell_volumes_by_loc_type: dict[tuple[int, int], float] = {}
        for type_id_chunk in type_id_chunks:
            sell_volumes_by_loc_type.update(
                {
                    (location_id, type_id): float(volume)
                    for location_id, type_id, volume in session.execute(
                        select(
                            EsiMarketOrder.location_id,
                            EsiMarketOrder.type_id,
                            func.sum(EsiMarketOrder.volume_remain),
                        )
                        .where(
                            EsiMarketOrder.location_id.in_(all_location_ids),
                            EsiMarketOrder.type_id.in_(type_id_chunk),
                            EsiMarketOrder.is_buy_order.is_(False),
                        )
                        .group_by(EsiMarketOrder.location_id, EsiMarketOrder.type_id)
                    ).all()
                    if volume is not None
                }
            )

        target_min_price_by_type: dict[int, float] = {}
        for type_id_chunk in type_id_chunks:
            target_min_price_by_type.update(
                {
                    type_id: float(min_price)
                    for type_id, min_price in session.execute(
                        select(EsiMarketOrder.type_id, func.min(EsiMarketOrder.price))
                        .where(
                            EsiMarketOrder.location_id == target_location_id,
                            EsiMarketOrder.type_id.in_(type_id_chunk),
                            EsiMarketOrder.is_buy_order.is_(False),
                        )
                        .group_by(EsiMarketOrder.type_id)
                    ).all()
                    if min_price is not None
                }
            )

        source_effective_price_by_loc_type: dict[tuple[int, int], tuple[float, float]] = {}
        for type_id_chunk in type_id_chunks:
            demand_cte = (
                select(
                    MarketDemandResolved.type_id.label("type_id"),
                    cast(MarketDemandResolved.buy_from_sell_yesterday, Float).label("buy_from_sell_yesterday"),
                )
                .where(
                    MarketDemandResolved.location_id == target_location_id,
                    MarketDemandResolved.type_id.in_(bindparam("type_ids", expanding=True)),
                    MarketDemandResolved.period_days == normalized_period_days,
                )
                .cte("demand_cte")
            )
            partition_by_location_type = (EsiMarketOrder.location_id, EsiMarketOrder.type_id)
            source_orders_cte = (
                select(
                    EsiMarketOrder.location_id.label("location_id"),
                    EsiMarketOrder.type_id.label("type_id"),
                    cast(EsiMarketOrder.price, Float).label("price"),
                    cast(EsiMarketOrder.volume_remain, Float).label("volume_remain"),
                    cast(
                        func.sum(EsiMarketOrder.volume_remain).over(partition_by=partition_by_location_type),
                        Float,
                    ).label("total_vol"),
                    cast(
                        func.sum(EsiMarketOrder.volume_remain).over(
                            partition_by=partition_by_location_type,
                            order_by=(
                                EsiMarketOrder.price.asc(),
                                EsiMarketOrder.issued.asc(),
                                EsiMarketOrder.order_id.asc(),
                            ),
                        ),
                        Float,
                    ).label("running_vol"),
                )
                .where(
                    EsiMarketOrder.location_id.in_(normalized_source_ids),
                    EsiMarketOrder.type_id.in_(bindparam("type_ids", expanding=True)),
                    EsiMarketOrder.is_buy_order.is_(False),
                )
                .cte("source_orders_cte")
            )
            purchase_units_expr = func.least(
                source_orders_cte.c.total_vol,
                demand_cte.c.buy_from_sell_yesterday,
            )
            volume_before_expr = source_orders_cte.c.running_vol - source_orders_cte.c.volume_remain
            consumed_volume_expr = func.least(
                source_orders_cte.c.volume_remain,
                func.greatest(purchase_units_expr - volume_before_expr, 0.0),
            )
            with_purchase_units_cte = (
                select(
                    source_orders_cte.c.location_id.label("location_id"),
                    source_orders_cte.c.type_id.label("type_id"),
                    source_orders_cte.c.price.label("price"),
                    purchase_units_expr.label("purchase_units"),
                    consumed_volume_expr.label("consumed_vol"),
                )
                .join(demand_cte, demand_cte.c.type_id == source_orders_cte.c.type_id)
                .cte("with_purchase_units_cte")
            )
            source_effective_price_by_loc_type.update(
                {
                    (location_id, type_id): (float(effective_price), float(purchase_units))
                    for location_id, type_id, effective_price, purchase_units in session.execute(
                        select(
                            with_purchase_units_cte.c.location_id,
                            with_purchase_units_cte.c.type_id,
                            (
                                func.sum(
                                    with_purchase_units_cte.c.price * with_purchase_units_cte.c.consumed_vol
                                )
                                / func.max(with_purchase_units_cte.c.purchase_units)
                            ).label("effective_price"),
                            func.max(with_purchase_units_cte.c.purchase_units).label("purchase_units"),
                        )
                        .where(
                            with_purchase_units_cte.c.consumed_vol > 0,
                            with_purchase_units_cte.c.purchase_units > 0,
                        )
                        .group_by(
                            with_purchase_units_cte.c.location_id,
                            with_purchase_units_cte.c.type_id,
                        ),
                        {"type_ids": type_id_chunk},
                    ).all()
                    if effective_price is not None and purchase_units is not None
                }
            )

        source_locations = {
            row.id: row
            for row in session.scalars(select(Location).where(Location.id.in_(normalized_source_ids))).all()
        }
        source_system_ids = list(dict.fromkeys(location.system_id for location in source_locations.values()))
        source_systems = {
            row.id: row
            for row in session.scalars(select(System).where(System.id.in_(source_system_ids))).all()
        }

        actual_source_ids_by_type: dict[int, list[int]] = {}
        for location_id, type_id in source_effective_price_by_loc_type:
            actual_source_ids_by_type.setdefault(type_id, []).append(location_id)
        for source_ids in actual_source_ids_by_type.values():
            source_ids.sort()

        item_rows: list[dict[str, object]] = []
        for type_id in normalized_type_ids:
            if cancellation_check is not None:
                cancellation_check()
            item = items_by_id.get(type_id)
            if item is None:
                continue
            demand = demands_by_type.get(type_id)
            if demand is None:
                continue
            if demand.buy_from_sell_yesterday <= 0:
                continue
            esi_demand_day = esi_history_avg_by_type.get(type_id, 0.0)
            target_price = target_prices_by_type.get(type_id)
            target_now_price = target_min_price_by_type.get(type_id)
            if target_now_price is None:
                continue
            actual_source_ids = actual_source_ids_by_type.get(type_id, [])
            if not actual_source_ids:
                continue

            for source_location_id in actual_source_ids:
                source_now_price, _ = source_effective_price_by_loc_type[(source_location_id, type_id)]
                source_location = source_locations.get(source_location_id)
                if source_location is None:
                    continue
                source_system = source_systems.get(source_location.system_id)
                source_security_status = source_system.security_status if source_system is not None else 0.0
                source_units_available = sell_volumes_by_loc_type.get((source_location_id, type_id), 0.0)
                target_supply_units = sell_volumes_by_loc_type.get((target_location_id, type_id), 0.0)
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
                in_transit_units = in_transit_totals_by_pair.get((source_location_id, type_id), 0.0)
                assets_units = asset_totals_by_type.get(type_id, 0.0)
                active_sell_orders_units = target_order_totals_by_type.get(type_id, 0.0)

                item_rows.append(
                    {
                        "target_location_id": target_location_id,
                        "source_location_id": source_location_id,
                        "type_id": type_id,
                        "period_days": period_days,
                        "purchase_units": purchase_units,
                        "source_units_available": source_units_available,
                        "target_demand_day": target_demand_day,
                        "target_supply_units": target_supply_units,
                        "target_dos": target_dos,
                        "in_transit_units": in_transit_units,
                        "assets_units": assets_units,
                        "active_sell_orders_units": active_sell_orders_units,
                        "source_station_sell_price": source_now_price,
                        "target_station_sell_price": float(target_now_price),
                        "target_period_avg_price": target_period_avg_price,
                        "target_now_profit": target_now_profit,
                        "target_period_profit": target_period_profit,
                        "capital_required": capital_required,
                        "roi_now": roi_now,
                        "roi_period": roi_period,
                        "source_security_status": source_security_status,
                        "item_volume_m3": item.volume_m3,
                        "shipping_cost": shipping_cost,
                        "demand_source": demand.demand_source,
                        "esi_demand_day": esi_demand_day,
                        "computed_at": computed_at,
                    }
                )
                generated_count += 1

        if item_rows:
            _insert_rows_in_batches(session, model=OpportunityItem, rows=item_rows)

        record_stage(
            "generate_item_rows",
            type_loop_started_at,
            type_count=len(normalized_type_ids),
            generated_count=generated_count,
        )

        summary_started_at = perf_counter()
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
        record_stage(
            "flush_summaries_commit",
            summary_started_at,
            generated_count=generated_count,
            summary_count=len(summary_rows),
        )
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
