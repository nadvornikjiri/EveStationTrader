import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.settings import UserSettingsResponse, UserSettingsUpdate
from app.db.session import SessionLocal
from app.models.all_models import UserSetting

_SETTINGS_KEY = "defaults"


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
        row = session.scalar(select(UserSetting).where(UserSetting.user_id.is_(None), UserSetting.key == _SETTINGS_KEY))
        if row is None:
            return UserSettingsResponse(
                default_filters={
                    "min_item_profit": 15_000_000,
                    "min_order_margin_pct": 0.20,
                    "roi_now": 0.05,
                    "target_demand_day": 1,
                }
            )
        value = dict(row.value)
        value.pop("warning_threshold_pct", None)
        value.pop("warning_enabled", None)
        return UserSettingsResponse(**value)

    @staticmethod
    def _apply_runtime_flags(settings: UserSettingsResponse) -> None:
        root_level = logging.DEBUG if settings.debug_enabled else logging.INFO
        http_level = logging.DEBUG if settings.debug_enabled else logging.WARNING
        logging.getLogger().setLevel(root_level)
        logging.getLogger("httpx").setLevel(http_level)
        logging.getLogger("httpcore").setLevel(http_level)
