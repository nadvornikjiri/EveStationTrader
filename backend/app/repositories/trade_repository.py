from datetime import UTC, datetime
from typing import Any, Callable, cast

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.orm import Session, aliased

from app.api.schemas.trade import (
    InTransitAssetRecord,
    InTransitAssetUpsertRequest,
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
        source_units_available_column: Any,
        target_dos_column: Any,
        item_volume_m3_column: Any,
        demand_source_column: Any,
        esi_demand_day_column: Any,
        item_search: str,
        min_profit: float,
        min_roi_now_pct: float,
        min_demand_day: float,
        max_dos: float | None,
        max_item_volume_m3: float | None,
        source_type: str,
        min_security: str,
        demand_source: str,
        min_esi_demand_day: float = 0.0,
    ) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        search_value = item_search.strip()
        if search_value:
            conditions.append(item_name_column.ilike(f"%{search_value}%"))
        if min_profit > 0:
            item_qty = func.least(func.ceil(target_demand_day_column), source_units_available_column)
            conditions.append(target_now_profit_column * item_qty > min_profit)
        if min_roi_now_pct > 0:
            conditions.append(roi_now_column > (min_roi_now_pct / 100.0))
        if min_demand_day > 0:
            conditions.append(target_demand_day_column >= min_demand_day)
        if max_dos is not None:
            conditions.append(target_dos_column <= max_dos)
        if max_item_volume_m3 is not None:
            conditions.append(item_volume_m3_column <= max_item_volume_m3)
        conditions.append(source_security_column >= TradeRepository._min_security_threshold(min_security))
        if source_type == "npc":
            conditions.append(location_type_column == LocationType.NPC_STATION.value)
        elif source_type == "structure":
            conditions.append(location_type_column == LocationType.STRUCTURE.value)
        if demand_source != "all":
            conditions.append(demand_source_column == demand_source)
        if min_esi_demand_day > 0:
            conditions.append(esi_demand_day_column >= min_esi_demand_day)
        return conditions

    @staticmethod
    def _build_market_browser_url(region_id: int | None, type_id: int) -> str | None:
        if region_id is None:
            return None
        return f"https://evemarketbrowser.com/region/{region_id}/type/{type_id}"

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
        max_item_volume_m3: float | None = None,
        source_type: str = "all",
        min_security: str = "all",
        demand_source: str = "all",
        min_esi_demand_day: float = 0.0,
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

            has_item_filters = any(
                (
                    item_search.strip(),
                    min_profit > 0,
                    min_roi_now_pct > 0,
                    min_demand_day > 0,
                    max_dos is not None,
                    max_item_volume_m3 is not None,
                    source_type != "all",
                    min_security != "all",
                    demand_source != "all",
                    min_esi_demand_day > 0,
                )
            )
            if not has_item_filters:
                summary_rows = session.execute(
                    select(
                        OpportunitySourceSummary.source_location_id,
                        resolved_name,
                        OpportunitySourceSummary.source_security_status,
                        OpportunitySourceSummary.purchase_units_total,
                        OpportunitySourceSummary.source_units_available_total,
                        OpportunitySourceSummary.target_demand_day_total,
                        OpportunitySourceSummary.target_supply_units_total,
                        OpportunitySourceSummary.target_dos_weighted,
                        OpportunitySourceSummary.in_transit_units,
                        OpportunitySourceSummary.assets_units,
                        OpportunitySourceSummary.active_sell_orders_units,
                        OpportunitySourceSummary.source_avg_price_weighted,
                        OpportunitySourceSummary.target_now_price_weighted,
                        OpportunitySourceSummary.target_period_avg_price_weighted,
                        OpportunitySourceSummary.target_now_profit_weighted,
                        OpportunitySourceSummary.target_period_profit_weighted,
                        OpportunitySourceSummary.capital_required_total,
                        OpportunitySourceSummary.roi_now_weighted,
                        OpportunitySourceSummary.roi_period_weighted,
                        OpportunitySourceSummary.total_item_volume_m3,
                        OpportunitySourceSummary.shipping_cost_total,
                        OpportunitySourceSummary.demand_source_summary,
                        OpportunitySourceSummary.esi_demand_day_total,
                    )
                    .join(Location, Location.id == OpportunitySourceSummary.source_location_id)
                    .outerjoin(Station, Station.station_id == Location.location_id)
                    .where(
                        OpportunitySourceSummary.target_location_id == resolved_target_location_id,
                        OpportunitySourceSummary.period_days == period_days,
                    )
                    .order_by(OpportunitySourceSummary.target_now_profit_weighted.desc(), resolved_name.asc())
                ).all()
                if summary_rows:
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
                            esi_demand_day_total=esi_demand_day_total,
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
                            esi_demand_day_total,
                        ) in summary_rows
                    ]

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
                source_units_available_column=OpportunityItem.source_units_available,
                target_dos_column=OpportunityItem.target_dos,
                item_volume_m3_column=OpportunityItem.item_volume_m3,
                demand_source_column=OpportunityItem.demand_source,
                esi_demand_day_column=OpportunityItem.esi_demand_day,
                item_search=item_search,
                min_profit=min_profit,
                min_roi_now_pct=min_roi_now_pct,
                min_demand_day=min_demand_day,
                max_dos=max_dos,
                max_item_volume_m3=max_item_volume_m3,
                source_type=source_type,
                min_security=min_security,
                demand_source=demand_source,
                min_esi_demand_day=min_esi_demand_day,
            )
            item_qty = func.least(func.ceil(OpportunityItem.target_demand_day), OpportunityItem.source_units_available)
            rows = session.execute(
                select(
                    OpportunityItem.source_location_id,
                    resolved_name,
                    (func.sum(OpportunityItem.source_security_status * weight) / total_weight),
                    func.sum(item_qty),
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
                    func.sum(OpportunityItem.target_now_profit * item_qty),
                    func.sum(OpportunityItem.target_period_profit * item_qty),
                    func.sum(OpportunityItem.source_station_sell_price * item_qty),
                    (func.sum(OpportunityItem.roi_now * weight) / total_weight),
                    (func.sum(OpportunityItem.roi_period * weight) / total_weight),
                    func.sum(OpportunityItem.item_volume_m3 * item_qty),
                    func.sum(OpportunityItem.shipping_cost),
                    demand_source_summary,
                    func.sum(OpportunityItem.esi_demand_day),
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
                .order_by(func.sum(OpportunityItem.target_now_profit * item_qty).desc(), resolved_name.asc())
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
                        esi_demand_day_total=esi_demand_day_total,
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
                        esi_demand_day_total,
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
        max_item_volume_m3: float | None = None,
        source_type: str = "all",
        min_security: str = "all",
        demand_source: str = "all",
        min_esi_demand_day: float = 0.0,
    ) -> list[OpportunityItemRow]:
        from app.models.all_models import Item, Location, OpportunityItem, Region
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
            target_region_id = session.scalar(
                select(Region.region_id)
                .join(Location, Location.region_id == Region.id)
                .where(Location.id == resolved_target_location_id)
            )

            conditions = self._item_filter_conditions(
                item_name_column=Item.name,
                location_type_column=Location.location_type,
                source_security_column=OpportunityItem.source_security_status,
                target_now_profit_column=OpportunityItem.target_now_profit,
                roi_now_column=OpportunityItem.roi_now,
                target_demand_day_column=OpportunityItem.target_demand_day,
                source_units_available_column=OpportunityItem.source_units_available,
                target_dos_column=OpportunityItem.target_dos,
                item_volume_m3_column=OpportunityItem.item_volume_m3,
                demand_source_column=OpportunityItem.demand_source,
                esi_demand_day_column=OpportunityItem.esi_demand_day,
                item_search=item_search,
                min_profit=min_profit,
                min_roi_now_pct=min_roi_now_pct,
                min_demand_day=min_demand_day,
                max_dos=max_dos,
                max_item_volume_m3=max_item_volume_m3,
                source_type=source_type,
                min_security=min_security,
                demand_source=demand_source,
                min_esi_demand_day=min_esi_demand_day,
            )
            from app.models.all_models import MarketPricePeriod, MarketVolumePeriod
            mpp7 = aliased(MarketPricePeriod)
            mvp7 = aliased(MarketVolumePeriod)
            rows = (
                session.execute(
                    select(
                        OpportunityItem,
                        Item.name,
                        Item.type_id,
                        mpp7.period_avg_price,
                        mvp7.current_sell_volume,
                        mvp7.period_avg_sell_volume,
                    )
                    .join(Item, Item.id == OpportunityItem.type_id)
                    .join(Location, Location.id == OpportunityItem.source_location_id)
                    .outerjoin(mpp7, and_(
                        mpp7.location_id == OpportunityItem.target_location_id,
                        mpp7.type_id == OpportunityItem.type_id,
                        mpp7.period_days == 7,
                    ))
                    .outerjoin(mvp7, and_(
                        mvp7.location_id == OpportunityItem.target_location_id,
                        mvp7.type_id == OpportunityItem.type_id,
                        mvp7.period_days == 7,
                    ))
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
                        type_id=external_type_id,
                        item_name=item_name,
                        market_browser_url=self._build_market_browser_url(target_region_id, external_type_id),
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
                        target_7d_price_delta=(
                            (item.target_station_sell_price - period_avg_7d) / period_avg_7d
                            if period_avg_7d
                            else None
                        ),
                        target_7d_vol_delta=(
                            (current_sell_volume - period_avg_sell_volume) / period_avg_sell_volume
                            if current_sell_volume is not None
                            and period_avg_sell_volume is not None
                            and period_avg_sell_volume > 0
                            else None
                        ),
                        target_period_avg_price=item.target_period_avg_price,
                        target_now_profit=item.target_now_profit,
                        target_period_profit=item.target_period_profit,
                        capital_required=item.capital_required,
                        roi_now=item.roi_now,
                        roi_period=item.roi_period,
                        item_volume_m3=item.item_volume_m3,
                        shipping_cost=item.shipping_cost,
                        demand_source=item.demand_source,
                        esi_demand_day=item.esi_demand_day,
                    )
                    for (
                        item,
                        item_name,
                        external_type_id,
                        period_avg_7d,
                        current_sell_volume,
                        period_avg_sell_volume,
                    ) in rows
                ]
            return []
        finally:
            session.close()

    def list_target_items(self, target_location_id: int, period_days: int) -> list[TargetOpportunityItemRow]:
        from app.models.all_models import Item, Location, OpportunityItem, Region
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
            target_region_id = session.scalar(
                select(Region.region_id)
                .join(Location, Location.region_id == Region.id)
                .where(Location.id == resolved_target_location_id)
            )

            rows = (
                session.execute(
                    select(OpportunityItem, Item.name, Item.type_id)
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
                    type_id=external_type_id,
                    item_name=item_name,
                    market_browser_url=self._build_market_browser_url(target_region_id, external_type_id),
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
                    esi_demand_day=item.esi_demand_day,
                )
                for item, item_name, external_type_id in rows
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
        from app.models.all_models import Item, Location, OpportunityItem, Region
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
            target_region_id = session.scalar(
                select(Region.region_id)
                .join(Location, Location.region_id == Region.id)
                .where(Location.id == resolved_target_location_id)
            )
            metrics = OpportunityItemRow(
                type_id=type_id,
                item_name=item_name,
                market_browser_url=self._build_market_browser_url(target_region_id, type_id),
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
                esi_demand_day=item.esi_demand_day,
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

    def list_in_transit_assets(self, target_location_id: int) -> list[InTransitAssetRecord]:
        from app.models.all_models import InTransitAsset, Item, Location, Station

        session = self.session_factory()
        try:
            resolved_target_location_id = self._resolve_location_id(session, target_location_id)
            if resolved_target_location_id is None:
                return []

            source_name = self._display_location_name(Location.name, Station.name)
            target_location = Location.__table__.alias("target_location")
            target_station = Station.__table__.alias("target_station")
            target_name = self._display_location_name(target_location.c.name, target_station.c.name)

            rows = session.execute(
                select(
                    InTransitAsset.id,
                    Location.location_id,
                    source_name,
                    target_location.c.location_id,
                    target_name,
                    Item.type_id,
                    Item.name,
                    InTransitAsset.quantity,
                    InTransitAsset.note,
                    InTransitAsset.created_at,
                    InTransitAsset.updated_at,
                )
                .join(Location, Location.id == InTransitAsset.source_location_id)
                .outerjoin(Station, Station.station_id == Location.location_id)
                .join(target_location, target_location.c.id == InTransitAsset.target_location_id)
                .outerjoin(target_station, target_station.c.station_id == target_location.c.location_id)
                .join(Item, Item.id == InTransitAsset.type_id)
                .where(InTransitAsset.target_location_id == resolved_target_location_id)
                .order_by(Location.location_id.asc(), Item.name.asc())
            ).all()
            return [
                InTransitAssetRecord(
                    id=entry_id,
                    source_location_id=source_external_location_id,
                    source_market_name=source_market_name,
                    target_location_id=target_external_location_id,
                    target_market_name=target_market_name,
                    type_id=external_type_id,
                    item_name=item_name,
                    quantity=quantity,
                    note=note,
                    created_at=created_at,
                    updated_at=updated_at,
                )
                for (
                    entry_id,
                    source_external_location_id,
                    source_market_name,
                    target_external_location_id,
                    target_market_name,
                    external_type_id,
                    item_name,
                    quantity,
                    note,
                    created_at,
                    updated_at,
                ) in rows
            ]
        finally:
            session.close()

    def upsert_in_transit_asset(self, payload: InTransitAssetUpsertRequest) -> InTransitAssetRecord:
        from app.models.all_models import InTransitAsset

        session = self.session_factory()
        try:
            resolved_source_location_id = self._resolve_location_id(session, payload.source_location_id)
            resolved_target_location_id = self._resolve_location_id(session, payload.target_location_id)
            resolved_type_id = self._resolve_type_id(session, payload.type_id)
            if resolved_source_location_id is None:
                raise LookupError(f"Unknown source location {payload.source_location_id}.")
            if resolved_target_location_id is None:
                raise LookupError(f"Unknown target location {payload.target_location_id}.")
            if resolved_type_id is None:
                raise LookupError(f"Unknown item type {payload.type_id}.")
            if payload.quantity < 1:
                raise ValueError("In-transit quantity must be at least 1.")

            entry = session.scalar(
                select(InTransitAsset).where(
                    InTransitAsset.source_location_id == resolved_source_location_id,
                    InTransitAsset.target_location_id == resolved_target_location_id,
                    InTransitAsset.type_id == resolved_type_id,
                )
            )
            if entry is None:
                entry = InTransitAsset(
                    source_location_id=resolved_source_location_id,
                    target_location_id=resolved_target_location_id,
                    type_id=resolved_type_id,
                )
                session.add(entry)

            entry.quantity = payload.quantity
            entry.note = payload.note.strip() if payload.note and payload.note.strip() else None
            session.commit()
            session.refresh(entry)
        finally:
            session.close()

        records = self.list_in_transit_assets(payload.target_location_id)
        for record in records:
            if (
                record.source_location_id == payload.source_location_id
                and record.target_location_id == payload.target_location_id
                and record.type_id == payload.type_id
            ):
                return record
        raise LookupError("In-transit asset could not be read back after save.")

    def delete_in_transit_asset(self, entry_id: int) -> bool:
        from app.models.all_models import InTransitAsset

        session = self.session_factory()
        try:
            entry = session.get(InTransitAsset, entry_id)
            if entry is None:
                return False
            session.delete(entry)
            session.commit()
            return True
        finally:
            session.close()

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

        # Location.id is a 32-bit INTEGER; structure EVE IDs exceed that range.
        # Only compare against Location.id when the value fits in 32 bits.
        max_int32 = 2_147_483_647
        if location_reference <= max_int32:
            condition = or_(
                Location.id == location_reference,
                Location.location_id == location_reference,
            )
        else:
            condition = Location.location_id == location_reference

        return session.scalar(select(Location.id).where(condition))

    @staticmethod
    def _resolve_type_id(session: Session, type_reference: int) -> int | None:
        from app.models.all_models import Item

        return session.scalar(
            select(Item.id).where(
                or_(
                    Item.id == type_reference,
                    Item.type_id == type_reference,
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

    def _create_target_rebuild_job(self, target_location_id: int) -> int:
        from app.models.all_models import SyncJobRun
        job_session = self.session_factory()
        try:
            job_run = SyncJobRun(
                job_type="target_rebuild",
                status="running",
                triggered_by="manual",
                started_at=datetime.now(UTC),
                records_processed=0,
                target_type="location",
                target_id=str(target_location_id),
                progress_phase="Starting",
                progress_current=None,
                progress_total=None,
                progress_unit=None,
                message="Rebuilding opportunities for target.",
            )
            job_session.add(job_run)
            job_session.flush()
            job_session.commit()
            return job_run.id
        finally:
            job_session.close()

    def _update_target_rebuild_job(
        self,
        job_id: int,
        *,
        progress_phase: str,
        message: str,
        progress_current: int | None = None,
        progress_total: int | None = None,
    ) -> None:
        from app.models.all_models import SyncJobRun
        job_session = self.session_factory()
        try:
            job_run = job_session.get(SyncJobRun, job_id)
            if job_run is None or job_run.finished_at is not None:
                return
            job_run.progress_phase = progress_phase
            job_run.message = message
            if progress_current is not None:
                job_run.progress_current = progress_current
            if progress_total is not None:
                job_run.progress_total = progress_total
            job_session.commit()
        finally:
            job_session.close()

    def _finish_target_rebuild_job(self, job_id: int, *, started_at: datetime, error: Exception | None) -> None:
        from app.models.all_models import SyncJobRun
        job_session = self.session_factory()
        try:
            job_run = job_session.get(SyncJobRun, job_id)
            if job_run is None:
                return
            finished_at = datetime.now(UTC)
            job_run.finished_at = finished_at
            job_run.duration_ms = max(int((finished_at - started_at).total_seconds() * 1000), 0)
            if error is None:
                job_run.status = "success"
                job_run.progress_phase = "Completed"
                job_run.message = "Rebuild complete."
            else:
                job_run.status = "failed"
                job_run.progress_phase = "Failed"
                job_run.message = f"Rebuild failed: {error}"
                job_run.error_details = str(error)
            job_session.commit()
        finally:
            job_session.close()

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

        started_at = datetime.now(UTC)
        job_id = self._create_target_rebuild_job(target_location_id)
        session = self.session_factory()
        try:
            # Step 1/5: Resolve location
            self._update_target_rebuild_job(
                job_id,
                progress_phase="Resolving location",
                message="Resolving target location.",
                progress_current=0,
                progress_total=5,
            )
            resolved_target_location_id = self._resolve_location_id(session, target_location_id)
            if resolved_target_location_id is None:
                raise LookupError(f"Target location {target_location_id} was not found.")

            resolved_source_location_id: int | None = None
            if source_location_id is not None:
                resolved_source_location_id = self._resolve_location_id(session, source_location_id)
                if resolved_source_location_id is None:
                    raise LookupError(f"Source location {source_location_id} was not found.")

            # Step 2/5: Check existing data
            self._update_target_rebuild_job(
                job_id,
                progress_phase="Checking existing market data",
                message="Checking for existing price and demand data.",
                progress_current=1,
                progress_total=5,
            )
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
            ):
                # Step 3/5: Fast-path rebuild from existing rows
                self._update_target_rebuild_job(
                    job_id,
                    progress_phase="Rebuilding opportunities",
                    message="Generating opportunities from existing market data.",
                    progress_current=3,
                    progress_total=5,
                )
                if sync_service.refresh_trade_scope_from_existing_rows(
                    session,
                    target_location_id=resolved_target_location_id,
                    source_location_id=resolved_source_location_id,
                    type_id=type_id,
                    period_days=period_days,
                ):
                    self._update_target_rebuild_job(
                        job_id,
                        progress_phase="Finalizing",
                        message="Committing results.",
                        progress_current=5,
                        progress_total=5,
                    )
                    self._finish_target_rebuild_job(job_id, started_at=started_at, error=None)
                    return

            # Step 3/5: Refresh market inputs (slow path)
            needs_refresh = has_target_price_period is None or has_target_demand is None
            if needs_refresh:
                self._update_target_rebuild_job(
                    job_id,
                    progress_phase="Refreshing market prices",
                    message="Fetching latest price periods and demand data.",
                    progress_current=2,
                    progress_total=5,
                )

            # Step 4/5: Generate opportunities
            self._update_target_rebuild_job(
                job_id,
                progress_phase="Generating opportunities",
                message="Computing opportunity items and source summaries.",
                progress_current=3,
                progress_total=5,
            )
            sync_service.prepare_trade_period(
                session,
                target_location_id=resolved_target_location_id,
                source_location_id=resolved_source_location_id,
                type_id=type_id,
                period_days=period_days,
                refresh_inputs=needs_refresh,
            )

            # Step 5/5: Done
            self._update_target_rebuild_job(
                job_id,
                progress_phase="Finalizing",
                message="Committing results.",
                progress_current=5,
                progress_total=5,
            )
            self._finish_target_rebuild_job(job_id, started_at=started_at, error=None)
        except Exception as exc:
            self._finish_target_rebuild_job(job_id, started_at=started_at, error=exc)
            raise
        finally:
            session.close()
