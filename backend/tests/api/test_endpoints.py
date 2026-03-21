from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.all_models import CharacterAccessibleStructure, EsiCharacter, EsiCharacterSyncState, User


def test_get_targets(client) -> None:
    response = client.get("/api/targets")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_get_sources(client) -> None:
    response = client.get("/api/sources", params={"target_location_id": 60003760})
    assert response.status_code == 200
    assert response.json()[0]["location_type"] == "npc_station"


def test_get_source_summaries(client) -> None:
    response = client.get("/api/opportunities/source-summaries", params={"target_location_id": 60003760})
    assert response.status_code == 200
    assert response.json()[0]["source_market_name"]


def test_get_items(client) -> None:
    response = client.get(
        "/api/opportunities/items",
        params={"target_location_id": 60003760, "source_location_id": 60008494},
    )
    assert response.status_code == 200
    assert response.json()[0]["item_name"] == "Tritanium"


def test_get_sync_status(client) -> None:
    response = client.get("/api/sync/status")
    assert response.status_code == 200
    assert response.json()[0]["label"]


def test_run_foundation_seed_sync(client) -> None:
    response = client.post("/api/sync/run/foundation_seed_sync")
    assert response.status_code == 200
    assert "Seeded foundation data" in response.json()["message"]


def test_get_characters(client) -> None:
    session = SessionLocal()
    try:
        session.execute(delete(CharacterAccessibleStructure))
        session.execute(delete(EsiCharacterSyncState))
        session.execute(delete(EsiCharacter))
        session.execute(delete(User))

        user = User(primary_character_id=None)
        session.add(user)
        session.flush()
        character = EsiCharacter(
            user_id=user.id,
            character_id=90000042,
            character_name="Audit Trader",
            corporation_name="Signal Cartel",
            granted_scopes="esi-assets.read_assets.v1",
            sync_enabled=True,
        )
        session.add(character)
        session.flush()
        user.primary_character_id = character.id
        session.add(
            EsiCharacterSyncState(
                character_id=character.id,
                assets_sync_status="ok",
                orders_sync_status="ok",
                skills_sync_status="pending",
                structures_sync_status="ok",
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get("/api/characters")
    assert response.status_code == 200
    assert response.json()[0]["character_name"] == "Audit Trader"


def test_get_character_returns_404_for_unknown_character(client) -> None:
    response = client.get("/api/characters/99999999")
    assert response.status_code == 404


def test_get_settings(client) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["default_analysis_period_days"] == 14


def test_get_auth_me(client) -> None:
    session = SessionLocal()
    try:
        session.execute(delete(CharacterAccessibleStructure))
        session.execute(delete(EsiCharacterSyncState))
        session.execute(delete(EsiCharacter))
        session.execute(delete(User))
        session.commit()
    finally:
        session.close()

    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["character_name"] == "Demo Trader"
