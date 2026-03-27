from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.all_models import BulkImportCursor, BulkImportFile


@dataclass(frozen=True)
class CachedImportFile:
    path: Path
    downloaded: bool


class BulkImportService:
    def __init__(self, cache_root: str | Path | None = None) -> None:
        settings = get_settings()
        self.cache_root = Path(cache_root or settings.bulk_import_cache_dir)

    def get_cached_or_fetch(
        self,
        session: Session | None,
        *,
        import_kind: str,
        file_key: str,
        remote_path: str,
        downloader,
        covered_date: date | None = None,
    ) -> CachedImportFile:
        destination = self._cache_path(import_kind=import_kind, file_key=file_key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists():
            self._record_cached_file(
                session,
                import_kind=import_kind,
                file_key=file_key,
                remote_path=remote_path,
                local_path=destination,
                covered_date=covered_date,
            )
            return CachedImportFile(path=destination, downloaded=False)

        content = downloader()
        destination.write_bytes(content)
        self._record_cached_file(
            session,
            import_kind=import_kind,
            file_key=file_key,
            remote_path=remote_path,
            local_path=destination,
            covered_date=covered_date,
        )
        return CachedImportFile(path=destination, downloaded=True)

    def get_cursor(self, session: Session, *, import_kind: str, scope_key: str) -> BulkImportCursor | None:
        return session.scalar(
            select(BulkImportCursor).where(
                BulkImportCursor.import_kind == import_kind,
                BulkImportCursor.scope_key == scope_key,
            )
        )

    def mark_cursor(
        self,
        session: Session,
        *,
        import_kind: str,
        scope_key: str,
        synced_through_date: date | None = None,
        last_completed_key: str | None = None,
    ) -> BulkImportCursor:
        cursor = self.get_cursor(session, import_kind=import_kind, scope_key=scope_key)
        if cursor is None:
            cursor = BulkImportCursor(import_kind=import_kind, scope_key=scope_key)
            session.add(cursor)

        if synced_through_date is not None:
            existing_synced_through = cursor.synced_through_date
            cursor.synced_through_date = (
                max(existing_synced_through, synced_through_date)
                if existing_synced_through is not None
                else synced_through_date
            )
        if last_completed_key is not None:
            cursor.last_completed_key = last_completed_key
        cursor.last_checked_at = datetime.now(UTC)
        session.commit()
        return cursor

    def cache_http_file(
        self,
        session: Session | None,
        *,
        import_kind: str,
        file_key: str,
        remote_path: str,
        client: httpx.Client,
        covered_date: date | None = None,
    ) -> CachedImportFile:
        return self.get_cached_or_fetch(
            session,
            import_kind=import_kind,
            file_key=file_key,
            remote_path=remote_path,
            covered_date=covered_date,
            downloader=lambda: self._download_with_client(client, remote_path),
        )

    def _record_cached_file(
        self,
        session: Session | None,
        *,
        import_kind: str,
        file_key: str,
        remote_path: str,
        local_path: Path,
        covered_date: date | None,
    ) -> None:
        if session is None:
            return

        row = session.scalar(
            select(BulkImportFile).where(
                BulkImportFile.import_kind == import_kind,
                BulkImportFile.file_key == file_key,
            )
        )
        if row is None:
            row = BulkImportFile(
                import_kind=import_kind,
                file_key=file_key,
                remote_path=remote_path,
                local_path=str(local_path),
                covered_date=covered_date,
            )
            session.add(row)
        else:
            row.remote_path = remote_path
            row.local_path = str(local_path)
            row.covered_date = covered_date
            row.last_used_at = datetime.now(UTC)
        session.commit()

    def _cache_path(self, *, import_kind: str, file_key: str) -> Path:
        parsed = urlparse(file_key)
        if parsed.scheme and parsed.netloc:
            relative = Path(parsed.netloc) / parsed.path.lstrip("/")
        else:
            relative = Path(file_key.lstrip("/"))
        return self.cache_root / import_kind / relative

    @staticmethod
    def _download_with_client(client: httpx.Client, remote_path: str) -> bytes:
        response = client.get(remote_path)
        response.raise_for_status()
        return response.content
