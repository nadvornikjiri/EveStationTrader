from collections.abc import Callable
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.postgres_copy import copy_delimited_file

_VALID_STAGED_ROWS = """
    s.region_id IS NOT NULL AND s.region_id <> ''
    AND s.type_id IS NOT NULL AND s.type_id <> ''
    AND s.date IS NOT NULL AND s.date <> ''
"""


class EveRefHistoryIngestionService:
    def ingest_history_file(
        self,
        session: Session,
        csv_path: Path,
        *,
        cancellation_check: Callable[[], None] | None = None,
    ) -> int:
        if session.get_bind().dialect.name != "postgresql":
            raise NotImplementedError("EVE Ref history ingestion requires PostgreSQL COPY.")

        session.execute(text("DROP TABLE IF EXISTS everef_history_stage"))
        session.execute(
            text(
                """
                CREATE TEMP TABLE everef_history_stage (
                    average TEXT,
                    date TEXT,
                    highest TEXT,
                    lowest TEXT,
                    order_count TEXT,
                    volume TEXT,
                    http_last_modified TEXT,
                    region_id TEXT,
                    type_id TEXT
                ) ON COMMIT DROP
                """
            )
        )

        copy_delimited_file(
            session,
            table_name="everef_history_stage",
            file_path=csv_path,
            delimiter=",",
            header=True,
        )

        if cancellation_check is not None:
            cancellation_check()

        # Join staging table against regions/items to resolve internal PKs,
        # then delete any existing rows that will be replaced.
        session.execute(
            text(
                f"""
                DELETE FROM esi_history_daily AS existing
                USING (
                    SELECT
                        r.id AS region_pk,
                        i.id AS type_pk,
                        s.date::date AS date
                    FROM everef_history_stage s
                    JOIN regions r ON r.region_id = s.region_id::int
                    JOIN items i ON i.type_id = s.type_id::int
                    WHERE {_VALID_STAGED_ROWS}
                ) AS staged
                WHERE existing.region_id = staged.region_pk
                  AND existing.type_id = staged.type_pk
                  AND existing.date = staged.date
                """
            )
        )

        if cancellation_check is not None:
            cancellation_check()

        # Count rows that will actually be inserted (only those whose
        # region/item exist in our reference tables).
        insert_count = int(
            session.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM everef_history_stage s
                    JOIN regions r ON r.region_id = s.region_id::int
                    JOIN items i ON i.type_id = s.type_id::int
                    WHERE {_VALID_STAGED_ROWS}
                    """
                )
            ).scalar_one()
        )

        session.execute(
            text(
                f"""
                INSERT INTO esi_history_daily (
                    region_id,
                    type_id,
                    date,
                    average,
                    highest,
                    lowest,
                    order_count,
                    volume
                )
                SELECT
                    r.id,
                    i.id,
                    s.date::date,
                    s.average::double precision,
                    s.highest::double precision,
                    s.lowest::double precision,
                    s.order_count::int,
                    s.volume::bigint
                FROM everef_history_stage s
                JOIN regions r ON r.region_id = s.region_id::int
                JOIN items i ON i.type_id = s.type_id::int
                WHERE {_VALID_STAGED_ROWS}
                """
            )
        )
        session.commit()
        return insert_count
