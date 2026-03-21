from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas.characters import AccessibleStructureItem, CharacterDetail, CharacterListItem
from app.db.session import SessionLocal
from app.models.all_models import CharacterAccessibleStructure, EsiCharacter, EsiCharacterSyncState


class CharacterService:
    def __init__(self, *, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self.session_factory = session_factory

    def enable_character_structure_tracking(self, character_id: int, structure_id: int) -> CharacterAccessibleStructure:
        session = self.session_factory()
        try:
            character = session.scalar(select(EsiCharacter).where(EsiCharacter.character_id == character_id))
            if character is None:
                raise LookupError(f"Character {character_id} was not found.")

            structure = session.scalar(
                select(CharacterAccessibleStructure).where(
                    CharacterAccessibleStructure.character_id == character.id,
                    CharacterAccessibleStructure.structure_id == structure_id,
                )
            )
            if structure is None:
                raise LookupError(f"Structure {structure_id} is not accessible for character {character_id}.")

            if not structure.tracking_enabled:
                structure.tracking_enabled = True
            session.commit()
            session.refresh(structure)
            return structure
        finally:
            session.close()

    def update_character_sync_enabled(self, character_id: int, sync_enabled: bool | None) -> EsiCharacter | None:
        session = self.session_factory()
        try:
            character = session.scalar(select(EsiCharacter).where(EsiCharacter.character_id == character_id))
            if character is None:
                return None

            if sync_enabled is not None and character.sync_enabled != sync_enabled:
                character.sync_enabled = sync_enabled
                session.commit()
                session.refresh(character)
            else:
                session.commit()

            return character
        finally:
            session.close()

    def list_characters(self) -> list[CharacterListItem]:
        session = self.session_factory()
        try:
            characters = session.scalars(select(EsiCharacter).order_by(EsiCharacter.character_id.asc())).all()
            if not characters:
                return []

            character_ids = [character.id for character in characters]
            sync_states = {
                state.character_id: state
                for state in session.scalars(
                    select(EsiCharacterSyncState).where(EsiCharacterSyncState.character_id.in_(character_ids))
                ).all()
            }
            structure_counts_rows = session.execute(
                select(
                    CharacterAccessibleStructure.character_id,
                    func.count(CharacterAccessibleStructure.id),
                )
                .where(CharacterAccessibleStructure.character_id.in_(character_ids))
                .group_by(CharacterAccessibleStructure.character_id)
            ).all()
            structure_counts: dict[int, int] = {
                character_id: structure_count for character_id, structure_count in structure_counts_rows
            }

            return [
                self._build_character_list_item(
                    character=character,
                    sync_state=sync_states.get(character.id),
                    accessible_structure_count=structure_counts.get(character.id, 0),
                )
                for character in characters
            ]
        finally:
            session.close()

    def get_character(self, character_id: int) -> CharacterDetail:
        session = self.session_factory()
        try:
            character = session.scalar(select(EsiCharacter).where(EsiCharacter.character_id == character_id))
            if character is None:
                raise LookupError(f"Character {character_id} was not found.")

            structures = session.scalars(
                select(CharacterAccessibleStructure)
                .where(CharacterAccessibleStructure.character_id == character.id)
                .order_by(CharacterAccessibleStructure.structure_name.asc())
            ).all()

            return CharacterDetail(
                id=character.character_id,
                character_name=character.character_name,
                corporation_name=character.corporation_name,
                granted_scopes=self._split_scopes(character.granted_scopes),
                sync_enabled=character.sync_enabled,
                sync_toggles={
                    "assets": character.sync_enabled,
                    "orders": character.sync_enabled,
                    "skills": character.sync_enabled,
                    "structures": character.sync_enabled,
                },
                structures=[self._build_structure_item(structure) for structure in structures],
                skills=[],
            )
        finally:
            session.close()

    def _build_character_list_item(
        self,
        *,
        character: EsiCharacter,
        sync_state: EsiCharacterSyncState | None,
        accessible_structure_count: int,
    ) -> CharacterListItem:
        return CharacterListItem(
            id=character.character_id,
            character_name=character.character_name,
            corporation_name=character.corporation_name,
            granted_scopes=self._split_scopes(character.granted_scopes),
            sync_enabled=character.sync_enabled,
            last_token_refresh=sync_state.last_token_refresh if sync_state else None,
            last_successful_sync=sync_state.last_successful_sync if sync_state else None,
            assets_sync_status=sync_state.assets_sync_status if sync_state else "pending",
            orders_sync_status=sync_state.orders_sync_status if sync_state else "pending",
            skills_sync_status=sync_state.skills_sync_status if sync_state else "pending",
            structures_sync_status=sync_state.structures_sync_status if sync_state else "pending",
            accessible_structure_count=accessible_structure_count,
        )

    def _build_structure_item(self, structure: CharacterAccessibleStructure) -> AccessibleStructureItem:
        return AccessibleStructureItem(
            structure_name=structure.structure_name,
            structure_id=structure.structure_id,
            system_name=structure.system_name,
            region_name=structure.region_name,
            access_verified_at=structure.access_verified_at,
            tracking_enabled=structure.tracking_enabled,
            polling_tier=structure.polling_tier,
            last_snapshot_at=structure.last_snapshot_at,
            confidence_score=structure.confidence_score,
        )

    def _split_scopes(self, granted_scopes: str) -> list[str]:
        return granted_scopes.split() if granted_scopes else []
