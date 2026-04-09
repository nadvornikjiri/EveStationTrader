from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import AdamMarketPriceHistoryDaily, EsiMarketOrder, Item, Location, MarketPricePeriod, Region, System
from app.services.adam4eve.client import AdamMarketOrdersExport, AdamStationPriceHistoryExport
from app.services.adam4eve.history_ingestion import AdamStationPriceHistoryIngestionService
from app.services.esi.history_ingestion import EsiRegionalHistoryRecord, EsiRegionalHistoryIngestionService
from app.services.sync.bulk_imports import CachedImportFile
from app.services.sync.service import SyncService
from tests.db_test_utils import build_test_session

pytestmark = pytest.mark.integration


def build_session() -> Session:
    return build_test_session()


def seed_region_location_and_items(session: Session) -> tuple[int, list[int], int]:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    session.add(system)
    session.flush()

    location = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=system.id,
        region_id=region.id,
        name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    )
    items = [
        Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material"),
        Item(type_id=35, name="Pyerite", volume_m3=0.01, group_name="Mineral", category_name="Material"),
    ]
    session.add(location)
    session.add_all(items)
    session.commit()
    return location.id, [item.id for item in items], region.id


def test_ingest_region_history_persists_internal_rows() -> None:
    session = build_session()
    location_id, item_ids, region_id = seed_region_location_and_items(session)

    result = EsiRegionalHistoryIngestionService().ingest_region_history(
        session,
        eve_region_id=10000002,
        records=[
            {
                "location_id": 60003760,
                "region_id": 10000002,
                "type_id": 34,
                "date": "2026-03-20",
                "buy_price_low": 90.0,
                "buy_price_avg": 95.0,
                "buy_price_high": 99.0,
                "sell_price_low": 90.0,
                "sell_price_avg": 100.0,
                "sell_price_high": 120.0,
            },
            {
                "location_id": 60003760,
                "region_id": 10000002,
                "type_id": 35,
                "date": "2026-03-20",
                "buy_price_low": 180.0,
                "buy_price_avg": 190.0,
                "buy_price_high": 195.0,
                "sell_price_low": 180.0,
                "sell_price_avg": 200.0,
                "sell_price_high": 220.0,
            },
        ],
    )

    rows = session.scalars(
        select(AdamMarketPriceHistoryDaily).order_by(AdamMarketPriceHistoryDaily.type_id.asc())
    ).all()

    assert result.region_id == region_id
    assert result.records_processed == 2
    assert result.created == 2
    assert result.updated == 0
    assert len(rows) == 2
    assert rows[0].location_id == location_id
    assert rows[0].type_id == item_ids[0]
    assert rows[0].date == date(2026, 3, 20)
    assert rows[0].average == 100.0
    assert rows[0].volume == 0
    assert rows[1].type_id == item_ids[1]
    assert rows[1].average == 200.0


def test_ingest_region_history_appends_new_history_rows_without_reading_existing_keys() -> None:
    session = build_session()
    seed_region_location_and_items(session)
    service = EsiRegionalHistoryIngestionService()

    first = service.ingest_region_history(
        session,
        eve_region_id=10000002,
        records=[
            {
                "location_id": 60003760,
                "region_id": 10000002,
                "type_id": 34,
                "date": "2026-03-20",
                "buy_price_low": 90.0,
                "buy_price_avg": 95.0,
                "buy_price_high": 99.0,
                "sell_price_low": 90.0,
                "sell_price_avg": 100.0,
                "sell_price_high": 120.0,
            }
        ],
    )
    second = service.ingest_region_history(
        session,
        eve_region_id=10000002,
        records=[
            {
                "location_id": 60003760,
                "region_id": 10000002,
                "type_id": 34,
                "date": "2026-03-21",
                "buy_price_low": 95.0,
                "buy_price_avg": 100.0,
                "buy_price_high": 104.0,
                "sell_price_low": 95.0,
                "sell_price_avg": 105.0,
                "sell_price_high": 125.0,
            }
        ],
    )

    rows = session.scalars(
        select(AdamMarketPriceHistoryDaily).order_by(AdamMarketPriceHistoryDaily.date.asc())
    ).all()

    assert first.created == 1
    assert first.updated == 0
    assert second.created == 1
    assert second.updated == 0
    assert len(rows) == 2
    assert rows[0].average == 100.0
    assert rows[0].highest == 120.0
    assert rows[0].lowest == 90.0
    assert rows[0].order_count == 0
    assert rows[0].volume == 0
    assert rows[1].date == date(2026, 3, 21)
    assert rows[1].average == 105.0
    assert rows[1].highest == 125.0
    assert rows[1].lowest == 95.0
    assert rows[1].order_count == 0
    assert rows[1].volume == 0


def test_ingest_region_history_file_accepts_price_date_columns(tmp_path) -> None:
    session = build_session()
    location_id, item_ids, region_id = seed_region_location_and_items(session)
    csv_path = tmp_path / "MarketPricesStationHistory_rest_weekly_2026-12.csv"
    csv_path.write_text(
        "type_id;location_id;region_id;price_date;buy_price_low;buy_price_avg;buy_price_high;"
        "sell_price_low;sell_price_avg;sell_price_high;buy_volume_low;buy_volume_avg;buy_volume_high;"
        "sell_volume_low;sell_volume_avg;sell_volume_high\n"
        "34;60003760;10000002;2026-03-21;90.0;95.0;99.0;90.0;100.0;120.0;1;1;1;2;2;2\n"
        "34;60003760;10000002;2026-03-20;91.0;96.0;100.0;91.0;101.0;121.0;1;1;1;2;2;2\n"
        "35;60003760;10000002;2026-03-21;180.0;190.0;195.0;180.0;200.0;220.0;1;1;1;2;2;2\n",
        encoding="utf-8",
    )

    result = AdamStationPriceHistoryIngestionService().ingest_region_history_file(
        session,
        eve_region_id=10000002,
        csv_file_path=csv_path,
        location_ids=[60003760],
        type_ids=[34],
        since_date=date(2026, 3, 20),
    )
    rows = session.scalars(select(AdamMarketPriceHistoryDaily)).all()

    assert result.region_id == region_id
    assert result.records_processed == 1
    assert result.created == 1
    assert len(rows) == 1
    assert rows[0].location_id == location_id
    assert rows[0].type_id == item_ids[0]
    assert rows[0].date == date(2026, 3, 21)
    assert rows[0].average == 100.0


class StubAdamHistoryClient:
    def __init__(self, cached_file_path: Path) -> None:
        self.cached_file_path = cached_file_path

    def get_headers(self) -> dict[str, str]:
        return {"User-Agent": "test-agent"}

    def resolve_latest_market_orders_export(self) -> AdamMarketOrdersExport:
        return AdamMarketOrdersExport(
            path="/MarketOrdersTrades/2026/marketOrderTrades_weekly_2026-12.csv",
            export_key="2026-12",
            covered_through_date=date(2026, 3, 22),
        )

    def resolve_market_orders_exports(
        self,
        *,
        since_date: date | None,
    ) -> list[AdamMarketOrdersExport]:
        del since_date
        return [self.resolve_latest_market_orders_export()]

    def cache_market_orders_export(self, *, export_path: str, session=None) -> CachedImportFile:
        del export_path, session
        return CachedImportFile(path=self.cached_file_path, downloaded=False)

    def cache_market_orders_exports(
        self,
        *,
        since_date: date | None,
        session=None,
    ) -> list[tuple[AdamMarketOrdersExport, CachedImportFile]]:
        del since_date, session
        export = self.resolve_latest_market_orders_export()
        return [(export, CachedImportFile(path=self.cached_file_path, downloaded=False))]

    def fetch_regional_price_history(
        self,
        region_id: int,
        type_ids: list[int],
        *,
        location_ids: list[int],
        since_date: date | None = None,
        session=None,
    ) -> list[EsiRegionalHistoryRecord]:
        del region_id
        del location_ids
        del since_date
        del session
        return [
            {
                "location_id": 60003760,
                "region_id": 10000002,
                "type_id": type_ids[0],
                "date": "2026-03-20",
                "buy_price_low": 90.0,
                "buy_price_avg": 95.0,
                "buy_price_high": 99.0,
                "sell_price_low": 90.0,
                "sell_price_avg": 100.0,
                "sell_price_high": 120.0,
            },
            {
                "location_id": 60003760,
                "region_id": 10000002,
                "type_id": type_ids[0],
                "date": "2026-03-19",
                "buy_price_low": 95.0,
                "buy_price_avg": 100.0,
                "buy_price_high": 105.0,
                "sell_price_low": 95.0,
                "sell_price_avg": 110.0,
                "sell_price_high": 130.0,
            },
        ]

    def resolve_station_price_history_exports(
        self,
        *,
        since_date: date | None,
    ) -> list[AdamStationPriceHistoryExport]:
        del since_date
        return [
            AdamStationPriceHistoryExport(
                path="/MarketPricesStationHistory/2026/MarketPricesStationHistory_rest_weekly_2026-12.csv",
                export_key="2026-12-rest",
                covered_through_date=date(2026, 3, 22),
            )
        ]

    def cache_station_price_history_exports(
        self,
        *,
        since_date: date | None,
        session=None,
    ):
        del since_date, session
        history_csv = self.cached_file_path.parent / "MarketPricesStationHistory_rest_weekly_2026-12.csv"
        history_csv.write_text(
            "type_id;location_id;region_id;date;buy_price_low;buy_price_avg;buy_price_high;"
            "sell_price_low;sell_price_avg;sell_price_high\n"
            "34;60003760;10000002;2026-03-20;90.0;95.0;99.0;90.0;100.0;120.0\n"
            "34;60003760;10000002;2026-03-19;95.0;100.0;105.0;95.0;110.0;130.0\n",
            encoding="utf-8",
        )
        return [
            (
                AdamStationPriceHistoryExport(
                    path="/MarketPricesStationHistory/2026/MarketPricesStationHistory_rest_weekly_2026-12.csv",
                    export_key="2026-12-rest",
                    covered_through_date=date(2026, 3, 22),
                ),
                CachedImportFile(path=history_csv, downloaded=False),
            )
        ]


def test_sync_service_adam4eve_sync_feeds_market_price_period_computation(tmp_path) -> None:
    session = build_session()
    location_id, item_ids, _region_id = seed_region_location_and_items(session)
    location = session.scalar(select(Location).where(Location.id == location_id))
    assert location is not None
    session.add(
        EsiMarketOrder(
            order_id=9001,
            region_id=location.region_id,
            location_id=location.id,
            type_id=item_ids[0],
            system_id=location.system_id,
            is_buy_order=False,
            price=4.12,
            volume_total=1000,
            volume_remain=400,
            min_volume=1,
            order_range="region",
            issued=datetime.now(UTC),
            duration=90,
        )
    )
    session.commit()

    csv_path = tmp_path / "marketOrderTrades_weekly_2026-12.csv"
    csv_path.write_text(
        "location_id;region_id;type_id;is_buy_order;has_gone;scanDate;amount;high;low;avg;orderNum;iskValue\n"
        "60003760;10000002;34;0;0;2026-03-20;10.0;5.0;5.0;5.0;1;50.0\n",
        encoding="utf-8",
    )
    service = SyncService(
        session_factory=lambda: session,
        adam_client=StubAdamHistoryClient(csv_path),
    )

    response = service.trigger_job("adam4eve_sync")
    result = session.scalar(
        select(MarketPricePeriod).where(
            MarketPricePeriod.location_id == location_id,
            MarketPricePeriod.type_id == item_ids[0],
            MarketPricePeriod.period_days == 14,
        )
    )

    assert response.records_processed >= 6
    assert response.target_type == "locations"
    assert response.target_id == "1"
    assert "Synced Adam4EVE raw staging and station price history" in (response.message or "")
    assert "price periods" in (response.message or "")
    assert result is not None
    assert result.current_price == 100.0
    assert result.period_avg_price == 105.0
    assert result.price_min == 90.0
    assert result.price_max == 130.0
