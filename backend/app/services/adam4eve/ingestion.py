from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.all_models import AdamMarketOrdersTradeRaw
from app.services.postgres_copy import copy_delimited_file


@dataclass
class AdamMarketOrdersImportResult:
    records_processed: int
    created: int
    updated: int


class AdamMarketOrdersIngestionService:
    def ingest_market_orders_export(
        self,
        session: Session,
        *,
        csv_file_path: str | Path,
    ) -> AdamMarketOrdersImportResult:
        return self.ingest_market_orders_exports(session, csv_file_paths=[csv_file_path])

    def ingest_market_orders_exports(
        self,
        session: Session,
        *,
        csv_file_paths: list[str | Path],
    ) -> AdamMarketOrdersImportResult:
        csv_paths = [Path(csv_file_path) for csv_file_path in csv_file_paths]
        if not csv_paths:
            return AdamMarketOrdersImportResult(records_processed=0, created=0, updated=0)
        if session.get_bind().dialect.name != "postgresql":
            raise RuntimeError("Adam4EVE raw staging import requires PostgreSQL COPY.")

        session.execute(delete(AdamMarketOrdersTradeRaw))
        records_processed = 0
        for csv_path in csv_paths:
            copy_delimited_file(
                session,
                table_name=AdamMarketOrdersTradeRaw.name,
                file_path=csv_path,
                delimiter=";",
                header=True,
            )
            records_processed += self._count_csv_rows(csv_path)
        session.commit()

        return AdamMarketOrdersImportResult(
            records_processed=records_processed,
            created=records_processed,
            updated=0,
        )

    @staticmethod
    def _count_csv_rows(csv_path: Path) -> int:
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            line_count = sum(1 for _ in handle)
        return max(line_count - 1, 0)
