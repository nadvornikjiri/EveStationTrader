from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.all_models import EsiCharacter, EsiCharacterSyncState, EsiCharacterToken, User
from app.services.auth.service import AuthService


class MockEsiClient:
    def __init__(self) -> None:
        self.token_payload = {
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "scopes": ["esi-assets.read_assets.v1", "esi-markets.read_character_orders.v1"],
        }
        self.identity_payload = {
            "character_id": 90000042,
            "character_name": "Audit Trader",
            "corporation_name": "Signal Cartel",
        }

    def exchange_code(self, code: str) -> dict:
        assert code
        return self.token_payload

    def fetch_character_identity(self, access_token: str) -> dict:
        assert access_token == self.token_payload["access_token"]
        return self.identity_payload


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_handle_callback_creates_initial_user_character_token_and_sync_state() -> None:
    session = build_session()
    service = AuthService(session_factory=lambda: session, esi_client=MockEsiClient())

    current_user = service.handle_callback("first-code")

    users = session.scalars(select(User)).all()
    characters = session.scalars(select(EsiCharacter)).all()
    tokens = session.scalars(select(EsiCharacterToken)).all()
    sync_states = session.scalars(select(EsiCharacterSyncState)).all()

    assert current_user.is_authenticated is True
    assert current_user.primary_character_id == 90000042
    assert len(users) == 1
    assert len(characters) == 1
    assert len(tokens) == 1
    assert len(sync_states) == 1
    assert characters[0].user_id == users[0].id
    assert users[0].primary_character_id == characters[0].id
    assert tokens[0].access_token == "access-1"


def test_handle_callback_updates_existing_character_and_token_without_duplicates() -> None:
    session = build_session()
    client = MockEsiClient()
    service = AuthService(session_factory=lambda: session, esi_client=client)
    first = service.handle_callback("first-code")

    client.token_payload = {
        "access_token": "access-2",
        "refresh_token": "refresh-2",
        "expires_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
        "scopes": ["esi-wallet.read_character_wallet.v1"],
    }
    client.identity_payload = {
        "character_id": 90000042,
        "character_name": "Audit Trader Updated",
        "corporation_name": "Brave Collective",
    }

    second = service.handle_callback("second-code")

    users = session.scalars(select(User)).all()
    characters = session.scalars(select(EsiCharacter)).all()
    tokens = session.scalars(select(EsiCharacterToken)).all()
    sync_states = session.scalars(select(EsiCharacterSyncState)).all()

    assert first.primary_character_id == second.primary_character_id
    assert len(users) == 1
    assert len(characters) == 1
    assert len(tokens) == 1
    assert len(sync_states) == 1
    assert characters[0].character_name == "Audit Trader Updated"
    assert characters[0].corporation_name == "Brave Collective"
    assert characters[0].granted_scopes == "esi-wallet.read_character_wallet.v1"
    assert tokens[0].access_token == "access-2"
    assert tokens[0].refresh_token == "refresh-2"
