from datetime import UTC, datetime
from typing import Callable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.schemas.trade import (
    ItemOrderRow,
    OpportunityItemDetail,
    OpportunityItemRow,
    SourceSummary,
    TargetLocation,
)
from app.db.session import SessionLocal
from app.domain.enums import LocationType


class TradeRepository:
    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _ensure_utc(timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)

    def list_targets(self) -> list[TargetLocation]:
        from app.models.all_models import Location, Region, System

        session = self.session_factory()
        try:
            rows = session.execute(
                select(
                    Location.location_id,
                    Location.name,
                    Location.location_type,
                    Region.name,
                    System.name,
                )
                .join(Region, Region.id == Location.region_id)
                .join(System, System.id == Location.system_id)
                .where(Location.location_type.in_([LocationType.NPC_STATION.value, LocationType.STRUCTURE.value]))
                .order_by(Location.location_type, Location.name)
            ).all()
            return [
                TargetLocation(
                    location_id=row[0],
                    name=row[1],
                    location_type=row[2],
                    region_name=row[3],
                    system_name=row[4],
                )
                for row in rows
            ]
        finally:
            session.close()

    def list_sources(self, target_location_id: int, period_days: int) -> list[TargetLocation]:
        from app.models.all_models import Location, OpportunitySourceSummary, Region, System

        session = self.session_factory()
        try:
            resolved_target_location_id = self._resolve_location_id(session, target_location_id)
            if resolved_target_location_id is None:
                return []

            rows = session.execute(
                select(
                    Location.location_id,
                    Location.name,
                    Location.location_type,
                    Region.name,
                    System.name,
                )
                .join(OpportunitySourceSummary, OpportunitySourceSummary.source_location_id == Location.id)
                .join(Region, Region.id == Location.region_id)
                .join(System, System.id == Location.system_id)
                .where(
                    OpportunitySourceSummary.target_location_id == resolved_target_location_id,
                    OpportunitySourceSummary.period_days == period_days,
                    Location.location_type.in_([LocationType.NPC_STATION.value, LocationType.STRUCTURE.value]),
                )
                .distinct()
                .order_by(Location.name.asc())
            ).all()
            return [
                TargetLocation(
                    location_id=row[0],
                    name=row[1],
                    location_type=row[2],
                    region_name=row[3],
                    system_name=row[4],
                )
                for row in rows
            ]
        finally:
            session.close()

    def list_source_summaries(self, target_location_id: int, period_days: int) -> list[SourceSummary]:
        from app.models.all_models import Location, OpportunitySourceSummary

        session = self.session_factory()
        try:
            resolved_target_location_id = self._resolve_location_id(session, target_location_id)
            if resolved_target_location_id is None:
                return []

            rows = (
                session.execute(
                    select(OpportunitySourceSummary, Location.name)
                    .join(Location, Location.id == OpportunitySourceSummary.source_location_id)
                    .where(
                        OpportunitySourceSummary.target_location_id == resolved_target_location_id,
                        OpportunitySourceSummary.period_days == period_days,
                    )
                    .order_by(OpportunitySourceSummary.roi_now_weighted.desc(), Location.name.asc())
                )
                .all()
            )
            if rows:
                return [
                    SourceSummary(
                        source_location_id=summary.source_location_id,
                        source_market_name=location_name,
                        source_security_status=summary.source_security_status,
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
                    )
                    for summary, location_name in rows
                ]
        finally:
            session.close()

        return []

    def list_items(self, target_location_id: int, source_location_id: int, period_days: int) -> list[OpportunityItemRow]:
        from app.models.all_models import Item, OpportunityItem

        session = self.session_factory()
        try:
            resolved_target_location_id = self._resolve_location_id(session, target_location_id)
            resolved_source_location_id = self._resolve_location_id(session, source_location_id)
            if resolved_target_location_id is None or resolved_source_location_id is None:
                return []

            rows = (
                session.execute(
                    select(OpportunityItem, Item.name)
                    .join(Item, Item.id == OpportunityItem.type_id)
                    .where(
                        OpportunityItem.target_location_id == resolved_target_location_id,
                        OpportunityItem.source_location_id == resolved_source_location_id,
                        OpportunityItem.period_days == period_days,
                    )
                    .order_by(OpportunityItem.roi_now.desc(), Item.name.asc())
                )
                .all()
            )
            if rows:
                return [
                    OpportunityItemRow(
                        type_id=item.type_id,
                        item_name=item_name,
                        source_security_status=item.source_security_status,
                        purchase_units=item.purchase_units,
                        source_units_available=item.source_units_available,
                        target_demand_day=item.target_demand_day,
                        target_supply_units=item.target_supply_units,
                        target_dos=item.target_dos,
                        in_transit_units_item=item.in_transit_units,
                        assets_units_item=item.assets_units,
                        active_sell_orders_units_item=item.active_sell_orders_units,
                        source_station_sell_price=item.source_station_sell_price,
                        target_station_sell_price=item.target_station_sell_price,
                        target_period_avg_price=item.target_period_avg_price,
                        risk_pct=item.risk_pct,
                        warning_flag=item.warning_flag,
                        target_now_profit=item.target_now_profit,
                        target_period_profit=item.target_period_profit,
                        capital_required=item.capital_required,
                        roi_now=item.roi_now,
                        roi_period=item.roi_period,
                        item_volume_m3=item.item_volume_m3,
                        shipping_cost=item.shipping_cost,
                        demand_source=item.demand_source,
                        confidence_score=item.confidence_score,
                    )
                    for item, item_name in rows
                ]
        finally:
            session.close()

        return []

    def get_item_detail(
        self,
        target_location_id: int,
        source_location_id: int,
        type_id: int,
        period_days: int,
    ) -> OpportunityItemDetail:
        from app.models.all_models import Item, OpportunityItem

        session = self.session_factory()
        try:
            resolved_target_location_id = self._resolve_location_id(session, target_location_id)
            resolved_source_location_id = self._resolve_location_id(session, source_location_id)
            row = session.execute(
                select(OpportunityItem, Item.name)
                .join(Item, Item.id == OpportunityItem.type_id)
                .where(
                    OpportunityItem.target_location_id == resolved_target_location_id,
                    OpportunityItem.source_location_id == resolved_source_location_id,
                    Item.type_id == type_id,
                    OpportunityItem.period_days == period_days,
                )
            ).first()
            has_computed_metrics = row is not None
            if has_computed_metrics:
                assert row is not None
                item, item_name = row
                metrics = OpportunityItemRow(
                    type_id=type_id,
                    item_name=item_name,
                    source_security_status=item.source_security_status,
                    purchase_units=item.purchase_units,
                    source_units_available=item.source_units_available,
                    target_demand_day=item.target_demand_day,
                    target_supply_units=item.target_supply_units,
                    target_dos=item.target_dos,
                    in_transit_units_item=item.in_transit_units,
                    assets_units_item=item.assets_units,
                    active_sell_orders_units_item=item.active_sell_orders_units,
                    source_station_sell_price=item.source_station_sell_price,
                    target_station_sell_price=item.target_station_sell_price,
                    target_period_avg_price=item.target_period_avg_price,
                    risk_pct=item.risk_pct,
                    warning_flag=item.warning_flag,
                    target_now_profit=item.target_now_profit,
                    target_period_profit=item.target_period_profit,
                    capital_required=item.capital_required,
                    roi_now=item.roi_now,
                    roi_period=item.roi_period,
                    item_volume_m3=item.item_volume_m3,
                    shipping_cost=item.shipping_cost,
                    demand_source=item.demand_source,
                    confidence_score=item.confidence_score,
                )
            else:
                item = session.scalar(select(Item).where(Item.type_id == type_id))
                item_name = item.name if item is not None else f"Item {type_id}"
                metrics = OpportunityItemRow(
                    type_id=type_id,
                    item_name=item_name,
                    source_security_status=0.0,
                    purchase_units=0.0,
                    source_units_available=0.0,
                    target_demand_day=0.0,
                    target_supply_units=0.0,
                    target_dos=0.0,
                    in_transit_units_item=0.0,
                    assets_units_item=0.0,
                    active_sell_orders_units_item=0.0,
                    source_station_sell_price=0.0,
                    target_station_sell_price=0.0,
                    target_period_avg_price=0.0,
                    risk_pct=0.0,
                    warning_flag=False,
                    target_now_profit=0.0,
                    target_period_profit=0.0,
                    capital_required=0.0,
                    roi_now=0.0,
                    roi_period=0.0,
                    item_volume_m3=item.volume_m3 if item is not None else 0.0,
                    shipping_cost=0.0,
                    demand_source="unavailable",
                    confidence_score=0.0,
                )
        finally:
            session.close()

        target_market_sell_orders: list[ItemOrderRow]
        source_market_sell_orders: list[ItemOrderRow]
        source_market_buy_orders: list[ItemOrderRow]
        if has_computed_metrics:
            target_market_sell_orders = [
                ItemOrderRow(
                    price=metrics.target_station_sell_price,
                    volume=12,
                    order_value=metrics.target_station_sell_price * 12,
                    cumulative_volume=12,
                ),
                ItemOrderRow(
                    price=metrics.target_station_sell_price + 150_000.0,
                    volume=22,
                    order_value=(metrics.target_station_sell_price + 150_000.0) * 22,
                    cumulative_volume=34,
                ),
            ]
            source_market_sell_orders = [
                ItemOrderRow(price=metrics.source_station_sell_price, volume=10, order_value=metrics.source_station_sell_price * 10),
                ItemOrderRow(
                    price=metrics.source_station_sell_price + 100_000.0,
                    volume=30,
                    order_value=(metrics.source_station_sell_price + 100_000.0) * 30,
                ),
            ]
            source_market_buy_orders = [
                ItemOrderRow(
                    price=max(metrics.source_station_sell_price - 600_000.0, 0.0),
                    volume=18,
                    order_value=max(metrics.source_station_sell_price - 600_000.0, 0.0) * 18,
                ),
                ItemOrderRow(
                    price=max(metrics.source_station_sell_price - 750_000.0, 0.0),
                    volume=25,
                    order_value=max(metrics.source_station_sell_price - 750_000.0, 0.0) * 25,
                ),
            ]
        else:
            target_market_sell_orders = []
            source_market_sell_orders = []
            source_market_buy_orders = []

        return OpportunityItemDetail(
            type_id=type_id,
            item_name=metrics.item_name,
            target_market_sell_orders=target_market_sell_orders,
            source_market_sell_orders=source_market_sell_orders,
            source_market_buy_orders=source_market_buy_orders,
            metrics=metrics,
        )

    @staticmethod
    def _resolve_location_id(session: Session, location_reference: int) -> int | None:
        from app.models.all_models import Location

        return session.scalar(
            select(Location.id).where(
                or_(
                    Location.id == location_reference,
                    Location.location_id == location_reference,
                )
            )
        )

    def get_last_refresh(self) -> datetime:
        from app.models.all_models import OpportunityItem, OpportunitySourceSummary

        session = self.session_factory()
        try:
            summary_times = session.scalars(select(OpportunitySourceSummary.computed_at)).all()
            item_times = session.scalars(select(OpportunityItem.computed_at)).all()
            timestamps = [self._ensure_utc(timestamp) for timestamp in [*summary_times, *item_times]]
            if timestamps:
                return max(timestamps)
        finally:
            session.close()
        return datetime.now(UTC)
