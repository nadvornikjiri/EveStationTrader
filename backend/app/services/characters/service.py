from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas.characters import AccessibleStructureItem, CharacterDetail, CharacterListItem
from app.db.session import SessionLocal
from app.models.all_models import (
    CharacterAccessibleStructure,
    CharacterAsset,
    CharacterOrder,
    EsiCharacter,
    EsiCharacterSyncState,
    EsiCharacterToken,
    Location,
    Item,
    Region,
    System,
    TrackedStructure,
)
from app.services.esi.client import (
    EsiAccessibleStructureRecord,
    EsiCharacterAssetRecord,
    EsiCharacterOrderRecord,
    EsiClient,
)


@dataclass(frozen=True)
class DiscoveredStructureInput:
    structure_id: int
    structure_name: str
    system_name: str | None
    region_name: str | None
    access_verified_at: datetime | None = None
    tracking_enabled: bool = False
    polling_tier: str = "user"
    last_snapshot_at: datetime | None = None
    confidence_score: float = 0.0


class CharacterSyncCapableEsiClient(Protocol):
    def refresh_access_token(self, refresh_token: str) -> dict: ...

    def fetch_character_assets(self, access_token: str) -> list[EsiCharacterAssetRecord]: ...

    def fetch_character_orders(self, access_token: str) -> list[EsiCharacterOrderRecord]: ...

    def fetch_accessible_structures(self, access_token: str) -> list[EsiAccessibleStructureRecord]: ...

    def resolve_structure_info(self, access_token: str, structure_id: int) -> dict | None: ...


class CharacterService:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        esi_client: CharacterSyncCapableEsiClient | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.esi_client = esi_client or EsiClient()

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
            self._upsert_tracked_structure(session, character.id, structure)
            session.commit()
            session.refresh(structure)
            return structure
        finally:
            session.close()

    def _ensure_valid_token(self, session: Session, character: EsiCharacter) -> str:
        """Refresh the access token if expired, return a valid access token.

        Only marks the character for re-authentication when CCP explicitly
        rejects the refresh token (``EsiTokenRevokedError``).  Transient
        failures (network, 5xx) are propagated so the sync job can retry
        later without permanently disabling the character.
        """
        from app.services.esi.client import EsiTokenRevokedError, EsiTokenRefreshError

        token = session.scalar(select(EsiCharacterToken).where(EsiCharacterToken.character_id == character.id))
        if token is None:
            raise LookupError(f"No token found for character {character.character_name}")

        # Refresh if token expires within 2 minutes
        if token.expires_at and token.expires_at < datetime.now(UTC) + timedelta(minutes=2):
            try:
                refreshed = self.esi_client.refresh_access_token(token.refresh_token)
                token.access_token = refreshed["access_token"]
                token.refresh_token = refreshed.get("refresh_token", token.refresh_token)
                token.expires_at = datetime.fromisoformat(refreshed["expires_at"])
                session.flush()
            except EsiTokenRevokedError:
                self._mark_character_reauth_required(session, character)
                raise LookupError(
                    f"Token permanently revoked for character {character.character_name}. "
                    "Reconnect the same character via EVE SSO."
                )
            except EsiTokenRefreshError as exc:
                # Transient — don't disable the character, just skip this sync cycle
                raise LookupError(
                    f"Temporary token refresh failure for {character.character_name}: {exc}. "
                    "Will retry on next sync cycle."
                )

        return token.access_token

    def _mark_character_reauth_required(self, session: Session, character: EsiCharacter) -> None:
        sync_state = session.scalar(
            select(EsiCharacterSyncState).where(EsiCharacterSyncState.character_id == character.id)
        )
        if sync_state is None:
            sync_state = EsiCharacterSyncState(character_id=character.id)
            session.add(sync_state)

        character.sync_enabled = False
        sync_state.last_token_refresh = datetime.now(UTC)
        sync_state.assets_sync_status = "reauth_required"
        sync_state.orders_sync_status = "reauth_required"
        sync_state.skills_sync_status = "reauth_required"
        sync_state.structures_sync_status = "reauth_required"
        session.commit()

    def sync_character(self, character_id: int) -> list[CharacterAccessibleStructure]:
        session = self.session_factory()
        try:
            character = session.scalar(select(EsiCharacter).where(EsiCharacter.character_id == character_id))
            if character is None:
                raise LookupError(f"Character {character_id} was not found.")
            access_token = self._ensure_valid_token(session, character)

            self._sync_character_assets(
                session,
                character=character,
                fetched_assets=self.esi_client.fetch_character_assets(access_token),
            )
            self._sync_character_orders(
                session,
                character=character,
                fetched_orders=self.esi_client.fetch_character_orders(access_token),
            )
            persisted_structures = self._persist_discovered_structures(
                session,
                character=character,
                discovered_structures=self._build_discovered_structure_inputs(
                    self.esi_client.fetch_accessible_structures(access_token)
                ),
            )

            sync_state = session.scalar(
                select(EsiCharacterSyncState).where(EsiCharacterSyncState.character_id == character.id)
            )
            if sync_state is None:
                sync_state = EsiCharacterSyncState(character_id=character.id)
                session.add(sync_state)

            # Resolve names for any unresolved structures in the locations table
            self._resolve_structure_names(session, access_token)

            sync_state.last_successful_sync = datetime.now(UTC)
            sync_state.assets_sync_status = "ok"
            sync_state.orders_sync_status = "ok"
            sync_state.structures_sync_status = "ok"
            session.commit()
            session.refresh(sync_state)
            return persisted_structures
        finally:
            session.close()

    def count_accessible_structures(self, character_id: int) -> int:
        """Return the total number of accessible structures for a character."""
        session = self.session_factory()
        try:
            character = session.scalar(select(EsiCharacter).where(EsiCharacter.character_id == character_id))
            if character is None:
                return 0
            return int(
                session.scalar(
                    select(func.count()).select_from(CharacterAccessibleStructure).where(
                        CharacterAccessibleStructure.character_id == character.id
                    )
                )
                or 0
            )
        finally:
            session.close()

    def discover_character_accessible_structures(
        self,
        character_id: int,
        discovered_structures: Iterable[DiscoveredStructureInput],
    ) -> list[CharacterAccessibleStructure]:
        session = self.session_factory()
        try:
            character = session.scalar(select(EsiCharacter).where(EsiCharacter.character_id == character_id))
            if character is None:
                raise LookupError(f"Character {character_id} was not found.")
            persisted_structures = self._persist_discovered_structures(
                session,
                character=character,
                discovered_structures=discovered_structures,
            )

            session.commit()
            for persisted_structure in persisted_structures:
                session.refresh(persisted_structure)
            return persisted_structures
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

    def _sync_character_assets(
        self,
        session: Session,
        *,
        character: EsiCharacter,
        fetched_assets: Iterable[EsiCharacterAssetRecord],
    ) -> None:
        session.query(CharacterAsset).filter(CharacterAsset.character_id == character.id).delete()

        resolved_item_ids = {
            type_id: item_id
            for type_id, item_id in session.execute(select(Item.type_id, Item.id)).all()
        }
        resolved_location_ids = {
            location_id: resolved_id
            for location_id, resolved_id in session.execute(select(Location.location_id, Location.id)).all()
        }
        # Aggregate duplicate (type_id, location_id) pairs — ESI returns individual
        # items (e.g., fitted modules) as separate entries.
        aggregated: dict[tuple[int, int | None], int] = {}
        for asset in fetched_assets:
            external_type_id = int(asset["type_id"])
            resolved_type_id = resolved_item_ids.get(external_type_id)
            if resolved_type_id is None:
                continue
            external_location_id = asset.get("location_id")
            key = (resolved_type_id, external_location_id)
            aggregated[key] = aggregated.get(key, 0) + max(int(asset["quantity"]), 0)

        for (resolved_type_id, external_location_id), quantity in aggregated.items():
            session.add(
                CharacterAsset(
                    character_id=character.id,
                    type_id=resolved_type_id,
                    quantity=quantity,
                    external_location_id=external_location_id,
                    resolved_location_id=resolved_location_ids.get(external_location_id) if external_location_id else None,
                    location_name=None,
                )
            )

    def _sync_character_orders(
        self,
        session: Session,
        *,
        character: EsiCharacter,
        fetched_orders: Iterable[EsiCharacterOrderRecord],
    ) -> None:
        session.query(CharacterOrder).filter(CharacterOrder.character_id == character.id).delete()

        resolved_item_ids = {
            type_id: item_id
            for type_id, item_id in session.execute(select(Item.type_id, Item.id)).all()
        }
        resolved_location_ids = {
            location_id: resolved_id
            for location_id, resolved_id in session.execute(select(Location.location_id, Location.id)).all()
        }
        for order in fetched_orders:
            external_type_id = int(order["type_id"])
            resolved_type_id = resolved_item_ids.get(external_type_id)
            if resolved_type_id is None:
                continue
            external_location_id = order.get("location_id")
            issued_raw = order.get("issued")
            issued_at = datetime.fromisoformat(issued_raw) if isinstance(issued_raw, str) else None
            price_raw = order.get("price")
            duration_raw = order.get("duration")
            session.add(
                CharacterOrder(
                    character_id=character.id,
                    order_id=int(order["order_id"]),
                    type_id=resolved_type_id,
                    volume_remain=max(int(order["volume_remain"]), 0),
                    is_buy_order=bool(order["is_buy_order"]),
                    price=float(price_raw) if price_raw is not None else None,
                    external_location_id=external_location_id,
                    resolved_location_id=resolved_location_ids.get(external_location_id) if external_location_id else None,
                    issued=issued_at,
                    duration=int(duration_raw) if duration_raw is not None else None,
                )
            )

    def _build_discovered_structure_inputs(
        self,
        structures: Iterable[EsiAccessibleStructureRecord],
    ) -> list[DiscoveredStructureInput]:
        now = datetime.now(UTC)
        return [
            DiscoveredStructureInput(
                structure_id=int(structure["structure_id"]),
                structure_name=str(structure["structure_name"]),
                system_name=str(structure["system_name"]) if structure.get("system_name") is not None else None,
                region_name=str(structure["region_name"]) if structure.get("region_name") is not None else None,
                access_verified_at=now,
                tracking_enabled=False,
                polling_tier=str(structure.get("polling_tier") or "user"),
                last_snapshot_at=now,
                confidence_score=float(structure.get("confidence_score") or 0.0),
            )
            for structure in structures
        ]

    def _persist_discovered_structures(
        self,
        session: Session,
        *,
        character: EsiCharacter,
        discovered_structures: Iterable[DiscoveredStructureInput],
    ) -> list[CharacterAccessibleStructure]:
        discovered_by_structure_id: dict[int, DiscoveredStructureInput] = {}
        for discovered_structure in discovered_structures:
            discovered_by_structure_id[discovered_structure.structure_id] = discovered_structure

        persisted_structures: list[CharacterAccessibleStructure] = []
        for structure_id in sorted(discovered_by_structure_id):
            discovered_structure = discovered_by_structure_id[structure_id]
            persisted_structure = session.scalar(
                select(CharacterAccessibleStructure).where(
                    CharacterAccessibleStructure.character_id == character.id,
                    CharacterAccessibleStructure.structure_id == structure_id,
                )
            )
            if persisted_structure is None:
                persisted_structure = CharacterAccessibleStructure(
                    character_id=character.id,
                    structure_id=structure_id,
                    structure_name=discovered_structure.structure_name,
                    system_name=discovered_structure.system_name,
                    region_name=discovered_structure.region_name,
                    access_verified_at=(
                        discovered_structure.access_verified_at
                        if discovered_structure.access_verified_at is not None
                        else datetime.now(UTC)
                    ),
                    tracking_enabled=discovered_structure.tracking_enabled,
                    polling_tier=discovered_structure.polling_tier,
                    last_snapshot_at=discovered_structure.last_snapshot_at,
                    confidence_score=discovered_structure.confidence_score,
                )
                session.add(persisted_structure)
            else:
                persisted_structure.structure_name = discovered_structure.structure_name
                persisted_structure.system_name = discovered_structure.system_name
                persisted_structure.region_name = discovered_structure.region_name
                if discovered_structure.access_verified_at is not None:
                    persisted_structure.access_verified_at = discovered_structure.access_verified_at
                persisted_structure.tracking_enabled = (
                    persisted_structure.tracking_enabled or discovered_structure.tracking_enabled
                )
                persisted_structure.polling_tier = discovered_structure.polling_tier
                persisted_structure.last_snapshot_at = discovered_structure.last_snapshot_at
                persisted_structure.confidence_score = discovered_structure.confidence_score

            self._upsert_structure_location_from_discovery(session, discovered_structure)
            persisted_structures.append(persisted_structure)

        for persisted_structure in persisted_structures:
            if persisted_structure.tracking_enabled:
                self._upsert_tracked_structure(session, character.id, persisted_structure)

        return persisted_structures

    def _upsert_structure_location_from_discovery(
        self,
        session: Session,
        discovered_structure: DiscoveredStructureInput,
    ) -> Location | None:
        system = self._resolve_system(session, discovered_structure.system_name, discovered_structure.region_name)
        if system is None:
            return None

        location = session.scalar(select(Location).where(Location.location_id == discovered_structure.structure_id))
        if location is None:
            location = Location(
                location_id=discovered_structure.structure_id,
                location_type="structure",
                system_id=system.id,
                region_id=system.region_id,
                name=discovered_structure.structure_name,
            )
            session.add(location)
            return location

        location.location_type = "structure"
        location.system_id = system.id
        location.region_id = system.region_id
        location.name = discovered_structure.structure_name
        return location

    def _resolve_structure_names(self, session: Session, access_token: str) -> int:
        """Resolve names for structures in the locations table that have placeholder names.

        Returns the number of structures successfully resolved.
        """
        import logging

        logger = logging.getLogger(__name__)

        unresolved = session.execute(
            select(Location.location_id).where(
                Location.location_type == "structure",
                Location.name.like("Structure %"),
            )
        ).scalars().all()

        if not unresolved:
            return 0

        logger.info("Resolving names for %d unresolved structures", len(unresolved))
        resolved_count = 0
        for structure_id in unresolved:
            info = self.esi_client.resolve_structure_info(access_token, structure_id)
            if info and info.get("name"):
                location = session.scalar(
                    select(Location).where(Location.location_id == structure_id)
                )
                if location:
                    location.name = info["name"]
                    resolved_count += 1

        if resolved_count:
            session.flush()
            logger.info("Resolved %d / %d structure names", resolved_count, len(unresolved))

        return resolved_count

    def _split_scopes(self, granted_scopes: str) -> list[str]:
        return granted_scopes.split() if granted_scopes else []

    def _upsert_tracked_structure(
        self,
        session: Session,
        character_db_id: int,
        structure: CharacterAccessibleStructure,
    ) -> None:
        system = self._resolve_system(session, structure.system_name, structure.region_name)
        if system is None:
            return

        location = session.scalar(select(Location).where(Location.location_id == structure.structure_id))
        if location is None:
            location = Location(
                location_id=structure.structure_id,
                location_type="structure",
                system_id=system.id,
                region_id=system.region_id,
                name=structure.structure_name,
            )
            session.add(location)
        else:
            location.location_type = "structure"
            location.system_id = system.id
            location.region_id = system.region_id
            location.name = structure.structure_name

        tracked_structure = session.scalar(
            select(TrackedStructure).where(TrackedStructure.structure_id == structure.structure_id)
        )
        if tracked_structure is None:
            tracked_structure = TrackedStructure(
                structure_id=structure.structure_id,
                name=structure.structure_name,
                system_id=system.id,
                region_id=system.region_id,
                tracking_tier=structure.polling_tier,
                poll_interval_minutes=self._poll_interval_minutes(structure.polling_tier),
                is_enabled=True,
                confidence_score=structure.confidence_score,
                discovered_by_character_id=character_db_id,
            )
            session.add(tracked_structure)
            return

        tracked_structure.name = structure.structure_name
        tracked_structure.system_id = system.id
        tracked_structure.region_id = system.region_id
        tracked_structure.tracking_tier = structure.polling_tier
        tracked_structure.poll_interval_minutes = self._poll_interval_minutes(structure.polling_tier)
        tracked_structure.is_enabled = True
        tracked_structure.confidence_score = structure.confidence_score
        tracked_structure.discovered_by_character_id = character_db_id

    def _resolve_system(
        self,
        session: Session,
        system_name: str | None,
        region_name: str | None,
    ) -> System | None:
        if system_name is None:
            return None

        statement = select(System).where(System.name == system_name)
        if region_name is not None:
            statement = statement.join(Region, Region.id == System.region_id).where(Region.name == region_name)

        return session.scalar(statement.order_by(System.id.asc()))

    @staticmethod
    def _poll_interval_minutes(polling_tier: str) -> int:
        return 10 if polling_tier == "core" else 30
