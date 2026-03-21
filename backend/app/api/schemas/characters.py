from datetime import datetime

from pydantic import BaseModel


class CharacterListItem(BaseModel):
    id: int
    character_name: str
    corporation_name: str | None = None
    granted_scopes: list[str]
    sync_enabled: bool
    last_token_refresh: datetime | None = None
    last_successful_sync: datetime | None = None
    assets_sync_status: str
    orders_sync_status: str
    skills_sync_status: str
    structures_sync_status: str
    accessible_structure_count: int


class AccessibleStructureItem(BaseModel):
    structure_name: str
    structure_id: int
    system_name: str | None = None
    region_name: str | None = None
    access_verified_at: datetime
    tracking_enabled: bool
    polling_tier: str
    last_snapshot_at: datetime | None = None
    confidence_score: float


class CharacterDetail(BaseModel):
    id: int
    character_name: str
    corporation_name: str | None = None
    granted_scopes: list[str]
    sync_enabled: bool
    sync_toggles: dict[str, bool]
    structures: list[AccessibleStructureItem]
    skills: list[str]


class CharacterPatchRequest(BaseModel):
    sync_enabled: bool | None = None
