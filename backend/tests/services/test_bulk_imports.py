from datetime import date
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.all_models import BulkImportCursor, BulkImportFile
from app.services.sync import bulk_imports as bulk_imports_module
from app.services.sync.bulk_imports import BulkImportService
from tests.db_test_utils import build_test_session

pytestmark = pytest.mark.integration


def test_cached_import_file_is_reused_without_redownload() -> None:
    session = build_test_session()
    download_calls = {"count": 0}

    with TemporaryDirectory() as temp_dir:
        service = BulkImportService(cache_root=temp_dir)

        def downloader() -> bytes:
            download_calls["count"] += 1
            return b"payload"

        first = service.get_cached_or_fetch(
            session,
            import_kind="adam4eve_npc_demand",
            file_key="/MarketOrdersTrades/2026/export.csv",
            remote_path="/MarketOrdersTrades/2026/export.csv",
            downloader=downloader,
            covered_date=date(2026, 3, 22),
        )
        second = service.get_cached_or_fetch(
            session,
            import_kind="adam4eve_npc_demand",
            file_key="/MarketOrdersTrades/2026/export.csv",
            remote_path="/MarketOrdersTrades/2026/export.csv",
            downloader=downloader,
            covered_date=date(2026, 3, 22),
        )

    rows = session.scalars(select(BulkImportFile)).all()

    assert first.downloaded is True
    assert second.downloaded is False
    assert download_calls["count"] == 1
    assert len(rows) == 1
    assert rows[0].covered_date == date(2026, 3, 22)


def test_bulk_import_cursor_tracks_latest_completed_date_and_key() -> None:
    session = build_test_session()
    service = BulkImportService()

    service.mark_cursor(
        session,
        import_kind="esi_history_daily",
        scope_key="region:1",
        synced_through_date=date(2026, 3, 20),
        last_completed_key="2026-03-20",
    )
    service.mark_cursor(
        session,
        import_kind="esi_history_daily",
        scope_key="region:1",
        synced_through_date=date(2026, 3, 22),
        last_completed_key="2026-03-22",
    )

    cursor = session.scalar(select(BulkImportCursor))

    assert cursor is not None
    assert cursor.synced_through_date == date(2026, 3, 22)
    assert cursor.last_completed_key == "2026-03-22"


def test_cached_import_file_logs_download_then_cache_hit() -> None:
    session = build_test_session()

    with TemporaryDirectory() as temp_dir:
        service = BulkImportService(cache_root=temp_dir)

        def downloader() -> bytes:
            return b"payload"

        with patch.object(bulk_imports_module.logger, "info") as mock_info:
            first = service.get_cached_or_fetch(
                session,
                import_kind="esi_history_daily",
                file_key="/MarketPricesRegionHistory/2026/export.csv",
                remote_path="/MarketPricesRegionHistory/2026/export.csv",
                downloader=downloader,
                covered_date=date(2026, 3, 26),
            )
            second = service.get_cached_or_fetch(
                session,
                import_kind="esi_history_daily",
                file_key="/MarketPricesRegionHistory/2026/export.csv",
                remote_path="/MarketPricesRegionHistory/2026/export.csv",
                downloader=downloader,
                covered_date=date(2026, 3, 26),
            )

    assert first.downloaded is True
    assert second.downloaded is False
    assert [call.args[0] for call in mock_info.call_args_list] == [
        "downloading import_kind=%s remote_path=%s local_path=%s covered_date=%s",
        "downloaded import_kind=%s remote_path=%s local_path=%s bytes=%s",
        "cache hit import_kind=%s remote_path=%s local_path=%s covered_date=%s",
    ]
