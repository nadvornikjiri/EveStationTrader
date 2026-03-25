from datetime import UTC, datetime
from typing import Callable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.schemas.trade import OpportunityItemDetail, OpportunityItemRow, SourceSummary, TargetLocation
from app.db.session import SessionLocal
from app.domain.enums import LocationType
from app.repositories.seed_data import CURATED_STATIONS


CURATED_TARGET_LOCATION_IDS = tuple(station.station_id for station in CURATED_STATIONS)


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
                .where(
                    Location.location_type == LocationType.NPC_STATION.value,
                    Location.location_id.in_(CURATED_TARGET_LOCATION_IDS),
                )
                .order_by(Location.name)
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
        from app.services.sync.service import SyncService

        session = self.session_factory()
        try:
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
        from app.services.sync.service import SyncService

        session = self.session_factory()
        try:
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
            return []
        finally:
            session.close()

    def list_items(self, target_location_id: int, source_location_id: int, period_days: int) -> list[OpportunityItemRow]:
        from app.models.all_models import Item, OpportunityItem
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
            return []
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
                confidence_score=item.confidence_score,
            )
        finally:
            session.close()

        return OpportunityItemDetail(
            type_id=type_id,
            item_name=metrics.item_name,
            target_market_sell_orders=[],
            source_market_sell_orders=[],
            source_market_buy_orders=[],
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
