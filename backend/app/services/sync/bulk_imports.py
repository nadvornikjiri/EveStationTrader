from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.all_models import BulkImportCursor, BulkImportFile

logger = logging.getLogger("app.imports")


@dataclass(frozen=True)
class DownloadProgress:
    """Progress state for a single file download."""
    file_index: int
    file_total: int
    file_name: str
    downloaded_bytes: int
    total_bytes: int | None


#: Callback signature: ``(progress: DownloadProgress) -> None``
DownloadProgressCallback = Callable[[DownloadProgress], None]


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
            logger.info(
                "cache hit import_kind=%s remote_path=%s local_path=%s covered_date=%s",
                import_kind,
                remote_path,
                destination,
                covered_date.isoformat() if covered_date is not None else "-",
            )
            return CachedImportFile(path=destination, downloaded=False)

        logger.info(
            "downloading import_kind=%s remote_path=%s local_path=%s covered_date=%s",
            import_kind,
            remote_path,
            destination,
            covered_date.isoformat() if covered_date is not None else "-",
        )
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
        logger.info(
            "downloaded import_kind=%s remote_path=%s local_path=%s bytes=%s",
            import_kind,
            remote_path,
            destination,
            len(content),
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
        progress_callback: DownloadProgressCallback | None = None,
        file_index: int = 0,
        file_total: int = 0,
    ) -> CachedImportFile:
        return self.get_cached_or_fetch(
            session,
            import_kind=import_kind,
            file_key=file_key,
            remote_path=remote_path,
            covered_date=covered_date,
            downloader=lambda: self._stream_download_with_client(
                client,
                remote_path,
                progress_callback=progress_callback,
                file_index=file_index,
                file_total=file_total,
            ),
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
        return BulkImportService._stream_download_with_client(client, remote_path)

    @staticmethod
    def _stream_download_with_client(
        client: httpx.Client,
        remote_path: str,
        *,
        progress_callback: DownloadProgressCallback | None = None,
        file_index: int = 0,
        file_total: int = 0,
    ) -> bytes:
        import time as _time

        file_name = remote_path.rsplit("/", 1)[-1] if "/" in remote_path else remote_path
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                if progress_callback is not None:
                    # Stream with progress reporting
                    with client.stream("GET", remote_path) as response:
                        response.raise_for_status()
                        content_length_header = response.headers.get("content-length")
                        total_bytes = int(content_length_header) if content_length_header else None
                        chunks: list[bytes] = []
                        downloaded = 0
                        _REPORT_INTERVAL = 1_048_576  # report every ~1 MB
                        last_reported = 0
                        for chunk in response.iter_bytes(chunk_size=131_072):
                            chunks.append(chunk)
                            downloaded += len(chunk)
                            if downloaded - last_reported >= _REPORT_INTERVAL or downloaded == total_bytes:
                                last_reported = downloaded
                                progress_callback(DownloadProgress(
                                    file_index=file_index,
                                    file_total=file_total,
                                    file_name=file_name,
                                    downloaded_bytes=downloaded,
                                    total_bytes=total_bytes,
                                ))
                        return b"".join(chunks)
                else:
                    response = client.get(remote_path)
                    response.raise_for_status()
                    content = getattr(response, "content", None)
                    if content is not None:
                        return content
                    return response.text.encode("utf-8")
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt < 2:
                    _time.sleep(2**attempt)
                    logger.warning(
                        "download retry attempt=%s remote_path=%s error=%s",
                        attempt + 1,
                        remote_path,
                        exc,
                    )
        raise last_error  # type: ignore[misc]
