from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.enums import LocationType
from app.models.all_models import EsiMarketOrder, Item, Location, Region, Station, System
from app.repositories.seed_data import StationSeed
from app.services.esi.client import EsiRegionalOrderRecord
from app.services.postgres_copy import copy_rows


class OrderMetadataCapableUniverseClient(Protocol):
    def fetch_station(self, station_id: int) -> StationSeed: ...


@dataclass(frozen=True)
class EsiMarketOrderIngestionResult:
    region_id: int
    records_processed: int
    created: int
    updated: int
    deleted: int
    stations_created: int
    items_created: int
    skipped_missing_items: int
    skipped_non_npc_locations: int


class EsiRegionalOrderIngestionService:
    def ingest_region_orders(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[EsiRegionalOrderRecord],
        universe_client: OrderMetadataCapableUniverseClient,
        cancellation_check: Callable[[], None] | None = None,
    ) -> EsiMarketOrderIngestionResult:
        if session.get_bind().dialect.name != "postgresql":
            return self._ingest_via_orm(
                session,
                eve_region_id=eve_region_id,
                records=records,
                universe_client=universe_client,
                cancellation_check=cancellation_check,
            )
        return self._ingest_via_postgres_copy(
            session,
            eve_region_id=eve_region_id,
            records=records,
            universe_client=universe_client,
            cancellation_check=cancellation_check,
        )

    def _ingest_via_postgres_copy(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[EsiRegionalOrderRecord],
        universe_client: OrderMetadataCapableUniverseClient,
        cancellation_check: Callable[[], None] | None = None,
    ) -> EsiMarketOrderIngestionResult:
        region = session.scalar(select(Region).where(Region.region_id == eve_region_id))
        if region is None:
            raise ValueError(f"Cannot ingest regional orders for unknown region {eve_region_id}.")

        item_lookup = {
            item.type_id: item.id
            for item in session.scalars(select(Item).where(Item.type_id.in_({record["type_id"] for record in records}))).all()
        }
        existing_order_ids = set(
            session.scalars(select(EsiMarketOrder.order_id).where(EsiMarketOrder.region_id == region.id)).all()
        )

        stations_created = 0
        items_created = 0
        skipped_missing_items = 0
        skipped_non_npc_locations = 0
        seen_order_ids: set[int] = set()
        normalized_rows: list[tuple[object, ...]] = []
        location_cache: dict[int, Location | None] = {}

        for record in records:
            if cancellation_check is not None:
                cancellation_check()

            item_id = item_lookup.get(record["type_id"])
            if item_id is None:
                skipped_missing_items += 1
                continue

            if record["location_id"] in location_cache:
                location = location_cache[record["location_id"]]
                station_was_created = False
            else:
                location, station_was_created = self._ensure_station_location(
                    session,
                    eve_region_id=eve_region_id,
                    station_id=record["location_id"],
                    system_id=record["system_id"],
                    universe_client=universe_client,
                )
                location_cache[record["location_id"]] = location

            if location is None:
                skipped_non_npc_locations += 1
                continue

            stations_created += int(station_was_created)
            seen_order_ids.add(record["order_id"])
            normalized_rows.append(
                (
                    record["order_id"],
                    region.id,
                    location.id,
                    item_id,
                    location.system_id,
                    record["is_buy_order"],
                    record["price"],
                    record["volume_total"],
                    record["volume_remain"],
                    record["min_volume"],
                    record["range"],
                    datetime.fromisoformat(record["issued"]).astimezone(UTC),
                    record["duration"],
                    datetime.now(UTC),
                )
            )

        updated = len(existing_order_ids & seen_order_ids)
        created = len(seen_order_ids) - updated
        deleted = len(existing_order_ids - seen_order_ids)

        if seen_order_ids:
            session.execute(
                delete(EsiMarketOrder).where(
                    (EsiMarketOrder.region_id == region.id) | EsiMarketOrder.order_id.in_(seen_order_ids)
                )
            )
        else:
            session.execute(delete(EsiMarketOrder).where(EsiMarketOrder.region_id == region.id))

        if normalized_rows:
            copy_rows(
                session,
                table_name="esi_market_orders",
                columns=(
                    "order_id",
                    "region_id",
                    "location_id",
                    "type_id",
                    "system_id",
                    "is_buy_order",
                    "price",
                    "volume_total",
                    "volume_remain",
                    "min_volume",
                    "order_range",
                    "issued",
                    "duration",
                    "updated_at",
                ),
                rows=normalized_rows,
            )

        session.commit()
        return EsiMarketOrderIngestionResult(
            region_id=region.id,
            records_processed=len(records),
            created=created,
            updated=updated,
            deleted=deleted,
            stations_created=stations_created,
            items_created=items_created,
            skipped_missing_items=skipped_missing_items,
            skipped_non_npc_locations=skipped_non_npc_locations,
        )

    def _ingest_via_orm(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[EsiRegionalOrderRecord],
        universe_client: OrderMetadataCapableUniverseClient,
        cancellation_check: Callable[[], None] | None = None,
    ) -> EsiMarketOrderIngestionResult:
        region = session.scalar(select(Region).where(Region.region_id == eve_region_id))
        if region is None:
            raise ValueError(f"Cannot ingest regional orders for unknown region {eve_region_id}.")

        created = 0
        updated = 0
        stations_created = 0
        items_created = 0
        skipped_missing_items = 0
        skipped_non_npc_locations = 0
        seen_order_ids: set[int] = set()

        for record in records:
            if cancellation_check is not None:
                cancellation_check()
            item = session.scalar(select(Item).where(Item.type_id == record["type_id"]))
            if item is None:
                skipped_missing_items += 1
                continue

            location, station_was_created = self._ensure_station_location(
                session,
                eve_region_id=eve_region_id,
                station_id=record["location_id"],
                system_id=record["system_id"],
                universe_client=universe_client,
            )
            if location is None:
                skipped_non_npc_locations += 1
                continue
            stations_created += int(station_was_created)
            seen_order_ids.add(record["order_id"])

            existing = session.scalar(select(EsiMarketOrder).where(EsiMarketOrder.order_id == record["order_id"]))
            issued_at = datetime.fromisoformat(record["issued"]).astimezone(UTC)
            if existing is None:
                session.add(
                    EsiMarketOrder(
                        order_id=record["order_id"],
                        region_id=region.id,
                        location_id=location.id,
                        type_id=item.id,
                        system_id=location.system_id,
                        is_buy_order=record["is_buy_order"],
                        price=record["price"],
                        volume_total=record["volume_total"],
                        volume_remain=record["volume_remain"],
                        min_volume=record["min_volume"],
                        order_range=record["range"],
                        issued=issued_at,
                        duration=record["duration"],
                    )
                )
                created += 1
                continue

            existing.region_id = region.id
            existing.location_id = location.id
            existing.type_id = item.id
            existing.system_id = location.system_id
            existing.is_buy_order = record["is_buy_order"]
            existing.price = record["price"]
            existing.volume_total = record["volume_total"]
            existing.volume_remain = record["volume_remain"]
            existing.min_volume = record["min_volume"]
            existing.order_range = record["range"]
            existing.issued = issued_at
            existing.duration = record["duration"]
            updated += 1

        deleted = self._delete_stale_orders(session, region_id=region.id, seen_order_ids=seen_order_ids)
        session.commit()
        return EsiMarketOrderIngestionResult(
            region_id=region.id,
            records_processed=len(records),
            created=created,
            updated=updated,
            deleted=deleted,
            stations_created=stations_created,
            items_created=items_created,
            skipped_missing_items=skipped_missing_items,
            skipped_non_npc_locations=skipped_non_npc_locations,
        )

    def _delete_stale_orders(self, session: Session, *, region_id: int, seen_order_ids: set[int]) -> int:
        existing_order_ids = list(
            session.scalars(select(EsiMarketOrder.order_id).where(EsiMarketOrder.region_id == region_id)).all()
        )
        stale_order_ids = [order_id for order_id in existing_order_ids if order_id not in seen_order_ids]
        if not stale_order_ids:
            return 0

        session.execute(delete(EsiMarketOrder).where(EsiMarketOrder.order_id.in_(stale_order_ids)))
        return len(stale_order_ids)

    def _ensure_station_location(
        self,
        session: Session,
        *,
        eve_region_id: int,
        station_id: int,
        system_id: int,
        universe_client: OrderMetadataCapableUniverseClient,
    ) -> tuple[Location | None, bool]:
        existing_location = session.scalar(select(Location).where(Location.location_id == station_id))
        if existing_location is not None:
            if existing_location.location_type != LocationType.NPC_STATION.value:
                return None, False
            return existing_location, False

        if station_id >= 1_000_000_000_000:
            return None, False

        try:
            station_seed = universe_client.fetch_station(station_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {400, 404}:
                return None, False
            raise
        target_system_id = station_seed.system_id or system_id
        system = session.scalar(select(System).where(System.system_id == target_system_id))
        if system is None:
            raise ValueError(
                f"Cannot ingest station {station_id} because system {target_system_id} is missing from foundation data."
            )

        station = session.scalar(select(Station).where(Station.station_id == station_id))
        if station is None:
            session.add(
                Station(
                    station_id=station_seed.station_id,
                    system_id=system.id,
                    region_id=system.region_id,
                    name=station_seed.name,
                )
            )

        location = Location(
            location_id=station_seed.station_id,
            location_type=LocationType.NPC_STATION.value,
            system_id=system.id,
            region_id=system.region_id,
            name=station_seed.name,
        )
        session.add(location)
        session.flush()

        region = session.scalar(select(Region).where(Region.region_id == eve_region_id))
        if region is None:
            raise ValueError(f"Unknown region {eve_region_id} while ingesting station {station_id}.")
        location.region_id = region.id
        return location, True
