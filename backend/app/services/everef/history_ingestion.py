from collections.abc import Callable
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.postgres_copy import copy_delimited_file


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

        session.execute(
            text(
                """
                DELETE FROM esi_history_daily AS existing
                USING (
                    SELECT
                        region_id::int AS region_id,
                        type_id::int AS type_id,
                        date::date AS date
                    FROM everef_history_stage
                    WHERE region_id IS NOT NULL
                      AND region_id <> ''
                      AND type_id IS NOT NULL
                      AND type_id <> ''
                      AND date IS NOT NULL
                      AND date <> ''
                ) AS staged
                WHERE existing.region_id = staged.region_id
                  AND existing.type_id = staged.type_id
                  AND existing.date = staged.date
                """
            )
        )

        if cancellation_check is not None:
            cancellation_check()

        insert_count = int(
            session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM everef_history_stage
                    WHERE region_id IS NOT NULL
                      AND region_id <> ''
                      AND type_id IS NOT NULL
                      AND type_id <> ''
                      AND date IS NOT NULL
                      AND date <> ''
                    """
                )
            ).scalar_one()
        )
        session.execute(
            text(
                """
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
                    region_id::int,
                    type_id::int,
                    date::date,
                    average::double precision,
                    highest::double precision,
                    lowest::double precision,
                    order_count::int,
                    volume::bigint
                FROM everef_history_stage
                WHERE region_id IS NOT NULL
                  AND region_id <> ''
                  AND type_id IS NOT NULL
                  AND type_id <> ''
                  AND date IS NOT NULL
                  AND date <> ''
                """
            )
        )
        session.commit()
        return insert_count
