from fastapi import APIRouter

from app.api.schemas.settings import RegionOption, UserSettingsResponse, UserSettingsUpdate
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=UserSettingsResponse)
def get_settings_route() -> UserSettingsResponse:
    return SettingsService().get_settings()


@router.get("/source-regions", response_model=list[RegionOption])
def get_source_regions_route() -> list[RegionOption]:
    return SettingsService().list_source_region_options()


@router.put("", response_model=UserSettingsResponse)
def put_settings(payload: UserSettingsUpdate) -> UserSettingsResponse:
    return SettingsService().update_settings(payload)
