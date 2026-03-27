from datetime import date
from tempfile import TemporaryDirectory

from sqlalchemy import select

from app.models.all_models import BulkImportCursor, BulkImportFile
from app.services.sync.bulk_imports import BulkImportService
from tests.db_test_utils import build_test_session


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
