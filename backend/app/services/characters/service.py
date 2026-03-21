from datetime import UTC, datetime

from app.api.schemas.characters import AccessibleStructureItem, CharacterDetail, CharacterListItem
from app.core.security import build_esi_scopes


class CharacterService:
    def list_characters(self) -> list[CharacterListItem]:
        return [
            CharacterListItem(
                id=1,
                character_name="Demo Trader",
                corporation_name="Open Traders Union",
                granted_scopes=build_esi_scopes(),
                sync_enabled=True,
                last_token_refresh=datetime.now(UTC),
                last_successful_sync=datetime.now(UTC),
                assets_sync_status="ok",
                orders_sync_status="ok",
                skills_sync_status="pending",
                structures_sync_status="ok",
                accessible_structure_count=2,
            )
        ]

    def get_character(self, character_id: int) -> CharacterDetail:
        structure = AccessibleStructureItem(
            structure_name="Perimeter Market Keepstar",
            structure_id=1022734985679,
            system_name="Perimeter",
            region_name="The Forge",
            access_verified_at=datetime.now(UTC),
            tracking_enabled=True,
            polling_tier="core",
            last_snapshot_at=datetime.now(UTC),
            confidence_score=0.88,
        )
        return CharacterDetail(
            id=character_id,
            character_name="Demo Trader",
            corporation_name="Open Traders Union",
            granted_scopes=build_esi_scopes(),
            sync_enabled=True,
            sync_toggles={"assets": True, "orders": True, "skills": False, "structures": True},
            structures=[structure],
            skills=["Accounting IV", "Broker Relations IV"],
        )
