from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.all_models import CharacterAccessibleStructure, EsiCharacter, EsiCharacterSyncState, User
from app.services.characters.service import CharacterService


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def seed_character_data(session: Session) -> None:
    user = User(primary_character_id=None)
    session.add(user)
    session.flush()

    first_character = EsiCharacter(
        user_id=user.id,
        character_id=90000042,
        character_name="Audit Trader",
        corporation_name="Signal Cartel",
        granted_scopes="esi-assets.read_assets.v1 esi-markets.read_character_orders.v1",
        sync_enabled=True,
    )
    second_character = EsiCharacter(
        user_id=user.id,
        character_id=90000077,
        character_name="Alt Hauler",
        corporation_name="PushX",
        granted_scopes="esi-assets.read_assets.v1",
        sync_enabled=False,
    )
    session.add_all([first_character, second_character])
    session.flush()
    user.primary_character_id = first_character.id

    session.add(
        EsiCharacterSyncState(
            character_id=first_character.id,
            last_token_refresh=datetime(2026, 3, 21, 10, 0, tzinfo=UTC),
            last_successful_sync=datetime(2026, 3, 21, 10, 5, tzinfo=UTC),
            assets_sync_status="ok",
            orders_sync_status="stale",
            skills_sync_status="pending",
            structures_sync_status="ok",
        )
    )
    session.add_all(
        [
            CharacterAccessibleStructure(
                character_id=first_character.id,
                structure_id=1022734985679,
                structure_name="Perimeter Market Keepstar",
                system_name="Perimeter",
                region_name="The Forge",
                access_verified_at=datetime(2026, 3, 21, 9, 0, tzinfo=UTC),
                tracking_enabled=True,
                polling_tier="core",
                last_snapshot_at=datetime(2026, 3, 21, 9, 30, tzinfo=UTC),
                confidence_score=0.88,
            ),
            CharacterAccessibleStructure(
                character_id=first_character.id,
                structure_id=1022734985680,
                structure_name="Jita Freeport",
                system_name="Jita",
                region_name="The Forge",
                access_verified_at=datetime(2026, 3, 20, 9, 0, tzinfo=UTC),
                tracking_enabled=False,
                polling_tier="user",
                last_snapshot_at=None,
                confidence_score=0.42,
            ),
        ]
    )
    session.commit()


def test_list_characters_reads_persisted_rows_and_counts_structures() -> None:
    session = build_session()
    seed_character_data(session)
    service = CharacterService(session_factory=lambda: session)

    characters = service.list_characters()

    assert [character.id for character in characters] == [90000042, 90000077]
    assert characters[0].granted_scopes == [
        "esi-assets.read_assets.v1",
        "esi-markets.read_character_orders.v1",
    ]
    assert characters[0].assets_sync_status == "ok"
    assert characters[0].orders_sync_status == "stale"
    assert characters[0].accessible_structure_count == 2
    assert characters[1].sync_enabled is False
    assert characters[1].accessible_structure_count == 0
    assert characters[1].assets_sync_status == "pending"


def test_get_character_returns_persisted_detail_and_structures() -> None:
    session = build_session()
    seed_character_data(session)
    service = CharacterService(session_factory=lambda: session)

    detail = service.get_character(90000042)

    assert detail.id == 90000042
    assert detail.character_name == "Audit Trader"
    assert detail.sync_enabled is True
    assert detail.sync_toggles == {
        "assets": True,
        "orders": True,
        "skills": True,
        "structures": True,
    }
    assert detail.skills == []
    assert [structure.structure_name for structure in detail.structures] == [
        "Jita Freeport",
        "Perimeter Market Keepstar",
    ]
    assert detail.structures[1].tracking_enabled is True
    assert detail.structures[1].confidence_score == 0.88


def test_get_character_raises_for_missing_public_character_id() -> None:
    session = build_session()
    service = CharacterService(session_factory=lambda: session)

    with pytest.raises(LookupError, match="90000042"):
        service.get_character(90000042)


def test_update_character_sync_enabled_persists_and_list_reads_reflect_it() -> None:
    session = build_session()
    seed_character_data(session)
    service = CharacterService(session_factory=lambda: session)

    updated_character = service.update_character_sync_enabled(90000042, False)

    assert updated_character is not None
    assert updated_character.sync_enabled is False

    characters = service.list_characters()
    detail = service.get_character(90000042)

    assert characters[0].sync_enabled is False
    assert detail.sync_enabled is False
    assert detail.sync_toggles == {
        "assets": False,
        "orders": False,
        "skills": False,
        "structures": False,
    }


def test_update_character_sync_enabled_noop_payload_leaves_value_unchanged() -> None:
    session = build_session()
    seed_character_data(session)
    service = CharacterService(session_factory=lambda: session)

    updated_character = service.update_character_sync_enabled(90000042, None)

    assert updated_character is not None
    assert updated_character.sync_enabled is True
    assert service.list_characters()[0].sync_enabled is True


def test_update_character_sync_enabled_raises_none_for_missing_character() -> None:
    session = build_session()
    service = CharacterService(session_factory=lambda: session)

    assert service.update_character_sync_enabled(90000042, True) is None


def test_enable_character_structure_tracking_sets_flag_and_is_idempotent() -> None:
    session = build_session()
    seed_character_data(session)
    service = CharacterService(session_factory=lambda: session)

    tracked_structure = service.enable_character_structure_tracking(90000042, 1022734985680)
    assert tracked_structure.tracking_enabled is True

    tracked_structure_again = service.enable_character_structure_tracking(90000042, 1022734985680)
    assert tracked_structure_again.tracking_enabled is True

    detail = service.get_character(90000042)
    assert detail.structures[0].tracking_enabled is True


def test_enable_character_structure_tracking_raises_for_missing_character_or_structure() -> None:
    session = build_session()
    seed_character_data(session)
    service = CharacterService(session_factory=lambda: session)

    with pytest.raises(LookupError, match="90000099"):
        service.enable_character_structure_tracking(90000099, 1022734985680)

    with pytest.raises(LookupError, match="1022734985799"):
        service.enable_character_structure_tracking(90000042, 1022734985799)
