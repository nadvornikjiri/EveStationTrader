from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import (
    CharacterAccessibleStructure,
    EsiCharacter,
    EsiCharacterSyncState,
    Location,
    Region,
    System,
    TrackedStructure,
    User,
)
from app.services.characters.service import CharacterService, DiscoveredStructureInput
from tests.db_test_utils import build_test_session


def build_session() -> Session:
    return build_test_session()


def seed_character_data(session: Session) -> None:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    session.add_all(
        [
            System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9),
            System(system_id=30000144, region_id=region.id, name="Perimeter", security_status=0.9),
        ]
    )
    session.flush()

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

    tracked_location = session.scalar(select(Location).where(Location.location_id == 1022734985680))
    assert tracked_location is not None
    assert tracked_location.location_type == "structure"
    assert tracked_location.name == "Jita Freeport"

    tracked_structure_row = session.scalar(
        select(TrackedStructure).where(TrackedStructure.structure_id == 1022734985680)
    )
    assert tracked_structure_row is not None
    assert tracked_structure_row.is_enabled is True
    assert tracked_structure_row.tracking_tier == "user"
    assert tracked_structure_row.poll_interval_minutes == 30
    assert tracked_structure_row.discovered_by_character_id is not None


def test_enable_character_structure_tracking_raises_for_missing_character_or_structure() -> None:
    session = build_session()
    seed_character_data(session)
    service = CharacterService(session_factory=lambda: session)

    with pytest.raises(LookupError, match="90000099"):
        service.enable_character_structure_tracking(90000099, 1022734985680)

    with pytest.raises(LookupError, match="1022734985799"):
        service.enable_character_structure_tracking(90000042, 1022734985799)


def test_discover_character_accessible_structures_inserts_asset_only_rows() -> None:
    session = build_session()
    seed_character_data(session)
    service = CharacterService(session_factory=lambda: session)

    discovered = service.discover_character_accessible_structures(
        90000042,
        [
            DiscoveredStructureInput(
                structure_id=1022734985683,
                structure_name="Amarr Logistics Hub",
                system_name="Amarr",
                region_name="Domain",
                access_verified_at=datetime(2026, 3, 21, 12, 0, tzinfo=UTC),
                tracking_enabled=False,
                polling_tier="user",
                last_snapshot_at=datetime(2026, 3, 21, 11, 30, tzinfo=UTC),
                confidence_score=0.55,
            )
        ],
    )

    assert len(discovered) == 1
    assert discovered[0].structure_id == 1022734985683
    assert discovered[0].structure_name == "Amarr Logistics Hub"

    rows = session.scalars(select(CharacterAccessibleStructure).order_by(CharacterAccessibleStructure.structure_id)).all()
    assert [row.structure_id for row in rows] == [1022734985679, 1022734985680, 1022734985683]
    assert rows[-1].tracking_enabled is False
    assert rows[-1].confidence_score == 0.55


def test_discover_character_accessible_structures_deduplicates_combined_inputs() -> None:
    session = build_session()
    seed_character_data(session)
    service = CharacterService(session_factory=lambda: session)

    discovered = service.discover_character_accessible_structures(
        90000042,
        [
            DiscoveredStructureInput(
                structure_id=1022734985684,
                structure_name="Duplicate Alpha",
                system_name="Jita",
                region_name="The Forge",
                access_verified_at=datetime(2026, 3, 21, 12, 0, tzinfo=UTC),
                polling_tier="core",
                confidence_score=0.2,
            ),
            DiscoveredStructureInput(
                structure_id=1022734985684,
                structure_name="Duplicate Beta",
                system_name="Perimeter",
                region_name="The Forge",
                access_verified_at=datetime(2026, 3, 21, 13, 0, tzinfo=UTC),
                polling_tier="user",
                confidence_score=0.7,
            ),
        ],
    )

    assert len(discovered) == 1
    assert discovered[0].structure_name == "Duplicate Beta"
    assert discovered[0].system_name == "Perimeter"

    rows = session.scalars(select(CharacterAccessibleStructure).where(CharacterAccessibleStructure.structure_id == 1022734985684)).all()
    assert len(rows) == 1
    assert rows[0].structure_name == "Duplicate Beta"
    assert rows[0].system_name == "Perimeter"
    assert rows[0].confidence_score == 0.7


def test_discover_character_accessible_structures_updates_existing_rows_without_clearing_tracking() -> None:
    session = build_session()
    seed_character_data(session)
    service = CharacterService(session_factory=lambda: session)

    discovered = service.discover_character_accessible_structures(
        90000042,
        [
            DiscoveredStructureInput(
                structure_id=1022734985679,
                structure_name="Perimeter Market Keepstar Updated",
                system_name="Perimeter",
                region_name="The Forge",
                access_verified_at=datetime(2026, 3, 21, 14, 0, tzinfo=UTC),
                tracking_enabled=False,
                polling_tier="secondary",
                last_snapshot_at=datetime(2026, 3, 21, 13, 45, tzinfo=UTC),
                confidence_score=0.91,
            )
        ],
    )

    assert len(discovered) == 1
    assert discovered[0].structure_name == "Perimeter Market Keepstar Updated"
    assert discovered[0].tracking_enabled is True

    row = session.scalar(
        select(CharacterAccessibleStructure).where(CharacterAccessibleStructure.structure_id == 1022734985679)
    )
    assert row is not None
    assert row.structure_name == "Perimeter Market Keepstar Updated"
    assert row.tracking_enabled is True
    assert row.confidence_score == 0.91
    assert row.access_verified_at == datetime(2026, 3, 21, 14, 0, tzinfo=UTC)

    tracked_structure = session.scalar(
        select(TrackedStructure).where(TrackedStructure.structure_id == 1022734985679)
    )
    assert tracked_structure is not None
    assert tracked_structure.name == "Perimeter Market Keepstar Updated"
    assert tracked_structure.tracking_tier == "secondary"
    assert tracked_structure.poll_interval_minutes == 30

    tracked_location = session.scalar(select(Location).where(Location.location_id == 1022734985679))
    assert tracked_location is not None
    assert tracked_location.name == "Perimeter Market Keepstar Updated"


def test_discover_character_accessible_structures_raises_for_missing_character() -> None:
    session = build_session()
    service = CharacterService(session_factory=lambda: session)

    with pytest.raises(LookupError, match="90000042"):
        service.discover_character_accessible_structures(
            90000042,
            [
                DiscoveredStructureInput(
                    structure_id=1022734985685,
                    structure_name="Missing Character Hub",
                    system_name="Jita",
                    region_name="The Forge",
                )
            ],
        )


def test_sync_character_persists_discovery_and_updates_sync_state() -> None:
    session = build_session()
    seed_character_data(session)
    service = CharacterService(session_factory=lambda: session)

    character = session.scalar(select(EsiCharacter).where(EsiCharacter.character_id == 90000042))
    assert character is not None

    before = session.scalar(select(EsiCharacterSyncState).where(EsiCharacterSyncState.character_id == character.id))
    assert before is not None
    before_last_successful_sync = before.last_successful_sync

    discovered = service.sync_character(90000042)

    assert len(discovered) == 3
    rows = session.scalars(select(CharacterAccessibleStructure).order_by(CharacterAccessibleStructure.structure_id)).all()
    assert [row.structure_id for row in rows] == [1022734985679, 1022734985680, 1022734985687]
    assert rows[0].tracking_enabled is True
    assert rows[-1].tracking_enabled is False

    sync_state = session.scalar(select(EsiCharacterSyncState).where(EsiCharacterSyncState.character_id == character.id))
    assert sync_state is not None
    assert sync_state.structures_sync_status == "ok"
    assert sync_state.last_successful_sync is not None
    assert sync_state.last_successful_sync != before_last_successful_sync


def test_sync_character_is_idempotent_and_raises_for_missing_character() -> None:
    session = build_session()
    seed_character_data(session)
    service = CharacterService(session_factory=lambda: session)

    character = session.scalar(select(EsiCharacter).where(EsiCharacter.character_id == 90000042))
    assert character is not None

    first = service.sync_character(90000042)
    second = service.sync_character(90000042)

    assert len(first) == 3
    assert len(second) == 3

    rows = session.scalars(select(CharacterAccessibleStructure).order_by(CharacterAccessibleStructure.structure_id)).all()
    assert [row.structure_id for row in rows] == [1022734985679, 1022734985680, 1022734985687]

    with pytest.raises(LookupError, match="90000099"):
        service.sync_character(90000099)
