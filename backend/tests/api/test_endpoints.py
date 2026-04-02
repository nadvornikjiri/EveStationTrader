from datetime import UTC, datetime


from sqlalchemy import delete, insert, select, update

from app.api.schemas.sync import SyncJobRunResponse
from app.core.security import build_esi_scopes
from app.db.session import SessionLocal
from app.models.all_models import (
    AdamMarketOrdersTradeRaw,
    CharacterAccessibleStructure,
    EsiCharacter,
    EsiCharacterSyncState,
    EsiCharacterToken,
    Item,
    Location,
    OpportunityItem,
    OpportunitySourceSummary,
    SyncJobRun,
    TrackedStructure,
    UserSetting,
    User,
)


def reset_character_tables() -> None:
    session = SessionLocal()
    try:
        session.execute(update(User).values(primary_character_id=None))
        session.execute(delete(CharacterAccessibleStructure))
        session.execute(delete(EsiCharacterSyncState))
        session.execute(delete(EsiCharacterToken))
        session.execute(delete(TrackedStructure))
        session.execute(delete(EsiCharacter))
        session.execute(delete(User))
        session.commit()
    finally:
        session.close()


def seed_trade_opportunity_rows() -> None:
    session = SessionLocal()
    try:
        target_location = session.scalar(select(Location).where(Location.location_id == 60003760))
        source_location = session.scalar(select(Location).where(Location.location_id == 60008494))
        item = session.scalar(select(Item).where(Item.type_id == 34))
        if target_location is None or source_location is None or item is None:
            raise AssertionError("Expected seeded trade entities to exist in the test database.")

        session.execute(
            delete(OpportunityItem).where(
                OpportunityItem.target_location_id == target_location.id,
                OpportunityItem.source_location_id == source_location.id,
                OpportunityItem.period_days == 14,
            )
        )
        session.execute(
            delete(OpportunitySourceSummary).where(
                OpportunitySourceSummary.target_location_id == target_location.id,
                OpportunitySourceSummary.source_location_id == source_location.id,
                OpportunitySourceSummary.period_days == 14,
            )
        )
        session.add(
            OpportunitySourceSummary(
                target_location_id=target_location.id,
                source_location_id=source_location.id,
                source_security_status=1.0,
                period_days=14,
                purchase_units_total=20.0,
                source_units_available_total=40.0,
                target_demand_day_total=15.0,
                target_supply_units_total=30.0,
                target_dos_weighted=2.0,
                in_transit_units=1.0,
                assets_units=2.0,
                active_sell_orders_units=3.0,
                source_avg_price_weighted=100.0,
                target_now_price_weighted=120.0,
                target_period_avg_price_weighted=125.0,
                target_now_profit_weighted=12.0,
                target_period_profit_weighted=15.0,
                capital_required_total=1500.0,
                roi_now_weighted=0.12,
                roi_period_weighted=0.15,
                total_item_volume_m3=5.0,
                shipping_cost_total=20.0,
                demand_source_summary="adam4eve",
                computed_at=datetime(2026, 3, 20, tzinfo=UTC),
            )
        )
        session.add(
            OpportunityItem(
                target_location_id=target_location.id,
                source_location_id=source_location.id,
                type_id=item.id,
                period_days=14,
                purchase_units=10.0,
                source_units_available=25.0,
                target_demand_day=12.0,
                target_supply_units=24.0,
                target_dos=2.0,
                in_transit_units=1.0,
                assets_units=2.0,
                active_sell_orders_units=3.0,
                source_station_sell_price=100.0,
                target_station_sell_price=125.0,
                target_period_avg_price=130.0,
                target_now_profit=16.75,
                target_period_profit=21.4,
                capital_required=1200.0,
                roi_now=0.1675,
                roi_period=0.214,
                source_security_status=1.0,
                item_volume_m3=0.01,
                shipping_cost=15.0,
                demand_source="adam4eve",
                computed_at=datetime(2026, 3, 20, tzinfo=UTC),
            )
        )
        session.commit()
    finally:
        session.close()


def seed_database_browser_items() -> None:
    session = SessionLocal()
    try:
        if session.scalar(select(Item).where(Item.type_id == 35)) is None:
            session.add(
                Item(
                    type_id=35,
                    name="Pyerite",
                    volume_m3=0.01,
                    group_name="Mineral",
                    category_name="Material",
                )
            )
        if session.scalar(select(Item).where(Item.type_id == 36)) is None:
            session.add(
                Item(
                    type_id=36,
                    name="Mexallon",
                    volume_m3=0.01,
                    group_name="Mineral",
                    category_name="Material",
                )
            )
        session.commit()
    finally:
        session.close()


def test_get_targets(client) -> None:
    response = client.get("/api/targets")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_get_target_options(client) -> None:
    response = client.get("/api/targets/options")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_get_sources(client) -> None:
    seed_trade_opportunity_rows()
    response = client.get("/api/sources", params={"target_location_id": 60003760})
    assert response.status_code == 200
    assert response.json() == [
        {
            "location_id": 60008494,
            "location_type": "npc_station",
            "name": "Amarr VIII (Oris) - Emperor Family Academy",
            "region_name": "Domain",
            "system_name": "Amarr",
        }
    ]


def test_get_source_summaries(client) -> None:
    seed_trade_opportunity_rows()
    response = client.get("/api/opportunities/source-summaries", params={"target_location_id": 60003760})
    assert response.status_code == 200
    assert response.json()[0]["source_market_name"]


def test_post_refresh_trade_opportunities(client, monkeypatch) -> None:
    from app.repositories.trade_repository import TradeRepository

    refresh_calls: list[tuple[int, int]] = []

    def fake_refresh(self, target_location_id: int, period_days: int, **_: object) -> None:
        refresh_calls.append((target_location_id, period_days))

    monkeypatch.setattr(TradeRepository, "refresh_opportunities", fake_refresh)
    monkeypatch.setattr(
        TradeRepository,
        "get_last_refresh",
        lambda self: datetime(2026, 3, 30, 12, 0, tzinfo=UTC),
    )

    response = client.post("/api/opportunities/refresh", params={"target_location_id": 60003760, "period_days": 14})

    assert response.status_code == 200
    assert refresh_calls == [(60003760, 14)]
    assert response.json()["last_refresh_at"] == "2026-03-30T12:00:00Z"


def test_get_items(client) -> None:
    seed_trade_opportunity_rows()
    response = client.get(
        "/api/opportunities/items",
        params={"target_location_id": 60003760, "source_location_id": 60008494},
    )
    assert response.status_code == 200
    assert response.json()[0]["item_name"] == "Tritanium"


def test_get_target_items(client) -> None:
    seed_trade_opportunity_rows()
    session = SessionLocal()
    try:
        source_location = session.scalar(select(Location).where(Location.location_id == 60008494))
        assert source_location is not None
        expected_source_location_id = source_location.id
    finally:
        session.close()

    response = client.get(
        "/api/opportunities/target-items",
        params={"target_location_id": 60003760},
    )
    assert response.status_code == 200
    assert response.json()[0]["item_name"] == "Tritanium"
    assert response.json()[0]["source_location_id"] == expected_source_location_id


def test_get_source_summaries_passes_trade_filters(client, monkeypatch) -> None:
    from app.repositories.trade_repository import TradeRepository

    captured: dict[str, object] = {}

    def fake_list_source_summaries(self, target_location_id: int, period_days: int, **filters: object) -> list[dict[str, object]]:
        captured["target_location_id"] = target_location_id
        captured["period_days"] = period_days
        captured["filters"] = filters
        return []

    monkeypatch.setattr(TradeRepository, "list_source_summaries", fake_list_source_summaries)

    response = client.get(
        "/api/opportunities/source-summaries",
        params={
            "target_location_id": 60003760,
            "period_days": 14,
            "item_search": "trit",
            "min_profit": 15000000,
            "min_roi_now_pct": 20,
            "min_demand_day": 2.5,
            "max_dos": 7.5,
            "source_type": "npc",
            "min_security": "highsec",
            "demand_source": "adam4eve",
        },
    )

    assert response.status_code == 200
    assert captured == {
        "target_location_id": 60003760,
        "period_days": 14,
        "filters": {
            "item_search": "trit",
            "min_profit": 15000000.0,
            "min_roi_now_pct": 20.0,
            "min_demand_day": 2.5,
            "max_dos": 7.5,
            "source_type": "npc",
            "min_security": "highsec",
            "demand_source": "adam4eve",
        },
    }


def test_get_items_passes_trade_filters(client, monkeypatch) -> None:
    from app.repositories.trade_repository import TradeRepository

    captured: dict[str, object] = {}

    def fake_list_items(
        self,
        target_location_id: int,
        source_location_id: int,
        period_days: int,
        **filters: object,
    ) -> list[dict[str, object]]:
        captured["target_location_id"] = target_location_id
        captured["source_location_id"] = source_location_id
        captured["period_days"] = period_days
        captured["filters"] = filters
        return []

    monkeypatch.setattr(TradeRepository, "list_items", fake_list_items)

    response = client.get(
        "/api/opportunities/items",
        params={
            "target_location_id": 60003760,
            "source_location_id": 60008494,
            "period_days": 14,
            "item_search": "trit",
            "min_profit": 15000000,
            "min_roi_now_pct": 20,
            "min_demand_day": 2.5,
            "max_dos": 7.5,
            "source_type": "npc",
            "min_security": "highsec",
            "demand_source": "adam4eve",
        },
    )

    assert response.status_code == 200
    assert captured == {
        "target_location_id": 60003760,
        "source_location_id": 60008494,
        "period_days": 14,
        "filters": {
            "item_search": "trit",
            "min_profit": 15000000.0,
            "min_roi_now_pct": 20.0,
            "min_demand_day": 2.5,
            "max_dos": 7.5,
            "source_type": "npc",
            "min_security": "highsec",
            "demand_source": "adam4eve",
        },
    }


def test_get_opportunity_lists_return_empty_when_no_computed_rows_exist(client) -> None:
    sources_response = client.get(
        "/api/sources",
        params={"target_location_id": 60003760, "period_days": 999},
    )
    assert sources_response.status_code == 200
    assert sources_response.json() == []

    summary_response = client.get(
        "/api/opportunities/source-summaries",
        params={"target_location_id": 60003760, "period_days": 999},
    )
    assert summary_response.status_code == 200
    assert summary_response.json() == []

    item_response = client.get(
        "/api/opportunities/items",
        params={"target_location_id": 60003760, "source_location_id": 60008494, "period_days": 999},
    )
    assert item_response.status_code == 200
    assert item_response.json() == []

    target_item_response = client.get(
        "/api/opportunities/target-items",
        params={"target_location_id": 60003760, "period_days": 999},
    )
    assert target_item_response.status_code == 200
    assert target_item_response.json() == []


def test_get_sync_status(client) -> None:
    response = client.get("/api/sync/status")
    assert response.status_code == 200
    assert response.json()[0]["label"]


def test_get_sync_jobs_includes_progress_fields(client) -> None:
    session = SessionLocal()
    try:
        session.execute(delete(SyncJobRun))
        session.add(
            SyncJobRun(
                job_type="esi_market_orders_sync",
                status="running",
                records_processed=60,
                progress_phase="Processing downloaded ESI market orders",
                progress_current=60,
                progress_total=100,
                progress_unit="downloaded records",
                message="Processed 60 / 100 downloaded ESI market orders.",
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get("/api/sync/jobs")
    assert response.status_code == 200
    assert response.json()[0]["progress_phase"] == "Processing downloaded ESI market orders"
    assert response.json()[0]["progress_current"] == 60
    assert response.json()[0]["progress_total"] == 100
    assert response.json()[0]["progress_unit"] == "downloaded records"


def test_get_database_tables(client) -> None:
    response = client.get("/api/database/tables")
    assert response.status_code == 200
    assert any(row["name"] == "items" for row in response.json())


def test_get_database_table_rows(client) -> None:
    response = client.get("/api/database/tables/items")
    assert response.status_code == 200
    payload = response.json()
    assert payload["table_name"] == "items"
    assert "name" in payload["columns"]
    assert isinstance(payload["rows"], list)
    assert payload["filtered_row_count"] <= payload["row_count"]
    assert payload["page"] == 1
    assert payload["page_size"] == 50
    assert payload["total_pages"] >= 1
    assert payload["sort_column"]


def test_get_database_table_rows_supports_filtering(client) -> None:
    seed_database_browser_items()
    response = client.get(
        "/api/database/tables/items",
        params={
            "filter_text": "py",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["table_name"] == "items"
    assert payload["filter_text"] == "py"
    assert payload["filtered_row_count"] >= 1
    assert all("py" in row["name"].lower() for row in payload["rows"])


def test_get_database_table_rows_supports_per_column_filtering(client) -> None:
    seed_database_browser_items()
    response = client.get(
        "/api/database/tables/items",
        params={
            "filter_name": "mex",
            "filter_type_id": "36",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["table_name"] == "items"
    assert payload["filtered_row_count"] == 1
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["name"] == "Mexallon"
    assert payload["rows"][0]["type_id"] == 36


def test_get_database_table_rows_supports_absolute_sort_and_pagination(client) -> None:
    seed_database_browser_items()
    response = client.get(
        "/api/database/tables/items",
        params={
            "sort_column": "name",
            "sort_direction": "asc",
            "page_size": 1,
            "page": 2,
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["table_name"] == "items"
    assert payload["sort_column"] == "name"
    assert payload["sort_direction"] == "asc"
    assert payload["page_size"] == 1
    assert payload["page"] == 2
    assert payload["filtered_row_count"] >= 2
    assert payload["total_pages"] >= 2
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["name"] == "Pyerite"


def test_get_database_table_rows_enriches_adam_demand_references(client) -> None:
    session = SessionLocal()
    try:
        location = session.scalar(select(Location).where(Location.location_id == 60003760))
        item = session.scalar(select(Item).where(Item.type_id == 34))
        if location is None or item is None:
            raise AssertionError("Expected seeded location and item to exist.")

        session.execute(delete(AdamMarketOrdersTradeRaw))
        session.execute(
            insert(AdamMarketOrdersTradeRaw).values(
                location_id=location.location_id,
                region_id=10000002,
                type_id=item.type_id,
                is_buy_order=0,
                has_gone=0,
                scanDate=datetime(2026, 3, 26, tzinfo=UTC).date(),
                amount=12.5,
                high=5.0,
                low=5.0,
                avg=5.0,
                orderNum=1,
                iskValue=62.5,
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get("/api/database/tables/adam_market_orders_trade_raw")
    assert response.status_code == 200
    payload = response.json()
    assert payload["table_name"] == "adam_market_orders_trade_raw"
    assert "location_eve_id" in payload["columns"]
    assert "location_name" in payload["columns"]
    assert "type_eve_id" in payload["columns"]
    assert "item_name" in payload["columns"]
    assert any(
        row["location_eve_id"] == 60003760 and row["type_eve_id"] == 34 and row["item_name"]
        for row in payload["rows"]
    )


def test_run_foundation_import_sync(client) -> None:
    response = client.post("/api/sync/run/foundation_import_sync")
    assert response.status_code == 200
    assert response.json()["job_type"] == "foundation_import_sync"


def test_clear_opportunity_rebuild_data(client) -> None:
    seed_trade_opportunity_rows()

    response = client.post("/api/sync/clear/opportunity_rebuild")

    assert response.status_code == 200
    assert response.json()["job_type"] == "opportunity_rebuild"
    assert response.json()["records_deleted"] >= 2

    session = SessionLocal()
    try:
        assert session.scalars(select(OpportunityItem)).all() == []
        assert session.scalars(select(OpportunitySourceSummary)).all() == []
    finally:
        session.close()


def test_run_sync_returns_failed_job_payload_when_job_fails_immediately(client, monkeypatch) -> None:
    from app.services.sync.service import SyncService

    def fail_job(self, job_type: str) -> SyncJobRunResponse:
        return SyncJobRunResponse(
            id=999,
            started_at=datetime(2026, 3, 23, 12, 0, tzinfo=UTC),
            finished_at=datetime(2026, 3, 23, 12, 0, 1, tzinfo=UTC),
            job_type=job_type,
            status="failed",
            duration_ms=1000,
            records_processed=0,
            target_type="manual",
            target_id=None,
            message=f"Failed {job_type}.",
            error_details="Synthetic immediate failure for API coverage.",
        )

    monkeypatch.setattr(SyncService, "enqueue_job", fail_job)

    response = client.post("/api/sync/run/foundation_import_sync")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error_details"] == "Synthetic immediate failure for API coverage."


def test_cancel_unknown_sync_job_returns_404(client) -> None:
    response = client.post("/api/sync/cancel/999999")
    assert response.status_code == 404


def test_get_characters(client) -> None:
    reset_character_tables()
    session = SessionLocal()
    try:
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


def test_patch_character_updates_sync_enabled(client) -> None:
    reset_character_tables()
    session = SessionLocal()
    try:
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
        session.commit()
    finally:
        session.close()

    response = client.patch("/api/characters/90000042", json={"sync_enabled": False})
    assert response.status_code == 200
    assert response.json()["message"] == "Sync for character 90000042 is now disabled."

    session = SessionLocal()
    try:
        persisted_character: EsiCharacter | None = session.scalar(
            select(EsiCharacter).where(EsiCharacter.character_id == 90000042)
        )
        assert persisted_character is not None
        assert persisted_character.sync_enabled is False
    finally:
        session.close()

    detail = client.get("/api/characters/90000042")
    assert detail.json()["sync_enabled"] is False
    assert detail.json()["sync_toggles"]["assets"] is False


def test_patch_character_noop_payload_is_stable(client) -> None:
    reset_character_tables()
    session = SessionLocal()
    try:
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
        session.commit()
    finally:
        session.close()

    response = client.patch("/api/characters/90000042", json={})
    assert response.status_code == 200
    assert response.json()["message"] == "No changes applied to character 90000042."


def test_patch_character_returns_404_for_unknown_character(client) -> None:
    response = client.patch("/api/characters/99999999", json={"sync_enabled": False})
    assert response.status_code == 404


def test_track_character_structure_updates_accessible_structure(client) -> None:
    reset_character_tables()
    session = SessionLocal()
    try:
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
            CharacterAccessibleStructure(
                character_id=character.id,
                structure_id=1022734985680,
                structure_name="Jita Freeport",
                system_name="Jita",
                region_name="The Forge",
                access_verified_at=datetime(2026, 3, 21, 11, 0, tzinfo=UTC),
                tracking_enabled=False,
                polling_tier="user",
                last_snapshot_at=None,
                confidence_score=0.42,
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.post("/api/characters/90000042/structures/1022734985680/track")
    assert response.status_code == 200
    assert response.json()["message"] == "Enabled tracking for structure 1022734985680 via character 90000042."

    detail = client.get("/api/characters/90000042/structures")
    assert detail.status_code == 200
    assert detail.json()[0]["tracking_enabled"] is True


def test_track_character_structure_returns_404_for_missing_character_or_access(client) -> None:
    response = client.post("/api/characters/99999999/structures/1022734985680/track")
    assert response.status_code == 404

    reset_character_tables()
    session = SessionLocal()
    try:
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
        session.commit()
    finally:
        session.close()

    response = client.post("/api/characters/90000042/structures/1022734985680/track")
    assert response.status_code == 404


def test_sync_character_triggers_structure_discovery_and_updates_sync_state(client) -> None:
    reset_character_tables()
    session = SessionLocal()
    try:
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
                structures_sync_status="pending",
            )
        )
        session.add(
            CharacterAccessibleStructure(
                character_id=character.id,
                structure_id=1022734985679,
                structure_name="Perimeter Market Keepstar",
                system_name="Perimeter",
                region_name="The Forge",
                access_verified_at=datetime(2026, 3, 21, 11, 0, tzinfo=UTC),
                tracking_enabled=True,
                polling_tier="core",
                last_snapshot_at=None,
                confidence_score=0.88,
            )
        )
        session.commit()
        character_db_id = character.id
    finally:
        session.close()

    response = client.post("/api/characters/90000042/sync")
    assert response.status_code == 200
    assert response.json()["message"] == "Synced 3 accessible structures for character 90000042."

    detail = client.get("/api/characters/90000042/structures")
    assert detail.status_code == 200
    rows_by_id = {row["structure_id"]: row for row in detail.json()}
    assert sorted(rows_by_id) == [1022734985679, 1022734985680, 1022734985687]
    assert rows_by_id[1022734985679]["tracking_enabled"] is True
    assert rows_by_id[1022734985687]["tracking_enabled"] is False

    session = SessionLocal()
    try:
        sync_state = session.scalar(
            select(EsiCharacterSyncState).where(EsiCharacterSyncState.character_id == character_db_id)
        )
        assert sync_state is not None
        assert sync_state.last_successful_sync is not None
        assert sync_state.structures_sync_status == "ok"
    finally:
        session.close()


def test_sync_character_returns_404_for_missing_character(client) -> None:
    response = client.post("/api/characters/99999999/sync")
    assert response.status_code == 404


def test_get_settings(client) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["default_analysis_period_days"] == 14
    assert response.json()["trade_groups_page_size"] == 20
    assert response.json()["debug_enabled"] is False
    assert response.json()["target_market_location_ids"]


def test_put_settings_persists_debug_flag(client) -> None:
    response = client.put(
        "/api/settings",
        json={
            "default_analysis_period_days": 14,
            "trade_groups_page_size": 30,
            "debug_enabled": True,
            "sales_tax_rate": 0.036,
            "broker_fee_rate": 0.03,
            "default_user_structure_poll_interval_minutes": 30,
            "snapshot_retention_days": 30,
            "fallback_policy": "regional_fallback",
            "shipping_cost_per_m3": 350.0,
            "target_market_location_ids": [60003760, 60008494],
            "default_filters": {
                "min_item_profit": 15_000_000,
                "min_order_margin_pct": 0.20,
                "roi_now": 0.05,
                "target_demand_day": 1,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["debug_enabled"] is True
    assert response.json()["trade_groups_page_size"] == 30

    session = SessionLocal()
    try:
        row = session.scalar(select(UserSetting).where(UserSetting.user_id.is_(None), UserSetting.key == "defaults"))
        assert row is not None
        assert row.value["debug_enabled"] is True
        assert row.value["trade_groups_page_size"] == 30
        assert row.value["target_market_location_ids"] == [60003760, 60008494]
    finally:
        session.close()


def test_get_auth_me(client) -> None:
    reset_character_tables()

    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["character_name"] == "Demo Trader"


def test_get_auth_login_returns_actionable_redirect_payload(client) -> None:
    response = client.get("/api/auth/login")

    assert response.status_code == 200
    payload = response.json()
    assert payload["authorize_url"].startswith("https://login.eveonline.com/v2/oauth/authorize/?")
    assert payload["scopes"] == build_esi_scopes()


def test_get_character_connect_matches_auth_login_payload(client) -> None:
    login_response = client.get("/api/auth/login")
    connect_response = client.post("/api/characters/connect")

    assert connect_response.status_code == 200
    assert connect_response.json() == login_response.json()
