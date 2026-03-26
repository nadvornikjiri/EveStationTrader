from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.auth import CurrentUser
from app.db.session import SessionLocal
from app.models.all_models import EsiCharacter, EsiCharacterSyncState, EsiCharacterToken, SyncJobRun, User
from app.services.esi.client import EsiClient


class SsoCapableEsiClient(Protocol):
    def exchange_code(self, code: str) -> dict: ...

    def fetch_character_identity(self, access_token: str) -> dict: ...


class AuthService:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        esi_client: SsoCapableEsiClient | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.esi_client = esi_client or EsiClient()

    def handle_callback(self, code: str) -> CurrentUser:
        token_payload = self.esi_client.exchange_code(code)
        identity = self.esi_client.fetch_character_identity(token_payload["access_token"])
        expires_at = datetime.fromisoformat(token_payload["expires_at"])
        scopes = token_payload.get("scopes", [])
        granted_scopes = " ".join(scopes) if isinstance(scopes, list) else str(scopes)

        session = self.session_factory()
        try:
            character = session.scalar(
                select(EsiCharacter).where(EsiCharacter.character_id == identity["character_id"])
            )
            user: User | None
            if character is None:
                # Single-user MVP assumption: any additional EVE SSO character links to the first user row.
                user = session.scalar(select(User).order_by(User.id.asc()))
                if user is None:
                    user = User(primary_character_id=None)
                    session.add(user)
                    session.flush()
                character = EsiCharacter(
                    user_id=user.id,
                    character_id=identity["character_id"],
                    character_name=identity["character_name"],
                    corporation_name=identity.get("corporation_name"),
                    granted_scopes=granted_scopes,
                )
                session.add(character)
                session.flush()
            else:
                user = session.get(User, character.user_id)
                if user is None:
                    raise ValueError("existing character is missing user")
                character.character_name = identity["character_name"]
                character.corporation_name = identity.get("corporation_name")
                character.granted_scopes = granted_scopes

            token = session.scalar(
                select(EsiCharacterToken).where(EsiCharacterToken.character_id == character.id)
            )
            if token is None:
                token = EsiCharacterToken(
                    character_id=character.id,
                    access_token=token_payload["access_token"],
                    refresh_token=token_payload["refresh_token"],
                    expires_at=expires_at,
                )
                session.add(token)
            else:
                token.access_token = token_payload["access_token"]
                token.refresh_token = token_payload["refresh_token"]
                token.expires_at = expires_at

            sync_state = session.scalar(
                select(EsiCharacterSyncState).where(EsiCharacterSyncState.character_id == character.id)
            )
            is_new_sync_state = sync_state is None
            if sync_state is None:
                session.add(EsiCharacterSyncState(character_id=character.id))

            # Enqueue initial sync job for newly connected characters
            if is_new_sync_state:
                session.add(
                    SyncJobRun(
                        job_type="character_sync",
                        status="pending",
                        triggered_by="sso_connect",
                        target_type="character",
                        target_id=str(character.character_id),
                        message=f"Initial sync for {character.character_name}",
                    )
                )

            if user.primary_character_id is None:
                user.primary_character_id = character.id

            primary_character_id = character.character_id
            if user.primary_character_id is not None:
                primary_character = session.get(EsiCharacter, user.primary_character_id)
                if primary_character is not None:
                    primary_character_id = primary_character.character_id

            session.commit()
            return CurrentUser(
                id=user.id,
                primary_character_id=primary_character_id,
                character_name=character.character_name,
                is_authenticated=True,
            )
        finally:
            session.close()

    def get_current_user(self) -> CurrentUser:
        session = self.session_factory()
        try:
            user = session.scalar(select(User).order_by(User.id.asc()))
            if user is None:
                return CurrentUser(
                    id=1,
                    primary_character_id=90000001,
                    character_name="Demo Trader",
                    is_authenticated=False,
                )

            character_name = None
            primary_character_id = None
            if user.primary_character_id is not None:
                character = session.get(EsiCharacter, user.primary_character_id)
                if character is not None:
                    character_name = character.character_name
                    primary_character_id = character.character_id

            return CurrentUser(
                id=user.id,
                primary_character_id=primary_character_id,
                character_name=character_name,
                is_authenticated=True,
            )
        finally:
            session.close()
