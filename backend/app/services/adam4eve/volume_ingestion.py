from csv import DictReader
from datetime import date
from io import StringIO
from pathlib import Path
from typing import TypedDict

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.models.all_models import AdamMarketVolumeHistoryDaily, Item, Location, Region
from app.services.adam4eve.history_ingestion import (
    AdamStationHistoryWorksetEntry,
    AdamStationPriceHistoryIngestionResult,
)
from app.services.postgres_copy import copy_delimited_file


class AdamStationVolumeHistoryRecord(TypedDict):
    location_id: int
    region_id: int
    type_id: int
    date: str | date
    sell_volume_avg: int | None


_COPYABLE_COLUMNS = {
    "type_id",
    "location_id",
    "region_id",
    "date",
    "price_date",
    "buy_volume_low",
    "buy_volume_avg",
    "buy_volume_high",
    "sell_volume_low",
    "sell_volume_avg",
    "sell_volume_high",
}


def volume_stage_has_export_key(session: Session, export_key: str) -> bool:
    result = session.execute(
        text("SELECT 1 FROM adam_volume_history_stage WHERE export_key = :key LIMIT 1"),
        {"key": export_key},
    )
    return result.first() is not None


def load_volume_to_stage(session: Session, csv_file_path: str | Path, export_key: str) -> None:
    csv_path = Path(csv_file_path)
    if csv_path.stat().st_size == 0:
        return

    stage_columns = _copy_columns_for_volume_csv(csv_file_path)

    session.execute(
        text(
            """
            CREATE TEMP TABLE IF NOT EXISTS adam_volume_history_file_stage (
                type_id TEXT NULL,
                location_id TEXT NULL,
                region_id TEXT NULL,
                date TEXT NULL,
                price_date TEXT NULL,
                buy_volume_low TEXT NULL,
                buy_volume_avg TEXT NULL,
                buy_volume_high TEXT NULL,
                sell_volume_low TEXT NULL,
                sell_volume_avg TEXT NULL,
                sell_volume_high TEXT NULL
            )
            """
        )
    )
    session.execute(text("TRUNCATE TABLE adam_volume_history_file_stage"))

    copy_delimited_file(
        session,
        table_name="adam_volume_history_file_stage",
        file_path=csv_file_path,
        columns=stage_columns,
    )

    session.execute(
        text(
            """
            INSERT INTO adam_volume_history_stage (
                location_id, region_id, type_id, date, sell_volume_avg, export_key
            )
            SELECT
                CAST(BTRIM(location_id) AS BIGINT),
                CAST(BTRIM(region_id) AS INTEGER),
                CAST(BTRIM(type_id) AS INTEGER),
                CAST(COALESCE(NULLIF(BTRIM(date), ''), NULLIF(BTRIM(price_date), '')) AS DATE),
                CAST(NULLIF(BTRIM(sell_volume_avg), '') AS BIGINT),
                :export_key
            FROM adam_volume_history_file_stage
            WHERE type_id IS NOT NULL
              AND BTRIM(type_id) <> '' AND BTRIM(type_id) <> 'type_id'
              AND location_id IS NOT NULL
              AND BTRIM(location_id) <> '' AND BTRIM(location_id) <> 'location_id'
              AND region_id IS NOT NULL
              AND BTRIM(region_id) <> '' AND BTRIM(region_id) <> 'region_id'
              AND COALESCE(NULLIF(BTRIM(date), ''), NULLIF(BTRIM(price_date), '')) IS NOT NULL
              AND COALESCE(NULLIF(BTRIM(date), ''), NULLIF(BTRIM(price_date), '')) NOT IN ('date', 'price_date')
            ON CONFLICT (location_id, type_id, date)
            DO UPDATE SET
                region_id = EXCLUDED.region_id,
                sell_volume_avg = EXCLUDED.sell_volume_avg,
                export_key = EXCLUDED.export_key
            """
        ),
        {"export_key": export_key},
    )


def populate_volume_daily_from_stage(
    session: Session,
    since_date: date | None,
) -> list[tuple[int, int]]:
    date_filter = "AND stage.date > :since_date" if since_date is not None else ""
    params: dict[str, object] = {}
    if since_date is not None:
        params["since_date"] = since_date

    session.execute(
        text(
            f"""
            DELETE FROM adam_market_volume_history_daily AS daily
            USING adam_volume_history_stage AS stage
            JOIN locations ON locations.location_id = stage.location_id
            JOIN items ON items.type_id = stage.type_id
            WHERE daily.location_id = locations.id
              AND daily.type_id = items.id
              AND daily.date = stage.date
              {date_filter}
            """
        ),
        params,
    )

    session.execute(
        text(
            f"""
            INSERT INTO adam_market_volume_history_daily (
                location_id, type_id, date, sell_volume_avg
            )
            SELECT
                locations.id,
                items.id,
                stage.date,
                stage.sell_volume_avg
            FROM adam_volume_history_stage AS stage
            JOIN locations ON locations.location_id = stage.location_id
            JOIN items ON items.type_id = stage.type_id
            WHERE stage.sell_volume_avg IS NOT NULL
              {date_filter}
            """
        ),
        params,
    )

    touched = session.execute(
        text(
            f"""
            SELECT DISTINCT locations.id, items.id
            FROM adam_volume_history_stage AS stage
            JOIN locations ON locations.location_id = stage.location_id
            JOIN items ON items.type_id = stage.type_id
            {'WHERE stage.date > :since_date' if since_date is not None else ''}
            ORDER BY locations.id ASC, items.id ASC
            """
        ),
        params,
    ).all()

    return [(loc_id, type_id) for loc_id, type_id in touched]


def _copy_columns_for_volume_csv(csv_file_path: str | Path) -> tuple[str, ...]:
    with Path(csv_file_path).open("r", encoding="utf-8") as source:
        header_line = source.readline().strip()
    if not header_line:
        return ()
    columns = tuple(col.strip() for col in header_line.split(";") if col.strip())
    normalized = tuple(col for col in columns if col in _COPYABLE_COLUMNS)
    if len(normalized) != len(columns):
        raise ValueError("Adam4EVE station volume history export is missing required columns.")
    if not {"type_id", "location_id", "region_id", "sell_volume_avg"}.issubset(set(normalized)) or not (
        "date" in normalized or "price_date" in normalized
    ):
        raise ValueError("Adam4EVE station volume history export is missing required columns.")
    return normalized


def _records_from_volume_csv(csv_file_path: str | Path) -> list[AdamStationVolumeHistoryRecord]:
    csv_text = Path(csv_file_path).read_text(encoding="utf-8")
    if not csv_text.strip():
        return []
    rows: list[AdamStationVolumeHistoryRecord] = []
    reader = DictReader(StringIO(csv_text), delimiter=";")
    for row in reader:
        try:
            normalized = _normalize_volume_csv_row(row)
        except (ValueError, KeyError):
            continue
        rows.append(normalized)
    return rows


def _normalize_volume_csv_row(row: dict[str, str | None]) -> AdamStationVolumeHistoryRecord:
    date_value = row.get("date") or row.get("price_date")
    if date_value is None:
        raise ValueError("row is malformed")
    sell_avg_raw = row.get("sell_volume_avg")
    sell_avg: int | None = None
    if sell_avg_raw is not None and sell_avg_raw.strip():
        sell_avg = int(float(sell_avg_raw.strip()))
    return {
        "location_id": int(row["location_id"] or 0),
        "region_id": int(row["region_id"] or 0),
        "type_id": int(row["type_id"] or 0),
        "date": date.fromisoformat(date_value).isoformat(),
        "sell_volume_avg": sell_avg,
    }


def _record_date(record: AdamStationVolumeHistoryRecord) -> date:
    return date.fromisoformat(record["date"]) if isinstance(record["date"], str) else record["date"]


class AdamStationVolumeHistoryIngestionService:
    def ingest_region_history(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[AdamStationVolumeHistoryRecord],
    ) -> AdamStationPriceHistoryIngestionResult:
        return self._ingest_via_orm(session, eve_region_id=eve_region_id, records=records)

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
        if session.get_bind().dialect.name != "postgresql":
            return self._ingest_via_orm_csv(
                session,
                csv_file_path=csv_file_path,
                eve_region_id=eve_region_id,
                location_ids=location_ids or [],
                type_ids=type_ids or [],
                since_date=since_date,
            )

        if Path(csv_file_path).stat().st_size == 0:
            session.commit()
            return AdamStationPriceHistoryIngestionResult(
                region_id=0, records_processed=0, created=0, updated=0, touched_internal_keys=[],
            )

        export_key = str(csv_file_path)
        load_volume_to_stage(session, csv_file_path, export_key)
        touched_internal_keys = populate_volume_daily_from_stage(session, since_date)
        session.commit()
        return AdamStationPriceHistoryIngestionResult(
            region_id=0,
            records_processed=len(touched_internal_keys),
            created=len(touched_internal_keys),
            updated=0,
            touched_internal_keys=touched_internal_keys,
        )

    def _ingest_via_orm_csv(
        self,
        session: Session,
        *,
        csv_file_path: str | Path,
        eve_region_id: int | None,
        location_ids: list[int],
        type_ids: list[int],
        since_date: date | None,
    ) -> AdamStationPriceHistoryIngestionResult:
        records = _records_from_volume_csv(csv_file_path)

        resolved_location_ids = set(location_ids)
        resolved_type_ids = set(type_ids)
        if resolved_location_ids or resolved_type_ids:
            records = [
                r
                for r in records
                if (not resolved_location_ids or r["location_id"] in resolved_location_ids)
                and (not resolved_type_ids or r["type_id"] in resolved_type_ids)
                and (since_date is None or _record_date(r) > since_date)
            ]
        elif since_date is not None:
            records = [r for r in records if _record_date(r) > since_date]

        ingest_region_id = eve_region_id or (records[0]["region_id"] if records else 0)
        return self._ingest_via_orm(session, eve_region_id=ingest_region_id, records=records)

    def _ingest_via_orm(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[AdamStationVolumeHistoryRecord],
    ) -> AdamStationPriceHistoryIngestionResult:
        if not records:
            session.commit()
            return AdamStationPriceHistoryIngestionResult(
                region_id=0, records_processed=0, created=0, updated=0, touched_internal_keys=[],
            )

        external_type_ids = sorted({r["type_id"] for r in records})
        item_lookup = {
            item.type_id: item.id
            for item in session.scalars(select(Item).where(Item.type_id.in_(external_type_ids))).all()
        }

        external_location_ids = sorted({r["location_id"] for r in records})
        location_lookup = {
            location.location_id: location.id
            for location in session.scalars(
                select(Location).where(Location.location_id.in_(external_location_ids))
            ).all()
        }

        known_records = [
            r
            for r in records
            if r["location_id"] in location_lookup and r["type_id"] in item_lookup
        ]
        if not known_records:
            session.commit()
            return AdamStationPriceHistoryIngestionResult(
                region_id=0, records_processed=0, created=0, updated=0, touched_internal_keys=[],
            )

        touched_internal_keys = sorted(
            {(location_lookup[r["location_id"]], item_lookup[r["type_id"]]) for r in known_records}
        )

        transformed_dates = sorted(
            {date.fromisoformat(r["date"]) if isinstance(r["date"], str) else r["date"] for r in known_records}
        )
        session.execute(
            delete(AdamMarketVolumeHistoryDaily).where(
                AdamMarketVolumeHistoryDaily.location_id.in_(location_lookup.values()),
                AdamMarketVolumeHistoryDaily.type_id.in_(item_lookup.values()),
                AdamMarketVolumeHistoryDaily.date.in_(transformed_dates),
            )
        )
        for record in known_records:
            sell_avg = record["sell_volume_avg"]
            if sell_avg is None:
                continue
            record_date = record["date"]
            normalized_date = date.fromisoformat(record_date) if isinstance(record_date, str) else record_date
            session.add(
                AdamMarketVolumeHistoryDaily(
                    location_id=location_lookup[record["location_id"]],
                    type_id=item_lookup[record["type_id"]],
                    date=normalized_date,
                    sell_volume_avg=sell_avg,
                )
            )

        session.commit()

        region_id = 0
        if eve_region_id:
            region = session.scalar(select(Region).where(Region.region_id == eve_region_id))
            region_id = region.id if region else 0

        return AdamStationPriceHistoryIngestionResult(
            region_id=region_id,
            records_processed=len(known_records),
            created=len(known_records),
            updated=0,
            touched_internal_keys=touched_internal_keys,
        )
