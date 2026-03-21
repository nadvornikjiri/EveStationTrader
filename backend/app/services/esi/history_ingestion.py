from dataclasses import dataclass
from datetime import date
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import EsiHistoryDaily, Item, Region


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
