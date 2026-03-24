import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TypedDict

from sqlalchemy import delete, select, tuple_
from sqlalchemy.orm import Session

from app.models.all_models import AdamNpcDemandDaily, Item, Location
from app.services.postgres_copy import copy_rows


class AdamNpcDemandRecord(TypedDict, total=False):
    location_id: int
    type_id: int
    demand_day: float
    source: str
    date: str | date
    raw_payload: dict


@dataclass
class AdamNpcDemandIngestionResult:
    records_processed: int
    created: int
    updated: int


class AdamNpcDemandIngestionService:
    def ingest_npc_demand(
        self,
        session: Session,
        *,
        records: list[AdamNpcDemandRecord],
    ) -> AdamNpcDemandIngestionResult:
        if session.get_bind().dialect.name != "postgresql":
            return self._ingest_via_orm(session, records=records)
        return self._ingest_via_postgres_copy(session, records=records)

    def _ingest_via_postgres_copy(
        self,
        session: Session,
        *,
        records: list[AdamNpcDemandRecord],
    ) -> AdamNpcDemandIngestionResult:
        if not records:
            session.commit()
            return AdamNpcDemandIngestionResult(records_processed=0, created=0, updated=0)

        external_location_ids = sorted({record["location_id"] for record in records})
        external_type_ids = sorted({record["type_id"] for record in records})

        location_lookup = {
            location.location_id: location.id
            for location in session.scalars(select(Location).where(Location.location_id.in_(external_location_ids))).all()
        }
        item_lookup = {
            item.type_id: item.id
            for item in session.scalars(select(Item).where(Item.type_id.in_(external_type_ids))).all()
        }

        missing_locations = [location_id for location_id in external_location_ids if location_id not in location_lookup]
        if missing_locations:
            missing = ", ".join(str(location_id) for location_id in missing_locations)
            raise ValueError(f"locations were not found for location_ids: {missing}")

        missing_type_ids = [type_id for type_id in external_type_ids if type_id not in item_lookup]
        if missing_type_ids:
            missing = ", ".join(str(type_id) for type_id in missing_type_ids)
            raise ValueError(f"items were not found for type_ids: {missing}")

        normalized_rows: list[tuple[int, int, date, float, str, str]] = []
        row_keys: list[tuple[int, int, date]] = []
        for record in records:
            normalized_date = self._normalize_date(record.get("date"))
            internal_location_id = location_lookup[record["location_id"]]
            internal_type_id = item_lookup[record["type_id"]]
            raw_payload = record.get("raw_payload", dict(record))
            source_label = record.get("source", "adam4eve")
            normalized_rows.append(
                (
                    internal_location_id,
                    internal_type_id,
                    normalized_date,
                    record["demand_day"],
                    source_label,
                    json.dumps(raw_payload),
                )
            )
            row_keys.append((internal_location_id, internal_type_id, normalized_date))

        existing_keys = set(
            session.execute(
                select(AdamNpcDemandDaily.location_id, AdamNpcDemandDaily.type_id, AdamNpcDemandDaily.date).where(
                    tuple_(
                        AdamNpcDemandDaily.location_id,
                        AdamNpcDemandDaily.type_id,
                        AdamNpcDemandDaily.date,
                    ).in_(row_keys)
                )
            ).all()
        )
        updated = sum(1 for key in row_keys if key in existing_keys)
        created = len(row_keys) - updated

        session.execute(
            delete(AdamNpcDemandDaily).where(
                tuple_(
                    AdamNpcDemandDaily.location_id,
                    AdamNpcDemandDaily.type_id,
                    AdamNpcDemandDaily.date,
                ).in_(row_keys)
            )
        )
        copy_rows(
            session,
            table_name="adam_npc_demand_daily",
            columns=("location_id", "type_id", "date", "demand_day", "source_label", "raw_payload"),
            rows=normalized_rows,
        )

        session.commit()
        return AdamNpcDemandIngestionResult(
            records_processed=len(records),
            created=created,
            updated=updated,
        )

    def _ingest_via_orm(
        self,
        session: Session,
        *,
        records: list[AdamNpcDemandRecord],
    ) -> AdamNpcDemandIngestionResult:
        external_location_ids = sorted({record["location_id"] for record in records})
        external_type_ids = sorted({record["type_id"] for record in records})

        location_lookup = {
            location.location_id: location.id
            for location in session.scalars(select(Location).where(Location.location_id.in_(external_location_ids))).all()
        }
        item_lookup = {
            item.type_id: item.id
            for item in session.scalars(select(Item).where(Item.type_id.in_(external_type_ids))).all()
        }

        missing_locations = [location_id for location_id in external_location_ids if location_id not in location_lookup]
        if missing_locations:
            missing = ", ".join(str(location_id) for location_id in missing_locations)
            raise ValueError(f"locations were not found for location_ids: {missing}")

        missing_type_ids = [type_id for type_id in external_type_ids if type_id not in item_lookup]
        if missing_type_ids:
            missing = ", ".join(str(type_id) for type_id in missing_type_ids)
            raise ValueError(f"items were not found for type_ids: {missing}")

        created = 0
        updated = 0

        for record in records:
            normalized_date = self._normalize_date(record.get("date"))
            internal_location_id = location_lookup[record["location_id"]]
            internal_type_id = item_lookup[record["type_id"]]
            row = session.scalar(
                select(AdamNpcDemandDaily).where(
                    AdamNpcDemandDaily.location_id == internal_location_id,
                    AdamNpcDemandDaily.type_id == internal_type_id,
                    AdamNpcDemandDaily.date == normalized_date,
                )
            )
            raw_payload = record.get("raw_payload", dict(record))
            source_label = record.get("source", "adam4eve")

            if row is None:
                session.add(
                    AdamNpcDemandDaily(
                        location_id=internal_location_id,
                        type_id=internal_type_id,
                        date=normalized_date,
                        demand_day=record["demand_day"],
                        source_label=source_label,
                        raw_payload=raw_payload,
                    )
                )
                created += 1
                continue

            row.demand_day = record["demand_day"]
            row.source_label = source_label
            row.raw_payload = raw_payload
            updated += 1

        session.commit()
        return AdamNpcDemandIngestionResult(
            records_processed=len(records),
            created=created,
            updated=updated,
        )

    def _normalize_date(self, value: str | date | None) -> date:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        return datetime.now(UTC).date()
