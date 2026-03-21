from fastapi import APIRouter

from app.api.schemas.settings import UserSettingsResponse, UserSettingsUpdate
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=UserSettingsResponse)
def get_settings_route() -> UserSettingsResponse:
    return SettingsService().get_settings()


@router.put("", response_model=UserSettingsResponse)
def put_settings(payload: UserSettingsUpdate) -> UserSettingsResponse:
    return SettingsService().update_settings(payload)
