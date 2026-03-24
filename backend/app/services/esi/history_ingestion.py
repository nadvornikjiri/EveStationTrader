from dataclasses import dataclass
from datetime import date
from typing import TypedDict

from sqlalchemy import delete, select, tuple_
from sqlalchemy.orm import Session

from app.models.all_models import EsiHistoryDaily, Item, Region
from app.services.postgres_copy import copy_rows


class EsiRegionalHistoryRecord(TypedDict):
    type_id: int
    date: str | date
    average: float
    highest: float
    lowest: float
    order_count: int
    volume: int


@dataclass
class EsiRegionalHistoryIngestionResult:
    region_id: int
    records_processed: int
    created: int
    updated: int


class EsiRegionalHistoryIngestionService:
    def ingest_region_history(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[EsiRegionalHistoryRecord],
    ) -> EsiRegionalHistoryIngestionResult:
        if session.get_bind().dialect.name != "postgresql":
            return self._ingest_via_orm(session, eve_region_id=eve_region_id, records=records)
        return self._ingest_via_postgres_copy(session, eve_region_id=eve_region_id, records=records)

    def _ingest_via_postgres_copy(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[EsiRegionalHistoryRecord],
    ) -> EsiRegionalHistoryIngestionResult:
        region = session.scalar(select(Region).where(Region.region_id == eve_region_id))
        if region is None:
            raise ValueError(f"eve_region_id {eve_region_id} was not found")

        if not records:
            session.commit()
            return EsiRegionalHistoryIngestionResult(region_id=region.id, records_processed=0, created=0, updated=0)

        external_type_ids = sorted({record["type_id"] for record in records})
        item_lookup = {
            item.type_id: item.id
            for item in session.scalars(select(Item).where(Item.type_id.in_(external_type_ids))).all()
        }
        missing_type_ids = [type_id for type_id in external_type_ids if type_id not in item_lookup]
        if missing_type_ids:
            missing = ", ".join(str(type_id) for type_id in missing_type_ids)
            raise ValueError(f"items were not found for type_ids: {missing}")

        normalized_rows: list[tuple[int, int, date, float, float, float, int, int]] = []
        row_keys: list[tuple[int, date]] = []
        for record in records:
            record_date = record["date"]
            normalized_date = date.fromisoformat(record_date) if isinstance(record_date, str) else record_date
            item_id = item_lookup[record["type_id"]]
            normalized_rows.append(
                (
                    region.id,
                    item_id,
                    normalized_date,
                    record["average"],
                    record["highest"],
                    record["lowest"],
                    record["order_count"],
                    record["volume"],
                )
            )
            row_keys.append((item_id, normalized_date))

        existing_keys = set(
            session.execute(
                select(EsiHistoryDaily.type_id, EsiHistoryDaily.date).where(
                    EsiHistoryDaily.region_id == region.id,
                    tuple_(EsiHistoryDaily.type_id, EsiHistoryDaily.date).in_(row_keys),
                )
            ).all()
        )
        updated = sum(1 for key in row_keys if key in existing_keys)
        created = len(row_keys) - updated

        session.execute(
            delete(EsiHistoryDaily).where(
                EsiHistoryDaily.region_id == region.id,
                tuple_(EsiHistoryDaily.type_id, EsiHistoryDaily.date).in_(row_keys),
            )
        )
        copy_rows(
            session,
            table_name="esi_history_daily",
            columns=("region_id", "type_id", "date", "average", "highest", "lowest", "order_count", "volume"),
            rows=normalized_rows,
        )

        session.commit()
        return EsiRegionalHistoryIngestionResult(
            region_id=region.id,
            records_processed=len(records),
            created=created,
            updated=updated,
        )

    def _ingest_via_orm(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[EsiRegionalHistoryRecord],
    ) -> EsiRegionalHistoryIngestionResult:
        region = session.scalar(select(Region).where(Region.region_id == eve_region_id))
        if region is None:
            raise ValueError(f"eve_region_id {eve_region_id} was not found")

        external_type_ids = sorted({record["type_id"] for record in records})
        item_lookup = {
            item.type_id: item.id
            for item in session.scalars(select(Item).where(Item.type_id.in_(external_type_ids))).all()
        }
        missing_type_ids = [type_id for type_id in external_type_ids if type_id not in item_lookup]
        if missing_type_ids:
            missing = ", ".join(str(type_id) for type_id in missing_type_ids)
            raise ValueError(f"items were not found for type_ids: {missing}")

        created = 0
        updated = 0

        for record in records:
            record_date = record["date"]
            normalized_date = date.fromisoformat(record_date) if isinstance(record_date, str) else record_date
            item_id = item_lookup[record["type_id"]]
            row = session.scalar(
                select(EsiHistoryDaily).where(
                    EsiHistoryDaily.region_id == region.id,
                    EsiHistoryDaily.type_id == item_id,
                    EsiHistoryDaily.date == normalized_date,
                )
            )

            if row is None:
                session.add(
                    EsiHistoryDaily(
                        region_id=region.id,
                        type_id=item_id,
                        date=normalized_date,
                        average=record["average"],
                        highest=record["highest"],
                        lowest=record["lowest"],
                        order_count=record["order_count"],
                        volume=record["volume"],
                    )
                )
                created += 1
                continue

            row.average = record["average"]
            row.highest = record["highest"]
            row.lowest = record["lowest"]
            row.order_count = record["order_count"]
            row.volume = record["volume"]
            updated += 1

        session.commit()
        return EsiRegionalHistoryIngestionResult(
            region_id=region.id,
            records_processed=len(records),
            created=created,
            updated=updated,
        )
