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
    response = client.get("/api/characters")
    assert response.status_code == 200
    assert response.json()[0]["character_name"] == "Demo Trader"


def test_get_settings(client) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["default_analysis_period_days"] == 14


def test_get_auth_me(client) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["character_name"] == "Demo Trader"
