from datetime import UTC, datetime
from typing import Any, Callable, cast

from sqlalchemy import case, func, or_, select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.orm import Session

from app.api.schemas.trade import (
    ItemOrderRow,
    OpportunityItemDetail,
    OpportunityItemRow,
    SourceSummary,
    TargetLocation,
    TargetOpportunityItemRow,
)
from app.db.session import SessionLocal
from app.domain.enums import LocationType
from app.services.settings_service import SettingsService


class TradeRepository:
    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _ensure_utc(timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)

    @staticmethod
    def _min_security_threshold(min_security: str) -> float:
        if min_security == "highsec":
            return 0.5
        if min_security == "lowsec":
            return 0.0
        return -10.0

    @staticmethod
    def _item_filter_conditions(
        *,
        item_name_column: Any,
        location_type_column: Any,
        source_security_column: Any,
        target_now_profit_column: Any,
        roi_now_column: Any,
        target_demand_day_column: Any,
        target_dos_column: Any,
        demand_source_column: Any,
        item_search: str,
        min_profit: float,
        min_roi_now_pct: float,
        min_demand_day: float,
        max_dos: float | None,
        source_type: str,
        min_security: str,
        demand_source: str,
    ) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        search_value = item_search.strip()
        if search_value:
            conditions.append(item_name_column.ilike(f"%{search_value}%"))
        if min_profit > 0:
            conditions.append(target_now_profit_column > min_profit)
        if min_roi_now_pct > 0:
            conditions.append(roi_now_column > (min_roi_now_pct / 100.0))
        if min_demand_day > 0:
            conditions.append(target_demand_day_column >= min_demand_day)
        if max_dos is not None:
            conditions.append(target_dos_column <= max_dos)
        conditions.append(source_security_column >= TradeRepository._min_security_threshold(min_security))
        if source_type == "npc":
            conditions.append(location_type_column == LocationType.NPC_STATION.value)
        elif source_type == "structure":
            conditions.append(location_type_column == LocationType.STRUCTURE.value)
        if demand_source != "all":
            conditions.append(demand_source_column == demand_source)
        return conditions

    def list_targets(self) -> list[TargetLocation]:
        from app.models.all_models import Location, Region, Station, System

        session = self.session_factory()
        try:
            configured_ids = SettingsService(session_factory=self.session_factory).get_settings_for_session(
                session
            ).target_market_location_ids
            if not configured_ids:
                return []
            resolved_name = self._display_location_name(Location.name, Station.name)
            rows = session.execute(
                select(
                    Location.id,
                    Location.location_id,
                    resolved_name,
                    Location.location_type,
                    Region.name,
                    System.name,
                )
                .outerjoin(Station, Station.station_id == Location.location_id)
                .join(Region, Region.id == Location.region_id)
                .join(System, System.id == Location.system_id)
                .where(
                    Location.location_id.in_(configured_ids),
                    Location.location_type.in_([LocationType.NPC_STATION.value, LocationType.STRUCTURE.value]),
                )
            ).all()
            rows_by_external_id = {row[1]: row for row in rows}
            return [
                TargetLocation(
                    location_id=row[1],
                    name=row[2],
                    location_type=row[3],
                    region_name=row[4],
                    system_name=row[5],
                )
                for configured_id in configured_ids
                if (row := rows_by_external_id.get(configured_id)) is not None
            ]
        finally:
            session.close()

    def list_target_options(self) -> list[TargetLocation]:
        from app.models.all_models import Location, Region, Station, System

        session = self.session_factory()
        try:
            resolved_name = self._display_location_name(Location.name, Station.name)
            rows = session.execute(
                select(
                    Location.location_id,
                    resolved_name,
                    Location.location_type,
                    Region.name,
                    System.name,
                )
                .outerjoin(Station, Station.station_id == Location.location_id)
                .join(Region, Region.id == Location.region_id)
                .join(System, System.id == Location.system_id)
                .where(Location.location_type.in_([LocationType.NPC_STATION.value, LocationType.STRUCTURE.value]))
                .order_by(System.name.asc(), resolved_name.asc())
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
        from app.models.all_models import Location, OpportunitySourceSummary, Region, Station, System
        from app.services.sync.service import SyncService

        session = self.session_factory()
        try:
            resolved_name = self._display_location_name(Location.name, Station.name)
            resolved_target_location_id = self._resolve_location_id(session, target_location_id)
            if resolved_target_location_id is None:
                return []
            has_rows = session.scalar(
                select(OpportunitySourceSummary.id).where(
                    OpportunitySourceSummary.target_location_id == resolved_target_location_id,
                    OpportunitySourceSummary.period_days == period_days,
                )
            )
            if has_rows is None:
                SyncService(session_factory=lambda: session).prepare_trade_period(
                    session,
                    target_location_id=resolved_target_location_id,
                    period_days=period_days,
                )

            rows = session.execute(
                select(
                    Location.location_id,
                    resolved_name,
                    Location.location_type,
                    Region.name,
                    System.name,
                )
                .join(OpportunitySourceSummary, OpportunitySourceSummary.source_location_id == Location.id)
                .outerjoin(Station, Station.station_id == Location.location_id)
                .join(Region, Region.id == Location.region_id)
                .join(System, System.id == Location.system_id)
                .where(
                    OpportunitySourceSummary.target_location_id == resolved_target_location_id,
                    OpportunitySourceSummary.period_days == period_days,
                    Location.location_type.in_([LocationType.NPC_STATION.value, LocationType.STRUCTURE.value]),
                )
                .distinct()
                .order_by(resolved_name.asc())
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

    def list_source_summaries(
        self,
        target_location_id: int,
        period_days: int,
        *,
        item_search: str = "",
        min_profit: float = 0.0,
        min_roi_now_pct: float = 0.0,
        min_demand_day: float = 0.0,
        max_dos: float | None = None,
        source_type: str = "all",
        min_security: str = "all",
        demand_source: str = "all",
    ) -> list[SourceSummary]:
        from app.models.all_models import Item, Location, OpportunityItem, OpportunitySourceSummary, Station
        from app.services.sync.service import SyncService

        session = self.session_factory()
        try:
            resolved_name = self._display_location_name(Location.name, Station.name)
            resolved_target_location_id = self._resolve_location_id(session, target_location_id)
            if resolved_target_location_id is None:
                return []
            has_rows = session.scalar(
                select(OpportunitySourceSummary.id).where(
                    OpportunitySourceSummary.target_location_id == resolved_target_location_id,
                    OpportunitySourceSummary.period_days == period_days,
                )
            )
            if has_rows is None:
                SyncService(session_factory=lambda: session).prepare_trade_period(
                    session,
                    target_location_id=resolved_target_location_id,
                    period_days=period_days,
                )

            weight = case((OpportunityItem.purchase_units > 1, OpportunityItem.purchase_units), else_=1.0)
            total_weight = func.sum(weight)
            demand_source_summary = case(
                (func.count(func.distinct(OpportunityItem.demand_source)) == 1, func.min(OpportunityItem.demand_source)),
                else_="Mixed",
            )
            conditions = self._item_filter_conditions(
                item_name_column=Item.name,
                location_type_column=Location.location_type,
                source_security_column=OpportunityItem.source_security_status,
                target_now_profit_column=OpportunityItem.target_now_profit,
                roi_now_column=OpportunityItem.roi_now,
                target_demand_day_column=OpportunityItem.target_demand_day,
                target_dos_column=OpportunityItem.target_dos,
                demand_source_column=OpportunityItem.demand_source,
                item_search=item_search,
                min_profit=min_profit,
                min_roi_now_pct=min_roi_now_pct,
                min_demand_day=min_demand_day,
                max_dos=max_dos,
                source_type=source_type,
                min_security=min_security,
                demand_source=demand_source,
            )
            rows = session.execute(
                select(
                    OpportunityItem.source_location_id,
                    resolved_name,
                    (func.sum(OpportunityItem.source_security_status * weight) / total_weight),
                    func.sum(OpportunityItem.purchase_units),
                    func.sum(OpportunityItem.source_units_available),
                    func.sum(OpportunityItem.target_demand_day),
                    func.sum(OpportunityItem.target_supply_units),
                    (func.sum(OpportunityItem.target_dos * weight) / total_weight),
                    func.sum(OpportunityItem.in_transit_units),
                    func.sum(OpportunityItem.assets_units),
                    func.sum(OpportunityItem.active_sell_orders_units),
                    (func.sum(OpportunityItem.source_station_sell_price * weight) / total_weight),
                    (func.sum(OpportunityItem.target_station_sell_price * weight) / total_weight),
                    (func.sum(OpportunityItem.target_period_avg_price * weight) / total_weight),
                    func.sum(OpportunityItem.target_now_profit * OpportunityItem.purchase_units),
                    func.sum(OpportunityItem.target_period_profit * OpportunityItem.purchase_units),
                    func.sum(OpportunityItem.capital_required),
                    (func.sum(OpportunityItem.roi_now * weight) / total_weight),
                    (func.sum(OpportunityItem.roi_period * weight) / total_weight),
                    func.sum(OpportunityItem.item_volume_m3 * OpportunityItem.purchase_units),
                    func.sum(OpportunityItem.shipping_cost),
                    demand_source_summary,
                )
                .join(Location, Location.id == OpportunityItem.source_location_id)
                .outerjoin(Station, Station.station_id == Location.location_id)
                .join(Item, Item.id == OpportunityItem.type_id)
                .where(
                    OpportunityItem.target_location_id == resolved_target_location_id,
                    OpportunityItem.period_days == period_days,
                    *conditions,
                )
                .group_by(OpportunityItem.source_location_id, resolved_name)
                .order_by(func.sum(OpportunityItem.target_now_profit * OpportunityItem.purchase_units).desc(), resolved_name.asc())
            ).all()
            if rows:
                return [
                    SourceSummary(
                        source_location_id=source_location_id,
                        source_market_name=location_name,
                        source_security_status=source_security_status,
                        purchase_units_total=purchase_units_total,
                        source_units_available_total=source_units_available_total,
                        target_demand_day_total=target_demand_day_total,
                        target_supply_units_total=target_supply_units_total,
                        target_dos_weighted=target_dos_weighted,
                        in_transit_units=in_transit_units,
                        assets_units=assets_units,
                        active_sell_orders_units=active_sell_orders_units,
                        source_avg_price_weighted=source_avg_price_weighted,
                        target_now_price_weighted=target_now_price_weighted,
                        target_period_avg_price_weighted=target_period_avg_price_weighted,
                        target_now_profit_weighted=target_now_profit_weighted,
                        target_period_profit_weighted=target_period_profit_weighted,
                        capital_required_total=capital_required_total,
                        roi_now_weighted=roi_now_weighted,
                        roi_period_weighted=roi_period_weighted,
                        total_item_volume_m3=total_item_volume_m3,
                        shipping_cost_total=shipping_cost_total,
                        demand_source_summary=group_demand_source_summary,
                    )
                    for (
                        source_location_id,
                        location_name,
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
                        group_demand_source_summary,
                    ) in rows
                ]
            return []
        finally:
            session.close()

    def list_items(
        self,
        target_location_id: int,
        source_location_id: int,
        period_days: int,
        *,
        item_search: str = "",
        min_profit: float = 0.0,
        min_roi_now_pct: float = 0.0,
        min_demand_day: float = 0.0,
        max_dos: float | None = None,
        source_type: str = "all",
        min_security: str = "all",
        demand_source: str = "all",
    ) -> list[OpportunityItemRow]:
        from app.models.all_models import Item, Location, OpportunityItem
        from app.services.sync.service import SyncService

        session = self.session_factory()
        try:
            resolved_target_location_id = self._resolve_location_id(session, target_location_id)
            resolved_source_location_id = self._resolve_location_id(session, source_location_id)
            if resolved_target_location_id is None or resolved_source_location_id is None:
                return []
            has_rows = session.scalar(
                select(OpportunityItem.id).where(
                    OpportunityItem.target_location_id == resolved_target_location_id,
                    OpportunityItem.source_location_id == resolved_source_location_id,
                    OpportunityItem.period_days == period_days,
                )
            )
            if has_rows is None:
                SyncService(session_factory=lambda: session).prepare_trade_period(
                    session,
                    target_location_id=resolved_target_location_id,
                    source_location_id=resolved_source_location_id,
                    period_days=period_days,
                )

            conditions = self._item_filter_conditions(
                item_name_column=Item.name,
                location_type_column=Location.location_type,
                source_security_column=OpportunityItem.source_security_status,
                target_now_profit_column=OpportunityItem.target_now_profit,
                roi_now_column=OpportunityItem.roi_now,
                target_demand_day_column=OpportunityItem.target_demand_day,
                target_dos_column=OpportunityItem.target_dos,
                demand_source_column=OpportunityItem.demand_source,
                item_search=item_search,
                min_profit=min_profit,
                min_roi_now_pct=min_roi_now_pct,
                min_demand_day=min_demand_day,
                max_dos=max_dos,
                source_type=source_type,
                min_security=min_security,
                demand_source=demand_source,
            )
            rows = (
                session.execute(
                    select(OpportunityItem, Item.name)
                    .join(Item, Item.id == OpportunityItem.type_id)
                    .join(Location, Location.id == OpportunityItem.source_location_id)
                    .where(
                        OpportunityItem.target_location_id == resolved_target_location_id,
                        OpportunityItem.source_location_id == resolved_source_location_id,
                        OpportunityItem.period_days == period_days,
                        *conditions,
                    )
                    .order_by(OpportunityItem.target_now_profit.desc(), Item.name.asc())
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
                        target_now_profit=item.target_now_profit,
                        target_period_profit=item.target_period_profit,
                        capital_required=item.capital_required,
                        roi_now=item.roi_now,
                        roi_period=item.roi_period,
                        item_volume_m3=item.item_volume_m3,
                        shipping_cost=item.shipping_cost,
                        demand_source=item.demand_source,
                    )
                    for item, item_name in rows
                ]
            return []
        finally:
            session.close()

    def list_target_items(self, target_location_id: int, period_days: int) -> list[TargetOpportunityItemRow]:
        from app.models.all_models import Item, OpportunityItem
        from app.services.sync.service import SyncService

        session = self.session_factory()
        try:
            resolved_target_location_id = self._resolve_location_id(session, target_location_id)
            if resolved_target_location_id is None:
                return []
            has_rows = session.scalar(
                select(OpportunityItem.id).where(
                    OpportunityItem.target_location_id == resolved_target_location_id,
                    OpportunityItem.period_days == period_days,
                )
            )
            if has_rows is None:
                SyncService(session_factory=lambda: session).prepare_trade_period(
                    session,
                    target_location_id=resolved_target_location_id,
                    period_days=period_days,
                )

            rows = (
                session.execute(
                    select(OpportunityItem, Item.name)
                    .join(Item, Item.id == OpportunityItem.type_id)
                    .where(
                        OpportunityItem.target_location_id == resolved_target_location_id,
                        OpportunityItem.period_days == period_days,
                    )
                    .order_by(
                        OpportunityItem.source_location_id.asc(),
                        OpportunityItem.target_now_profit.desc(),
                        Item.name.asc(),
                    )
                )
                .all()
            )
            return [
                TargetOpportunityItemRow(
                    source_location_id=item.source_location_id,
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
                    target_now_profit=item.target_now_profit,
                    target_period_profit=item.target_period_profit,
                    capital_required=item.capital_required,
                    roi_now=item.roi_now,
                    roi_period=item.roi_period,
                    item_volume_m3=item.item_volume_m3,
                    shipping_cost=item.shipping_cost,
                    demand_source=item.demand_source,
                )
                for item, item_name in rows
            ]
        finally:
            session.close()

    def get_item_detail(
        self,
        target_location_id: int,
        source_location_id: int,
        type_id: int,
        period_days: int,
    ) -> OpportunityItemDetail:
        from app.models.all_models import Item, OpportunityItem
        from app.services.sync.service import SyncService

        session = self.session_factory()
        try:
            resolved_target_location_id = self._resolve_location_id(session, target_location_id)
            resolved_source_location_id = self._resolve_location_id(session, source_location_id)
            if resolved_target_location_id is None or resolved_source_location_id is None:
                raise LookupError(
                    "Opportunity item detail was requested before derived opportunity rows were available."
                )
            resolved_type_id = session.scalar(
                select(Item.id).where(Item.type_id == type_id)
            )
            if resolved_type_id is None:
                raise LookupError(
                    "Opportunity item detail was requested before derived opportunity rows were available."
                )
            has_row = session.scalar(
                select(OpportunityItem.id)
                .join(Item, Item.id == OpportunityItem.type_id)
                .where(
                    OpportunityItem.target_location_id == resolved_target_location_id,
                    OpportunityItem.source_location_id == resolved_source_location_id,
                    OpportunityItem.period_days == period_days,
                    Item.type_id == type_id,
                )
            )
            if has_row is None:
                SyncService(session_factory=lambda: session).prepare_trade_period(
                    session,
                    target_location_id=resolved_target_location_id,
                    source_location_id=resolved_source_location_id,
                    type_id=type_id,
                    period_days=period_days,
                )
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
            if row is None:
                raise LookupError(
                    "Opportunity item detail was requested before derived opportunity rows were available."
                )

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
                target_now_profit=item.target_now_profit,
                target_period_profit=item.target_period_profit,
                capital_required=item.capital_required,
                roi_now=item.roi_now,
                roi_period=item.roi_period,
                item_volume_m3=item.item_volume_m3,
                shipping_cost=item.shipping_cost,
                demand_source=item.demand_source,
            )

            target_sell_orders = self._query_orders(
                session, resolved_target_location_id, resolved_type_id, is_buy=False
            )
            source_sell_orders = self._query_orders(
                session, resolved_source_location_id, resolved_type_id, is_buy=False
            )
            source_buy_orders = self._query_orders(
                session, resolved_source_location_id, resolved_type_id, is_buy=True
            )
        finally:
            session.close()

        return OpportunityItemDetail(
            type_id=type_id,
            item_name=metrics.item_name,
            target_market_sell_orders=target_sell_orders,
            source_market_sell_orders=source_sell_orders,
            source_market_buy_orders=source_buy_orders,
            metrics=metrics,
        )

    @staticmethod
    def _query_orders(
        session: Session, location_id: int, type_id: int, *, is_buy: bool
    ) -> list[ItemOrderRow]:
        from app.models.all_models import EsiMarketOrder

        order_by = EsiMarketOrder.price.asc() if not is_buy else EsiMarketOrder.price.desc()
        rows = session.execute(
            select(
                EsiMarketOrder.price,
                EsiMarketOrder.volume_remain,
            )
            .where(
                EsiMarketOrder.location_id == location_id,
                EsiMarketOrder.type_id == type_id,
                EsiMarketOrder.is_buy_order.is_(is_buy),
            )
            .order_by(order_by)
        ).all()

        result: list[ItemOrderRow] = []
        cumulative = 0
        for price, volume in rows:
            cumulative += volume
            result.append(
                ItemOrderRow(
                    price=price,
                    volume=volume,
                    order_value=price * volume,
                    cumulative_volume=cumulative if not is_buy else None,
                )
            )
        return result

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

    @staticmethod
    def _display_location_name(
        location_name: Any,
        station_name: Any,
    ) -> ColumnElement[str]:
        return cast(
            ColumnElement[str],
            case(
            (
                station_name.is_not(None) & (~station_name.like("Station %")),
                station_name,
            ),
            (
                location_name.is_not(None) & (~location_name.like("Station %")),
                location_name,
            ),
            else_=func.coalesce(station_name, location_name),
            ).label("display_location_name"),
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

    def refresh_opportunities(
        self,
        target_location_id: int,
        period_days: int,
        *,
        source_location_id: int | None = None,
        type_id: int | None = None,
    ) -> None:
        from app.services.sync.service import SyncService
        from app.models.all_models import MarketDemandResolved, MarketPricePeriod

        session = self.session_factory()
        try:
            resolved_target_location_id = self._resolve_location_id(session, target_location_id)
            if resolved_target_location_id is None:
                raise LookupError(f"Target location {target_location_id} was not found.")

            resolved_source_location_id: int | None = None
            if source_location_id is not None:
                resolved_source_location_id = self._resolve_location_id(session, source_location_id)
                if resolved_source_location_id is None:
                    raise LookupError(f"Source location {source_location_id} was not found.")

            has_target_price_period = session.scalar(
                select(MarketPricePeriod.id).where(
                    MarketPricePeriod.location_id == resolved_target_location_id,
                    MarketPricePeriod.period_days == period_days,
                )
            )
            has_target_demand = session.scalar(
                select(MarketDemandResolved.id).where(
                    MarketDemandResolved.location_id == resolved_target_location_id,
                    MarketDemandResolved.period_days == period_days,
                )
            )
            sync_service = SyncService(session_factory=lambda: session)
            if (
                has_target_price_period is not None
                and has_target_demand is not None
                and sync_service.refresh_trade_scope_from_existing_rows(
                    session,
                    target_location_id=resolved_target_location_id,
                    source_location_id=resolved_source_location_id,
                    type_id=type_id,
                    period_days=period_days,
                )
            ):
                return

            sync_service.prepare_trade_period(
                session,
                target_location_id=resolved_target_location_id,
                source_location_id=resolved_source_location_id,
                type_id=type_id,
                period_days=period_days,
                refresh_inputs=has_target_price_period is None or has_target_demand is None,
            )
        finally:
            session.close()
