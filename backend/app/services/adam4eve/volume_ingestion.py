from datetime import date
from pathlib import Path
from typing import TypedDict

from sqlalchemy import and_, delete, or_, text, select
from sqlalchemy.orm import Session

from app.models.all_models import AdamMarketVolumeHistoryDaily, AdamMarketVolumeHistoryRaw, Item, Location, Region
from app.services.adam4eve.history_ingestion import (
    AdamStationHistoryWorksetEntry,
    AdamStationPriceHistoryIngestionResult,
)
from app.services.postgres_copy import copy_delimited_file, copy_rows


class AdamStationVolumeHistoryRecord(TypedDict):
    location_id: int
    region_id: int
    type_id: int
    date: str | date
    sell_volume_avg: int | None


class AdamStationVolumeHistoryIngestionService:
    _COPYABLE_COLUMNS = {
        "type_id",
        "location_id",
        "region_id",
        "date",
        "price_date",
        "sell_volume_avg",
    }

    def ingest_region_history(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[AdamStationVolumeHistoryRecord],
    ) -> AdamStationPriceHistoryIngestionResult:
        if session.get_bind().dialect.name != "postgresql":
            return self._ingest_via_orm(session, eve_region_id=eve_region_id, records=records)
        return self._ingest_via_postgres_copy(session, eve_region_id=eve_region_id, records=records)

    def ingest_region_history_file(
        self,
        session: Session,
        *,
        csv_file_path: str | Path,
        workset_entries: list[AdamStationHistoryWorksetEntry] | None = None,
        eve_region_id: int | None = None,
        location_ids: list[int] | None = None,
        type_ids: list[int] | None = None,
        since_date: date | None,
    ) -> AdamStationPriceHistoryIngestionResult:
        resolved_workset_entries = workset_entries or self._build_workset_entries(
            session,
            eve_region_id=eve_region_id,
            location_ids=location_ids or [],
            type_ids=type_ids or [],
        )
        if session.get_bind().dialect.name != "postgresql":
            records = self._records_from_csv_file(csv_file_path)
            resolved_location_ids = {entry.external_location_id for entry in resolved_workset_entries}
            resolved_type_ids = {entry.external_type_id for entry in resolved_workset_entries}
            resolved_region_ids = {entry.external_region_id for entry in resolved_workset_entries}
            filtered_records = [
                record
                for record in records
                if record["region_id"] in resolved_region_ids
                and record["location_id"] in resolved_location_ids
                and record["type_id"] in resolved_type_ids
                and (since_date is None or self._record_date(record) > since_date)
            ]
            return self.ingest_region_history(
                session,
                eve_region_id=next(iter(resolved_region_ids), 0),
                records=filtered_records,
            )

        if not resolved_workset_entries:
            session.commit()
            return AdamStationPriceHistoryIngestionResult(
                region_id=0,
                records_processed=0,
                created=0,
                updated=0,
                touched_internal_keys=[],
            )
        if Path(csv_file_path).stat().st_size == 0:
            session.commit()
            return AdamStationPriceHistoryIngestionResult(
                region_id=0,
                records_processed=0,
                created=0,
                updated=0,
                touched_internal_keys=[],
            )

        stage_columns = self._copy_columns_for_csv(csv_file_path)
        self._prepare_stage_tables(session, workset_entries=resolved_workset_entries)
        copy_delimited_file(
            session,
            table_name="adam_market_volume_history_file_stage",
            file_path=csv_file_path,
            columns=stage_columns,
        )

        filter_sql = self._filtered_stage_sql(since_date=since_date)
        self._materialize_filtered_stage(
            session,
            since_date=since_date,
            filter_sql=filter_sql,
        )
        row_count = int(
            session.execute(
                text("SELECT COUNT(*) FROM adam_market_volume_history_filtered_stage")
            ).scalar_one()
        )
        if row_count == 0:
            session.commit()
            return AdamStationPriceHistoryIngestionResult(
                region_id=0,
                records_processed=0,
                created=0,
                updated=0,
                touched_internal_keys=[],
            )

        touched_internal_keys = [
            (location_id, type_id)
            for location_id, type_id in session.execute(
                text(
                    """
                    SELECT DISTINCT
                        filtered_stage.internal_location_id,
                        filtered_stage.internal_type_id
                    FROM adam_market_volume_history_filtered_stage AS filtered_stage
                    ORDER BY filtered_stage.internal_location_id ASC, filtered_stage.internal_type_id ASC
                    """
                )
            ).all()
        ]

        session.execute(
            text(
                """
                DELETE FROM adam_market_volume_history_raw AS raw
                USING adam_market_volume_history_filtered_stage AS filtered_stage
                WHERE raw.location_id = filtered_stage.external_location_id
                  AND raw.type_id = filtered_stage.external_type_id
                  AND raw.date = filtered_stage.date
                """
            ),
        )
        session.execute(
            text(
                """
                INSERT INTO adam_market_volume_history_raw (
                    location_id,
                    region_id,
                    type_id,
                    date,
                    sell_volume_avg
                )
                SELECT
                    external_location_id,
                    external_region_id,
                    external_type_id,
                    date,
                    sell_volume_avg
                FROM adam_market_volume_history_filtered_stage
                WHERE sell_volume_avg IS NOT NULL
                """
            ),
        )
        session.execute(
            text(
                """
                DELETE FROM adam_market_volume_history_daily AS daily
                USING (
                    SELECT
                        filtered_stage.internal_location_id AS location_id,
                        filtered_stage.internal_type_id AS type_id,
                        filtered_stage.date AS date
                    FROM adam_market_volume_history_filtered_stage AS filtered_stage
                ) AS filtered_internal
                WHERE daily.location_id = filtered_internal.location_id
                  AND daily.type_id = filtered_internal.type_id
                  AND daily.date = filtered_internal.date
                """
            ),
        )
        session.execute(
            text(
                """
                INSERT INTO adam_market_volume_history_daily (
                    location_id,
                    type_id,
                    date,
                    sell_volume_avg
                )
                SELECT
                    filtered_stage.internal_location_id,
                    filtered_stage.internal_type_id,
                    filtered_stage.date,
                    filtered_stage.sell_volume_avg
                FROM adam_market_volume_history_filtered_stage AS filtered_stage
                WHERE filtered_stage.sell_volume_avg IS NOT NULL
                """
            ),
        )

        session.commit()
        return AdamStationPriceHistoryIngestionResult(
            region_id=resolved_workset_entries[0].internal_region_id,
            records_processed=row_count,
            created=row_count,
            updated=0,
            touched_internal_keys=touched_internal_keys,
        )

    def _build_workset_entries(
        self,
        session: Session,
        *,
        eve_region_id: int | None,
        location_ids: list[int],
        type_ids: list[int],
    ) -> list[AdamStationHistoryWorksetEntry]:
        if eve_region_id is None or not location_ids or not type_ids:
            return []

        region = session.scalar(select(Region).where(Region.region_id == eve_region_id))
        if region is None:
            raise ValueError(f"eve_region_id {eve_region_id} was not found")

        locations = {
            location.location_id: location
            for location in session.scalars(select(Location).where(Location.location_id.in_(location_ids))).all()
        }
        missing_location_ids = [location_id for location_id in location_ids if location_id not in locations]
        if missing_location_ids:
            missing = ", ".join(str(location_id) for location_id in missing_location_ids)
            raise ValueError(f"locations were not found for location_ids: {missing}")

        items = {
            item.type_id: item.id for item in session.scalars(select(Item).where(Item.type_id.in_(type_ids))).all()
        }
        missing_type_ids = [type_id for type_id in type_ids if type_id not in items]
        if missing_type_ids:
            missing = ", ".join(str(type_id) for type_id in missing_type_ids)
            raise ValueError(f"items were not found for type_ids: {missing}")

        return [
            AdamStationHistoryWorksetEntry(
                internal_region_id=region.id,
                external_region_id=eve_region_id,
                internal_location_id=locations[location_id].id,
                external_location_id=location_id,
                internal_type_id=items[type_id],
                external_type_id=type_id,
            )
            for location_id in sorted(set(location_ids))
            for type_id in sorted(set(type_ids))
        ]

    def _ingest_via_postgres_copy(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[AdamStationVolumeHistoryRecord],
    ) -> AdamStationPriceHistoryIngestionResult:
        region = session.scalar(select(Region).where(Region.region_id == eve_region_id))
        if region is None:
            raise ValueError(f"eve_region_id {eve_region_id} was not found")

        if not records:
            session.commit()
            return AdamStationPriceHistoryIngestionResult(
                region_id=region.id,
                records_processed=0,
                created=0,
                updated=0,
                touched_internal_keys=[],
            )

        external_type_ids = sorted({record["type_id"] for record in records})
        item_lookup = {
            item.type_id: item.id
            for item in session.scalars(select(Item).where(Item.type_id.in_(external_type_ids))).all()
        }
        missing_type_ids = [type_id for type_id in external_type_ids if type_id not in item_lookup]
        if missing_type_ids:
            missing = ", ".join(str(type_id) for type_id in missing_type_ids)
            raise ValueError(f"items were not found for type_ids: {missing}")

        external_location_ids = sorted({record["location_id"] for record in records})
        location_lookup = {
            location.location_id: location.id
            for location in session.scalars(
                select(Location).where(Location.location_id.in_(external_location_ids))
            ).all()
        }
        missing_location_ids = [
            location_id for location_id in external_location_ids if location_id not in location_lookup
        ]
        if missing_location_ids:
            missing = ", ".join(str(location_id) for location_id in missing_location_ids)
            raise ValueError(f"locations were not found for location_ids: {missing}")

        normalized_rows: list[tuple[int, int, int, date, int | None]] = []
        for record in records:
            record_date = record["date"]
            normalized_date = date.fromisoformat(record_date) if isinstance(record_date, str) else record_date
            normalized_rows.append(
                (
                    record["location_id"],
                    record["region_id"],
                    record["type_id"],
                    normalized_date,
                    record["sell_volume_avg"],
                )
            )
        created = len(normalized_rows)
        updated = 0
        touched_internal_keys = sorted(
            {
                (location_lookup[record["location_id"]], item_lookup[record["type_id"]])
                for record in records
            }
        )

        if normalized_rows:
            raw_delete_values = ", ".join(
                f"(:location_id_{index}, :type_id_{index}, :date_{index})" for index in range(len(normalized_rows))
            )
            raw_delete_params: dict[str, object] = {}
            for index, row in enumerate(normalized_rows):
                raw_delete_params[f"location_id_{index}"] = row[0]
                raw_delete_params[f"type_id_{index}"] = row[2]
                raw_delete_params[f"date_{index}"] = row[3]
            session.execute(
                text(
                    """
                    DELETE FROM adam_market_volume_history_raw
                    WHERE (location_id, type_id, date) IN (
                        """
                    + raw_delete_values
                    + """
                    )
                    """
                ),
                raw_delete_params,
            )
            copy_rows(
                session,
                table_name="adam_market_volume_history_raw",
                columns=(
                    "location_id",
                    "region_id",
                    "type_id",
                    "date",
                    "sell_volume_avg",
                ),
                rows=(row for row in normalized_rows if row[4] is not None),
            )
            self._transform_raw_history(
                session,
                normalized_rows=normalized_rows,
            )

        session.commit()
        return AdamStationPriceHistoryIngestionResult(
            region_id=region.id,
            records_processed=len(records),
            created=created,
            updated=updated,
            touched_internal_keys=touched_internal_keys,
        )

    def _ingest_via_orm(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[AdamStationVolumeHistoryRecord],
    ) -> AdamStationPriceHistoryIngestionResult:
        region = session.scalar(select(Region).where(Region.region_id == eve_region_id))
        if region is None:
            raise ValueError(f"eve_region_id {eve_region_id} was not found")

        if not records:
            session.commit()
            return AdamStationPriceHistoryIngestionResult(
                region_id=region.id,
                records_processed=0,
                created=0,
                updated=0,
                touched_internal_keys=[],
            )

        external_type_ids = sorted({record["type_id"] for record in records})
        item_lookup = {
            item.type_id: item.id
            for item in session.scalars(select(Item).where(Item.type_id.in_(external_type_ids))).all()
        }
        missing_type_ids = [type_id for type_id in external_type_ids if type_id not in item_lookup]
        if missing_type_ids:
            missing = ", ".join(str(type_id) for type_id in missing_type_ids)
            raise ValueError(f"items were not found for type_ids: {missing}")

        external_location_ids = sorted({record["location_id"] for record in records})
        location_lookup = {
            location.location_id: location.id
            for location in session.scalars(
                select(Location).where(Location.location_id.in_(external_location_ids))
            ).all()
        }
        missing_location_ids = [
            location_id for location_id in external_location_ids if location_id not in location_lookup
        ]
        if missing_location_ids:
            missing = ", ".join(str(location_id) for location_id in missing_location_ids)
            raise ValueError(f"locations were not found for location_ids: {missing}")

        raw_rows_to_add: list[dict[str, object]] = []
        updated = 0
        for record in records:
            record_date = record["date"]
            normalized_date = date.fromisoformat(record_date) if isinstance(record_date, str) else record_date
            raw_rows_to_add.append(
                {
                    "location_id": record["location_id"],
                    "region_id": record["region_id"],
                    "type_id": record["type_id"],
                    "date": normalized_date,
                    "sell_volume_avg": record["sell_volume_avg"],
                }
            )

        if raw_rows_to_add:
            transformed_dates = sorted(
                {
                    date.fromisoformat(record["date"]) if isinstance(record["date"], str) else record["date"]
                    for record in records
                }
            )
            session.execute(
                delete(AdamMarketVolumeHistoryDaily).where(
                    AdamMarketVolumeHistoryDaily.location_id.in_(location_lookup.values()),
                    AdamMarketVolumeHistoryDaily.type_id.in_(item_lookup.values()),
                    AdamMarketVolumeHistoryDaily.date.in_(transformed_dates),
                )
            )
            session.execute(
                delete(AdamMarketVolumeHistoryRaw).where(
                    or_(
                        *[
                            and_(
                                AdamMarketVolumeHistoryRaw.c.location_id == record["location_id"],
                                AdamMarketVolumeHistoryRaw.c.type_id == record["type_id"],
                                AdamMarketVolumeHistoryRaw.c.date
                                == (
                                    date.fromisoformat(record["date"])
                                    if isinstance(record["date"], str)
                                    else record["date"]
                                ),
                            )
                            for record in records
                        ]
                    )
                )
            )
            session.execute(
                AdamMarketVolumeHistoryRaw.insert(),
                [row for row in raw_rows_to_add if row["sell_volume_avg"] is not None],
            )
            session.flush()
            for record in records:
                sell_volume_avg = record["sell_volume_avg"]
                if sell_volume_avg is None:
                    continue
                session.add(
                    AdamMarketVolumeHistoryDaily(
                        location_id=location_lookup[record["location_id"]],
                        type_id=item_lookup[record["type_id"]],
                        date=date.fromisoformat(record["date"]) if isinstance(record["date"], str) else record["date"],
                        sell_volume_avg=sell_volume_avg,
                    )
                )

        session.commit()
        return AdamStationPriceHistoryIngestionResult(
            region_id=region.id,
            records_processed=len(records),
            created=len(raw_rows_to_add),
            updated=updated,
            touched_internal_keys=sorted(
                {
                    (location_lookup[record["location_id"]], item_lookup[record["type_id"]])
                    for record in records
                }
            ),
        )

    def _transform_raw_history(
        self,
        session: Session,
        *,
        normalized_rows: list[tuple[int, int, int, date, int | None]],
    ) -> None:
        delete_values = ", ".join(
            f"(:location_id_{index}, :type_id_{index}, :date_{index})" for index in range(len(normalized_rows))
        )
        params: dict[str, object] = {}
        for index, row in enumerate(normalized_rows):
            params[f"location_id_{index}"] = row[0]
            params[f"type_id_{index}"] = row[2]
            params[f"date_{index}"] = row[3]

        session.execute(
            text(
                """
                DELETE FROM adam_market_volume_history_daily
                USING locations, items
                WHERE adam_market_volume_history_daily.location_id = locations.id
                  AND adam_market_volume_history_daily.type_id = items.id
                  AND (locations.location_id, items.type_id, adam_market_volume_history_daily.date) IN (
                    """
                + delete_values
                + """
                  )
                """
            ),
            params,
        )
        session.execute(
            text(
                """
                INSERT INTO adam_market_volume_history_daily (
                    location_id,
                    type_id,
                    date,
                    sell_volume_avg
                )
                SELECT
                    locations.id,
                    items.id,
                    raw.date,
                    raw.sell_volume_avg
                FROM adam_market_volume_history_raw AS raw
                JOIN locations ON locations.location_id = raw.location_id
                JOIN items ON items.type_id = raw.type_id
                WHERE (raw.location_id, raw.type_id, raw.date) IN (
                    """
                + delete_values
                + """
                )
                  AND raw.sell_volume_avg IS NOT NULL
                """
            ),
            params,
        )

    def _prepare_stage_tables(
        self,
        session: Session,
        *,
        workset_entries: list[AdamStationHistoryWorksetEntry],
    ) -> None:
        session.execute(
            text(
                """
                CREATE TEMP TABLE IF NOT EXISTS adam_market_volume_history_file_stage (
                    type_id TEXT NULL,
                    location_id TEXT NULL,
                    region_id TEXT NULL,
                    date TEXT NULL,
                    price_date TEXT NULL,
                    sell_volume_avg TEXT NULL
                ) ON COMMIT DROP
                """
            )
        )
        session.execute(text("TRUNCATE TABLE adam_market_volume_history_file_stage"))
        session.execute(
            text(
                """
                CREATE TEMP TABLE IF NOT EXISTS adam_market_volume_history_workset (
                    internal_region_id INTEGER NOT NULL,
                    external_region_id INTEGER NOT NULL,
                    internal_location_id INTEGER NOT NULL,
                    external_location_id BIGINT NOT NULL,
                    internal_type_id INTEGER NOT NULL,
                    external_type_id INTEGER NOT NULL,
                    PRIMARY KEY (external_region_id, external_location_id, external_type_id)
                ) ON COMMIT DROP
                """
            )
        )
        session.execute(text("TRUNCATE TABLE adam_market_volume_history_workset"))
        copy_rows(
            session,
            table_name="adam_market_volume_history_workset",
            columns=(
                "internal_region_id",
                "external_region_id",
                "internal_location_id",
                "external_location_id",
                "internal_type_id",
                "external_type_id",
            ),
            rows=(
                (
                    entry.internal_region_id,
                    entry.external_region_id,
                    entry.internal_location_id,
                    entry.external_location_id,
                    entry.internal_type_id,
                    entry.external_type_id,
                )
                for entry in workset_entries
            ),
        )
        session.execute(
            text(
                """
                CREATE TEMP TABLE IF NOT EXISTS adam_market_volume_history_filtered_stage (
                    internal_region_id INTEGER NOT NULL,
                    external_region_id INTEGER NOT NULL,
                    internal_location_id INTEGER NOT NULL,
                    external_location_id BIGINT NOT NULL,
                    internal_type_id INTEGER NOT NULL,
                    external_type_id INTEGER NOT NULL,
                    date DATE NOT NULL,
                    sell_volume_avg BIGINT NULL
                ) ON COMMIT DROP
                """
            )
        )
        session.execute(text("TRUNCATE TABLE adam_market_volume_history_filtered_stage"))

    def _copy_columns_for_csv(self, csv_file_path: str | Path) -> tuple[str, ...]:
        with Path(csv_file_path).open("r", encoding="utf-8") as source:
            header_line = source.readline().strip()
        if not header_line:
            return ()
        columns = tuple(column.strip() for column in header_line.split(";") if column.strip())
        normalized = tuple(column for column in columns if column in self._COPYABLE_COLUMNS)
        if len(normalized) != len(columns):
            raise ValueError("Adam4EVE station volume history export is missing required columns.")
        if not {"type_id", "location_id", "region_id", "sell_volume_avg"}.issubset(set(normalized)) or not (
            "date" in normalized or "price_date" in normalized
        ):
            raise ValueError("Adam4EVE station volume history export is missing required columns.")
        return normalized

    @staticmethod
    def _filtered_stage_sql(*, since_date: date | None) -> str:
        date_predicate = (
            ""
            if since_date is None
            else "AND CAST(COALESCE(NULLIF(BTRIM(stage.date), ''), NULLIF(BTRIM(stage.price_date), '')) AS DATE) > :since_date"
        )
        return f"""
            SELECT
                workset.internal_region_id AS internal_region_id,
                workset.external_region_id AS external_region_id,
                workset.internal_location_id AS internal_location_id,
                workset.external_location_id AS external_location_id,
                workset.internal_type_id AS internal_type_id,
                workset.external_type_id AS external_type_id,
                CAST(COALESCE(NULLIF(BTRIM(stage.date), ''), NULLIF(BTRIM(stage.price_date), '')) AS DATE) AS date,
                CAST(NULLIF(BTRIM(stage.sell_volume_avg), '') AS BIGINT) AS sell_volume_avg
            FROM (
                SELECT *
                FROM adam_market_volume_history_file_stage
                WHERE type_id IS NOT NULL
                  AND BTRIM(type_id) <> ''
                  AND BTRIM(type_id) <> 'type_id'
                  AND location_id IS NOT NULL
                  AND BTRIM(location_id) <> ''
                  AND BTRIM(location_id) <> 'location_id'
                  AND region_id IS NOT NULL
                  AND BTRIM(region_id) <> ''
                  AND BTRIM(region_id) <> 'region_id'
                  AND COALESCE(NULLIF(BTRIM(date), ''), NULLIF(BTRIM(price_date), '')) IS NOT NULL
                  AND COALESCE(NULLIF(BTRIM(date), ''), NULLIF(BTRIM(price_date), '')) NOT IN ('date', 'price_date')
            ) AS stage
            JOIN adam_market_volume_history_workset AS workset
              ON workset.external_location_id = CAST(stage.location_id AS BIGINT)
             AND workset.external_type_id = CAST(stage.type_id AS INTEGER)
             AND workset.external_region_id = CAST(stage.region_id AS INTEGER)
            WHERE 1 = 1
              {date_predicate}
        """

    def _materialize_filtered_stage(
        self,
        session: Session,
        *,
        since_date: date | None,
        filter_sql: str,
    ) -> None:
        session.execute(
            text(
                f"""
                INSERT INTO adam_market_volume_history_filtered_stage (
                    internal_region_id,
                    external_region_id,
                    internal_location_id,
                    external_location_id,
                    internal_type_id,
                    external_type_id,
                    date,
                    sell_volume_avg
                )
                {filter_sql}
                """
            ),
            {"since_date": since_date},
        )

    def _records_from_csv_file(self, csv_file_path: str | Path) -> list[AdamStationVolumeHistoryRecord]:
        csv_text = Path(csv_file_path).read_text(encoding="utf-8")
        if not csv_text.strip():
            return []
        required_columns = self._copy_columns_for_csv(csv_file_path)
        del required_columns
        from csv import DictReader
        from io import StringIO

        rows: list[AdamStationVolumeHistoryRecord] = []
        reader = DictReader(StringIO(csv_text), delimiter=";")
        for row in reader:
            try:
                normalized = self._normalize_raw_csv_row(row)
            except ValueError:
                continue
            rows.append(normalized)
        return rows

    @staticmethod
    def _normalize_raw_csv_row(row: dict[str, str | None]) -> AdamStationVolumeHistoryRecord:
        date_value = row.get("date") or row.get("price_date")
        if date_value is None:
            raise ValueError("Adam4EVE station volume history export row is malformed.")
        return {
            "location_id": int(row["location_id"] or 0),
            "region_id": int(row["region_id"] or 0),
            "type_id": int(row["type_id"] or 0),
            "date": date.fromisoformat(date_value).isoformat(),
            "sell_volume_avg": AdamStationVolumeHistoryIngestionService._optional_int(row.get("sell_volume_avg")),
        }

    @staticmethod
    def _record_date(record: AdamStationVolumeHistoryRecord) -> date:
        return date.fromisoformat(record["date"]) if isinstance(record["date"], str) else record["date"]

    @staticmethod
    def _optional_int(value: str | None) -> int | None:
        if value is None:
            return None
        rendered = value.strip()
        if not rendered:
            return None
        return int(float(rendered))
