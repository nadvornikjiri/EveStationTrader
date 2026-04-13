import logging
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.settings import UserSettingsResponse, UserSettingsUpdate
from app.db.session import SessionLocal
from app.models.all_models import Location, UserSetting

_SETTINGS_KEY = "defaults"
_DEFAULT_TARGET_MARKET_LOCATION_IDS = [
    60003760,  # Jita IV - Moon 4 - Caldari Navy Assembly Plant
    60008494,  # Amarr VIII (Oris) - Emperor Family Academy
    60011866,  # Dodixie IX - Moon 20 - Federation Navy Assembly Plant
    60005686,  # Hek VIII - Moon 12 - Boundless Creation Factory
    60004588,  # Rens VI - Moon 8 - Brutor Tribe Treasury
]
_DEFAULT_SOURCE_REGION_IDS = [
    10000002,  # The Forge
    10000043,  # Domain
    10000032,  # Sinq Laison
    10000042,  # Metropolis
    10000030,  # Heimatar
]
_DEFAULT_SETTINGS: dict[str, Any] = {
    "default_analysis_period_days": 14,
    "trade_groups_page_size": 20,
    "debug_enabled": False,
    "sales_tax_rate": 0.036,
    "broker_fee_rate": 0.03,
    "default_user_structure_poll_interval_minutes": 30,
    "snapshot_retention_days": 30,
    "fallback_policy": "regional_fallback",
    "shipping_cost_per_m3": 350.0,
    "target_market_location_ids": list(_DEFAULT_TARGET_MARKET_LOCATION_IDS),
    "source_region_ids": list(_DEFAULT_SOURCE_REGION_IDS),
    "default_filters": {
        "min_item_profit": 15_000_000,
        "roi_now": 0.20,
        "target_demand_day": 1,
    },
}


class SettingsService:
    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory

    def get_settings(self) -> UserSettingsResponse:
        session = self.session_factory()
        try:
            return self.get_settings_for_session(session)
        finally:
            session.close()

    def get_settings_for_session(self, session: Session) -> UserSettingsResponse:
        settings = self._load_settings(session)
        self._apply_runtime_flags(settings)
        return settings

    def update_settings(self, payload: UserSettingsUpdate) -> UserSettingsResponse:
        session = self.session_factory()
        try:
            row = session.scalar(select(UserSetting).where(UserSetting.user_id.is_(None), UserSetting.key == _SETTINGS_KEY))
            settings = UserSettingsResponse(**payload.model_dump())
            if row is None:
                session.add(UserSetting(user_id=None, key=_SETTINGS_KEY, value=settings.model_dump()))
            else:
                row.value = settings.model_dump()
            session.commit()
            self._apply_runtime_flags(settings)
            return settings
        finally:
            session.close()

    def _load_settings(self, session: Session) -> UserSettingsResponse:
        default_target_market_location_ids = self._default_target_market_location_ids(session)
        row = session.scalar(select(UserSetting).where(UserSetting.user_id.is_(None), UserSetting.key == _SETTINGS_KEY))
        if row is None:
            default_settings = dict(_DEFAULT_SETTINGS)
            default_settings["target_market_location_ids"] = default_target_market_location_ids
            return self._build_settings_response(default_settings)
        value = cast(dict[str, Any], dict(row.value))
        value.pop("warning_threshold_pct", None)
        value.pop("warning_enabled", None)
        value.pop("min_confidence_for_local_structure_demand", None)
        default_filters = value.get("default_filters", {})
        if not isinstance(default_filters, dict):
            default_filters = {}
        merged_value = dict(_DEFAULT_SETTINGS)
        merged_value["target_market_location_ids"] = default_target_market_location_ids
        merged_value.update(value)
        merged_value["default_filters"] = {
            **_DEFAULT_SETTINGS["default_filters"],
            **cast(dict[str, Any], default_filters),
        }
        return self._build_settings_response(merged_value)

    @staticmethod
    def _default_target_market_location_ids(session: Session) -> list[int]:
        configured_ids = list(_DEFAULT_TARGET_MARKET_LOCATION_IDS)
        perimeter_ttt_id = session.scalar(
            select(Location.location_id).where(Location.name.ilike("%tranquility trading tower%"))
        )
        if perimeter_ttt_id is not None and perimeter_ttt_id not in configured_ids:
            configured_ids.append(int(perimeter_ttt_id))
        return configured_ids

    @staticmethod
    def _build_settings_response(value: dict[str, Any]) -> UserSettingsResponse:
        return UserSettingsResponse(
            default_analysis_period_days=int(value["default_analysis_period_days"]),
            trade_groups_page_size=max(int(value.get("trade_groups_page_size", 20)), 1),
            debug_enabled=bool(value["debug_enabled"]),
            sales_tax_rate=float(value["sales_tax_rate"]),
            broker_fee_rate=float(value["broker_fee_rate"]),
            default_user_structure_poll_interval_minutes=int(value["default_user_structure_poll_interval_minutes"]),
            snapshot_retention_days=int(value["snapshot_retention_days"]),
            fallback_policy=str(value["fallback_policy"]),
            shipping_cost_per_m3=float(value["shipping_cost_per_m3"]),
            target_market_location_ids=[int(location_id) for location_id in list(value["target_market_location_ids"])],
            source_region_ids=[int(r) for r in list(value.get("source_region_ids", []))],
            default_filters=dict(value["default_filters"]),
        )

    @staticmethod
    def _apply_runtime_flags(settings: UserSettingsResponse) -> None:
        app_level = logging.DEBUG if settings.debug_enabled else logging.INFO
        sql_level = logging.DEBUG if settings.debug_enabled else logging.INFO
        http_level = logging.DEBUG if settings.debug_enabled else logging.WARNING
        logging.getLogger().setLevel(app_level)
        logging.getLogger("app.requests").setLevel(app_level)
        logging.getLogger("app.imports").setLevel(app_level)
        logging.getLogger("uvicorn.access").setLevel(app_level)
        logging.getLogger("uvicorn.error").setLevel(app_level)
        logging.getLogger("app.db.queries").setLevel(sql_level)
        logging.getLogger("sqlalchemy.engine").setLevel(sql_level)
        logging.getLogger("httpx").setLevel(http_level)
        logging.getLogger("httpcore").setLevel(http_level)
