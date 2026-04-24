from csv import DictReader
from dataclasses import dataclass
from datetime import date
from io import StringIO
import logging
from pathlib import Path
from time import perf_counter
from typing import TypedDict

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.all_models import AdamMarketPriceHistoryDaily, Item, Location, Region
from app.services.postgres_copy import copy_delimited_file

logger = logging.getLogger(__name__)


class AdamStationPriceHistoryRecord(TypedDict):
    location_id: int
    region_id: int
    type_id: int
    date: str | date
    buy_price_low: float | None
    buy_price_avg: float | None
    buy_price_high: float | None
    sell_price_low: float | None
    sell_price_avg: float | None
    sell_price_high: float | None


@dataclass
class AdamStationPriceHistoryIngestionResult:
    region_id: int
    records_processed: int
    created: int
    updated: int
    touched_internal_keys: list[tuple[int, int]]


@dataclass(frozen=True)
class AdamStationHistoryWorksetEntry:
    internal_region_id: int
    external_region_id: int
    internal_location_id: int
    external_location_id: int
    internal_type_id: int
    external_type_id: int


_COPYABLE_COLUMNS = {
    "type_id",
    "location_id",
    "region_id",
    "date",
    "price_date",
    "buy_price_low",
    "buy_price_avg",
    "buy_price_high",
    "sell_price_low",
    "sell_price_avg",
    "sell_price_high",
    "buy_volume_low",
    "buy_volume_avg",
    "buy_volume_high",
    "sell_volume_low",
    "sell_volume_avg",
    "sell_volume_high",
}

_CREATE_TEMP_TABLE_SQL = """
    CREATE TEMP TABLE IF NOT EXISTS adam_price_history_file_stage (
        type_id INTEGER NULL,
        location_id BIGINT NULL,
        region_id INTEGER NULL,
        date DATE NULL,
        price_date DATE NULL,
        buy_price_low DOUBLE PRECISION NULL,
        buy_price_avg DOUBLE PRECISION NULL,
        buy_price_high DOUBLE PRECISION NULL,
        sell_price_low DOUBLE PRECISION NULL,
        sell_price_avg DOUBLE PRECISION NULL,
        sell_price_high DOUBLE PRECISION NULL,
        buy_volume_low DOUBLE PRECISION NULL,
        buy_volume_avg DOUBLE PRECISION NULL,
        buy_volume_high DOUBLE PRECISION NULL,
        sell_volume_low DOUBLE PRECISION NULL,
        sell_volume_avg DOUBLE PRECISION NULL,
        sell_volume_high DOUBLE PRECISION NULL
    )
"""

_INSERT_FROM_TEMP_SQL = """
    INSERT INTO adam_market_price_history_daily (
        location_id, type_id, date, average, highest, lowest, order_count, volume
    )
    SELECT
        locations.id,
        items.id,
        COALESCE(t.date, t.price_date),
        t.sell_price_avg,
        t.sell_price_high,
        t.sell_price_low,
        0,
        0
    FROM adam_price_history_file_stage t
    JOIN locations ON locations.location_id = t.location_id
    JOIN items ON items.type_id = t.type_id
    WHERE t.type_id IS NOT NULL
      AND t.location_id IS NOT NULL
      AND COALESCE(t.date, t.price_date) IS NOT NULL
      AND t.sell_price_avg IS NOT NULL
      AND t.sell_price_high IS NOT NULL
      AND t.sell_price_low IS NOT NULL
"""

_TOUCHED_KEYS_SQL = """
    SELECT DISTINCT locations.id, items.id
    FROM adam_price_history_file_stage t
    JOIN locations ON locations.location_id = t.location_id
    JOIN items ON items.type_id = t.type_id
    WHERE t.type_id IS NOT NULL
      AND t.location_id IS NOT NULL
    ORDER BY locations.id ASC, items.id ASC
"""


def _copy_columns_for_price_csv(csv_file_path: str | Path) -> tuple[str, ...]:
    with Path(csv_file_path).open("r", encoding="utf-8") as source:
        header_line = source.readline().strip()
    if not header_line:
        return ()
    columns = tuple(col.strip() for col in header_line.split(";") if col.strip())
    normalized = tuple(col for col in columns if col in _COPYABLE_COLUMNS)
    if len(normalized) != len(columns):
        raise ValueError("Adam4EVE station price history export is missing required columns.")
    if not {"type_id", "location_id", "region_id"}.issubset(set(normalized)) or not (
        "date" in normalized or "price_date" in normalized
    ):
        raise ValueError("Adam4EVE station price history export is missing required columns.")
    return normalized


def truncate_price_history_daily(session: Session) -> None:
    """Clear all rows from the daily table before a full reimport."""
    session.execute(text("TRUNCATE TABLE adam_market_price_history_daily"))


def import_price_csv_to_daily(session: Session, csv_file_path: str | Path) -> list[tuple[int, int]]:
    """COPY a CSV into a temp table, then INSERT directly into the daily table with ID translation.

    Returns the list of (location_id, type_id) internal key pairs touched.
    """
    csv_path = Path(csv_file_path)
    if csv_path.stat().st_size == 0:
        return []
    file_size_bytes = csv_path.stat().st_size

    stage_columns = _copy_columns_for_price_csv(csv_file_path)

    session.execute(text(_CREATE_TEMP_TABLE_SQL))
    session.execute(text("TRUNCATE TABLE adam_price_history_file_stage"))

    copy_started_at = perf_counter()
    copy_delimited_file(
        session,
        table_name="adam_price_history_file_stage",
        file_path=csv_file_path,
        columns=stage_columns,
    )
    logger.info(
        "adam4eve profile phase=price_history_copy_to_temp elapsed_s=%.3f file=%s file_size_mb=%.2f column_count=%s",
        perf_counter() - copy_started_at,
        csv_path.name,
        file_size_bytes / (1024 * 1024),
        len(stage_columns),
    )

    insert_started_at = perf_counter()
    session.execute(text(_INSERT_FROM_TEMP_SQL))
    logger.info(
        "adam4eve profile phase=price_history_insert_from_temp elapsed_s=%.3f file=%s",
        perf_counter() - insert_started_at,
        csv_path.name,
    )

    touched_started_at = perf_counter()
    touched = session.execute(text(_TOUCHED_KEYS_SQL)).all()
    touched_keys = [(int(loc_id), int(type_id)) for loc_id, type_id in touched]
    logger.info(
        "adam4eve profile phase=price_history_load_touched_keys elapsed_s=%.3f file=%s touched_keys=%s",
        perf_counter() - touched_started_at,
        csv_path.name,
        len(touched_keys),
    )
    return touched_keys



# ---------------------------------------------------------------------------
# ORM-based helpers (used for non-PostgreSQL backends / tests)
# ---------------------------------------------------------------------------

def _records_from_price_csv(csv_file_path: str | Path) -> list[AdamStationPriceHistoryRecord]:
    csv_text = Path(csv_file_path).read_text(encoding="utf-8")
    if not csv_text.strip():
        return []
    rows: list[AdamStationPriceHistoryRecord] = []
    reader = DictReader(StringIO(csv_text), delimiter=";")
    for row in reader:
        try:
            normalized = _normalize_price_csv_row(row)
        except (ValueError, KeyError):
            continue
        rows.append(normalized)
    return rows


def _normalize_price_csv_row(row: dict[str, str | None]) -> AdamStationPriceHistoryRecord:
    date_value = row.get("date") or row.get("price_date")
    if date_value is None:
        raise ValueError("row is malformed")
    return {
        "location_id": int(row["location_id"] or 0),
        "region_id": int(row["region_id"] or 0),
        "type_id": int(row["type_id"] or 0),
        "date": date.fromisoformat(date_value).isoformat(),
        "buy_price_low": _optional_float(row.get("buy_price_low")),
        "buy_price_avg": _optional_float(row.get("buy_price_avg")),
        "buy_price_high": _optional_float(row.get("buy_price_high")),
        "sell_price_low": _optional_float(row.get("sell_price_low")),
        "sell_price_avg": _optional_float(row.get("sell_price_avg")),
        "sell_price_high": _optional_float(row.get("sell_price_high")),
    }


def _optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    rendered = value.strip()
    if not rendered:
        return None
    return float(rendered)


def _record_date(record: AdamStationPriceHistoryRecord) -> date:
    return date.fromisoformat(record["date"]) if isinstance(record["date"], str) else record["date"]


class AdamStationPriceHistoryIngestionService:
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

        touched_internal_keys = import_price_csv_to_daily(session, csv_file_path)
        session.commit()
        return AdamStationPriceHistoryIngestionResult(
            region_id=0,
            records_processed=len(touched_internal_keys),
            created=len(touched_internal_keys),
            updated=0,
            touched_internal_keys=touched_internal_keys,
        )

    def ingest_region_history(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[AdamStationPriceHistoryRecord],
    ) -> AdamStationPriceHistoryIngestionResult:
        return self._ingest_via_orm(session, eve_region_id=eve_region_id, records=records)

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
        records = _records_from_price_csv(csv_file_path)

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
        records: list[AdamStationPriceHistoryRecord],
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
        from sqlalchemy import delete
        session.execute(
            delete(AdamMarketPriceHistoryDaily).where(
                AdamMarketPriceHistoryDaily.location_id.in_(location_lookup.values()),
                AdamMarketPriceHistoryDaily.type_id.in_(item_lookup.values()),
                AdamMarketPriceHistoryDaily.date.in_(transformed_dates),
            )
        )
        for record in known_records:
            sell_avg = record["sell_price_avg"]
            sell_high = record["sell_price_high"]
            sell_low = record["sell_price_low"]
            if sell_avg is None or sell_high is None or sell_low is None:
                continue
            record_date = record["date"]
            normalized_date = date.fromisoformat(record_date) if isinstance(record_date, str) else record_date
            session.add(
                AdamMarketPriceHistoryDaily(
                    location_id=location_lookup[record["location_id"]],
                    type_id=item_lookup[record["type_id"]],
                    date=normalized_date,
                    average=sell_avg,
                    highest=sell_high,
                    lowest=sell_low,
                    order_count=0,
                    volume=0,
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
