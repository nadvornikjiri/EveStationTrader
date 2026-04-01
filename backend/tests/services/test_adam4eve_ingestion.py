from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import AdamMarketOrdersTradeRaw, AdamNpcDemandSyncState, Item, Location, Region, System
from app.services.adam4eve.client import AdamMarketOrdersExport, AdamStationPriceHistoryExport
from app.services.adam4eve.history_ingestion import AdamStationPriceHistoryRecord
from app.services.adam4eve.ingestion import AdamMarketOrdersIngestionService
from app.services.sync.bulk_imports import CachedImportFile
from app.services.sync.service import SyncService
from tests.db_test_utils import build_test_session


def build_session() -> Session:
    return build_test_session()


def seed_locations_and_items(session: Session) -> tuple[list[int], list[int]]:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    session.add(system)
    session.flush()

    locations = [
        Location(
            location_id=60003760,
            location_type="npc_station",
            system_id=system.id,
            region_id=region.id,
            name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
        ),
        Location(
            location_id=60008494,
            location_type="npc_station",
            system_id=system.id,
            region_id=region.id,
            name="Amarr VIII (Oris) - Emperor Family Academy",
        ),
    ]
    items = [
        Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material"),
        Item(type_id=35, name="Pyerite", volume_m3=0.01, group_name="Mineral", category_name="Material"),
    ]
    session.add_all(locations)
    session.add_all(items)
    session.commit()
    return [location.id for location in locations], [item.id for item in items]


def test_ingest_market_orders_export_replaces_staging_table(tmp_path) -> None:
    session = build_session()
    seed_locations_and_items(session)
    csv_path = tmp_path / "marketOrderTrades_weekly_2026-12.csv"
    csv_path.write_text(
        "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
        "60003760;10000002;34;0;0;2026-03-20;12.5;5.0;5.0;5.0;1;62.5\n"
        "60008494;10000002;35;1;0;2026-03-20;8.0;4.0;4.0;4.0;1;32.0\n",
        encoding="utf-8",
    )

    result = AdamMarketOrdersIngestionService().ingest_market_orders_export(session, csv_file_path=csv_path)
    rows = session.execute(select(AdamMarketOrdersTradeRaw)).all()

    assert result.records_processed == 2
    assert result.created == 2
    assert result.updated == 0
    assert len(rows) == 2


def test_ingest_market_orders_exports_appends_multiple_files_into_one_refresh(tmp_path) -> None:
    session = build_session()
    seed_locations_and_items(session)
    first_csv = tmp_path / "marketOrderTrades_weekly_2026-11.csv"
    second_csv = tmp_path / "marketOrderTrades_weekly_2026-12.csv"
    first_csv.write_text(
        "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
        "60003760;10000002;34;0;0;2026-03-15;12.5;5.0;5.0;5.0;1;62.5\n",
        encoding="utf-8",
    )
    second_csv.write_text(
        "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
        "60008494;10000002;35;1;0;2026-03-22;8.0;4.0;4.0;4.0;1;32.0\n",
        encoding="utf-8",
    )

    result = AdamMarketOrdersIngestionService().ingest_market_orders_exports(
        session,
        csv_file_paths=[first_csv, second_csv],
    )
    rows = session.execute(select(AdamMarketOrdersTradeRaw)).all()

    assert result.records_processed == 2
    assert result.created == 2
    assert result.updated == 0
    assert len(rows) == 2


class StubAdamClient:
    def __init__(self, cached_file_path) -> None:
        self.cached_file_path = cached_file_path

    def get_headers(self) -> dict[str, str]:
        return {"User-Agent": "test-agent"}

    def resolve_latest_market_orders_export(self):
        return AdamMarketOrdersExport(
            path="/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv",
            export_key="2026-12",
            covered_through_date=date(2026, 3, 22),
        )

    def resolve_market_orders_exports(self, *, since_date: date | None):
        del since_date
        return [self.resolve_latest_market_orders_export()]

    def cache_market_orders_export(self, *, export_path: str, session=None) -> CachedImportFile:
        del export_path, session
        return CachedImportFile(path=self.cached_file_path, downloaded=False)

    def cache_market_orders_exports(self, *, since_date: date | None, session=None):
        del since_date, session
        return [(self.resolve_latest_market_orders_export(), CachedImportFile(path=self.cached_file_path, downloaded=False))]

    def fetch_regional_price_history(
        self,
        region_id: int,
        type_ids: list[int],
        *,
        location_ids: list[int],
        since_date: date | None = None,
        session=None,
    ) -> list[AdamStationPriceHistoryRecord]:
        del region_id, type_ids, location_ids, since_date, session
        return []

    def resolve_station_price_history_exports(
        self,
        *,
        since_date: date | None,
    ) -> list[AdamStationPriceHistoryExport]:
        del since_date
        return []

    def cache_station_price_history_exports(
        self,
        *,
        since_date: date | None,
        session=None,
    ):
        del since_date, session
        return []


def test_sync_service_adam4eve_sync_persists_raw_rows(tmp_path) -> None:
    session = build_session()
    seed_locations_and_items(session)
    csv_path = tmp_path / "marketOrderTrades_weekly_2026-12.csv"
    csv_path.write_text(
        "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
        "60003760;10000002;34;0;0;2026-03-20;20.0;5.0;5.0;5.0;1;100.0\n"
        "60008494;10000002;35;1;0;2026-03-22;10.0;4.0;4.0;4.0;1;40.0\n",
        encoding="utf-8",
    )
    service = SyncService(
        session_factory=lambda: session,
        adam_client=StubAdamClient(csv_path),
    )

    response = service.trigger_job("adam4eve_sync")
    rows = session.execute(select(AdamMarketOrdersTradeRaw)).all()
    sync_states = session.scalars(select(AdamNpcDemandSyncState).order_by(AdamNpcDemandSyncState.region_id.asc())).all()

    assert response.records_processed >= 2
    assert response.target_type == "locations"
    assert "raw rows staged" in (response.message or "")
    assert len(rows) == 2
    assert len(sync_states) == 1
    assert sync_states[0].export_key == "2026-12"
    assert sync_states[0].synced_through_date == date(2026, 3, 22)
