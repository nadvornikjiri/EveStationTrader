from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import httpx
from sqlalchemy import delete, select, text
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
    delta_count: int = 0


@dataclass(frozen=True)
class EsiRegionOrderBatch:
    region_id: int
    eve_region_id: int
    records: list[EsiRegionalOrderRecord]


class EsiRegionalOrderIngestionService:
    DELETE_BATCH_SIZE = 5_000

    def ingest_order_batches(
        self,
        session: Session,
        *,
        region_batches: Sequence[EsiRegionOrderBatch],
        universe_client: OrderMetadataCapableUniverseClient,
        cancellation_check: Callable[[], None] | None = None,
        target_location_ids: set[int] | None = None,
    ) -> EsiMarketOrderIngestionResult:
        if not region_batches:
            return EsiMarketOrderIngestionResult(
                region_id=0,
                records_processed=0,
                created=0,
                updated=0,
                deleted=0,
                stations_created=0,
                items_created=0,
                skipped_missing_items=0,
                skipped_non_npc_locations=0,
            )
        if session.get_bind().dialect.name != "postgresql":
            aggregate = EsiMarketOrderIngestionResult(
                region_id=0,
                records_processed=0,
                created=0,
                updated=0,
                deleted=0,
                stations_created=0,
                items_created=0,
                skipped_missing_items=0,
                skipped_non_npc_locations=0,
            )
            for batch in region_batches:
                result = self._ingest_via_orm(
                    session,
                    eve_region_id=batch.eve_region_id,
                    records=batch.records,
                    universe_client=universe_client,
                    cancellation_check=cancellation_check,
                )
                aggregate = EsiMarketOrderIngestionResult(
                    region_id=0,
                    records_processed=aggregate.records_processed + result.records_processed,
                    created=aggregate.created + result.created,
                    updated=aggregate.updated + result.updated,
                    deleted=aggregate.deleted + result.deleted,
                    stations_created=aggregate.stations_created + result.stations_created,
                    items_created=aggregate.items_created + result.items_created,
                    skipped_missing_items=aggregate.skipped_missing_items + result.skipped_missing_items,
                    skipped_non_npc_locations=aggregate.skipped_non_npc_locations + result.skipped_non_npc_locations,
                )
            return aggregate
        return self._ingest_batches_via_postgres_copy(
            session,
            region_batches=region_batches,
            universe_client=universe_client,
            cancellation_check=cancellation_check,
            target_location_ids=target_location_ids,
        )

    def ingest_region_orders(
        self,
        session: Session,
        *,
        eve_region_id: int,
        records: list[EsiRegionalOrderRecord],
        universe_client: OrderMetadataCapableUniverseClient,
        cancellation_check: Callable[[], None] | None = None,
    ) -> EsiMarketOrderIngestionResult:
        return self.ingest_order_batches(
            session,
            region_batches=[EsiRegionOrderBatch(region_id=self._require_region_id(session, eve_region_id), eve_region_id=eve_region_id, records=records)],
            universe_client=universe_client,
            cancellation_check=cancellation_check,
        )

    def _require_region_id(self, session: Session, eve_region_id: int) -> int:
        region = session.scalar(select(Region).where(Region.region_id == eve_region_id))
        if region is None:
            raise ValueError(f"Cannot ingest regional orders for unknown region {eve_region_id}.")
        return region.id

    def _ingest_batches_via_postgres_copy(
        self,
        session: Session,
        *,
        region_batches: Sequence[EsiRegionOrderBatch],
        universe_client: OrderMetadataCapableUniverseClient,
        cancellation_check: Callable[[], None] | None = None,
        target_location_ids: set[int] | None = None,
    ) -> EsiMarketOrderIngestionResult:
        region_ids = sorted({batch.region_id for batch in region_batches})
        if not region_ids:
            return EsiMarketOrderIngestionResult(
                region_id=0,
                records_processed=0,
                created=0,
                updated=0,
                deleted=0,
                stations_created=0,
                items_created=0,
                skipped_missing_items=0,
                skipped_non_npc_locations=0,
            )

        total_records = sum(len(batch.records) for batch in region_batches)
        self._prepare_stage_tables(session)
        station_rows = self._collect_unique_station_rows(region_batches)
        stations_created = self._ensure_station_locations_for_batches(
            session,
            station_rows=station_rows,
            universe_client=universe_client,
            cancellation_check=cancellation_check,
        )
        copy_rows(
            session,
            table_name="esi_market_orders_stage",
            columns=(
                "region_id",
                "eve_region_id",
                "order_id",
                "external_type_id",
                "external_location_id",
                "external_system_id",
                "is_buy_order",
                "price",
                "volume_total",
                "volume_remain",
                "min_volume",
                "order_range",
                "issued",
                "duration",
            ),
            rows=(
                (
                    batch.region_id,
                    batch.eve_region_id,
                    record["order_id"],
                    record["type_id"],
                    record["location_id"],
                    record["system_id"],
                    record["is_buy_order"],
                    record["price"],
                    record["volume_total"],
                    record["volume_remain"],
                    record["min_volume"],
                    record["range"],
                    datetime.fromisoformat(record["issued"]).astimezone(UTC),
                    record["duration"],
                )
                for batch in region_batches
                for record in batch.records
            ),
        )
        self._materialize_valid_stage(session)

        skipped_missing_items = int(
            session.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM esi_market_orders_stage AS stage
                    LEFT JOIN items ON items.type_id = stage.external_type_id
                    WHERE items.id IS NULL
                    """
                )
            )
            or 0
        )
        skipped_non_npc_locations = int(
            session.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM esi_market_orders_stage AS stage
                    JOIN items ON items.type_id = stage.external_type_id
                    LEFT JOIN locations
                      ON locations.location_id = stage.external_location_id
                    WHERE locations.id IS NULL
                    """
                ),
            )
            or 0
        )
        valid_count = int(session.scalar(text("SELECT COUNT(*) FROM esi_market_orders_valid_stage")) or 0)
        updated = int(
            session.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM esi_market_orders_valid_stage AS valid
                    JOIN esi_market_orders AS existing
                      ON existing.order_id = valid.order_id
                    """
                )
            )
            or 0
        )
        created = valid_count - updated
        deleted = int(
            session.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM esi_market_orders AS existing
                    WHERE existing.region_id IN (
                        SELECT DISTINCT region_id FROM esi_market_orders_stage
                    )
                      AND NOT EXISTS (
                        SELECT 1
                        FROM esi_market_orders_valid_stage AS valid
                        WHERE valid.order_id = existing.order_id
                    )
                    """
                )
            )
            or 0
        )

        # Compute order book deltas at target stations BEFORE deleting old orders.
        # Both esi_market_orders (old) and esi_market_orders_valid_stage (new) are
        # available at this point, enabling a sorted merge-diff per station.
        delta_count = 0
        if target_location_ids:
            from app.services.npc_stations.deltas import NpcStationDeltaService

            delta_result = NpcStationDeltaService().compute_and_persist_deltas(
                session,
                target_location_ids=list(target_location_ids),
                snapshot_time=datetime.now(UTC),
            )
            delta_count = delta_result.delta_count

        session.execute(delete(EsiMarketOrder).where(EsiMarketOrder.region_id.in_(region_ids)))
        session.execute(
            text(
                """
                INSERT INTO esi_market_orders (
                    order_id,
                    region_id,
                    location_id,
                    type_id,
                    system_id,
                    is_buy_order,
                    price,
                    volume_total,
                    volume_remain,
                    min_volume,
                    order_range,
                    issued,
                    duration,
                    updated_at
                )
                SELECT
                    order_id,
                    region_id,
                    location_id,
                    type_id,
                    system_id,
                    is_buy_order,
                    price,
                    volume_total,
                    volume_remain,
                    min_volume,
                    order_range,
                    issued,
                    duration,
                    updated_at
                FROM esi_market_orders_valid_stage
                """
            )
        )

        session.commit()
        return EsiMarketOrderIngestionResult(
            region_id=0,
            records_processed=total_records,
            created=created,
            updated=updated,
            deleted=deleted,
            stations_created=stations_created,
            items_created=0,
            skipped_missing_items=skipped_missing_items,
            skipped_non_npc_locations=skipped_non_npc_locations,
            delta_count=delta_count,
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
            self._delete_orders_by_ids(session, order_ids=seen_order_ids)
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

    def _prepare_stage_tables(self, session: Session) -> None:
        session.execute(
            text(
                """
                CREATE TEMP TABLE IF NOT EXISTS esi_market_orders_stage (
                    region_id INTEGER NOT NULL,
                    eve_region_id INTEGER NOT NULL,
                    order_id BIGINT NOT NULL,
                    external_type_id INTEGER NOT NULL,
                    external_location_id BIGINT NOT NULL,
                    external_system_id INTEGER NOT NULL,
                    is_buy_order BOOLEAN NOT NULL,
                    price DOUBLE PRECISION NOT NULL,
                    volume_total INTEGER NOT NULL,
                    volume_remain INTEGER NOT NULL,
                    min_volume INTEGER NOT NULL,
                    order_range TEXT NOT NULL,
                    issued TIMESTAMP WITH TIME ZONE NOT NULL,
                    duration INTEGER NOT NULL
                ) ON COMMIT DROP
                """
            )
        )
        session.execute(text("TRUNCATE TABLE esi_market_orders_stage"))
        session.execute(
            text(
                """
                CREATE TEMP TABLE IF NOT EXISTS esi_market_orders_valid_stage (
                    order_id BIGINT NOT NULL,
                    region_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    type_id INTEGER NOT NULL,
                    system_id INTEGER NOT NULL,
                    is_buy_order BOOLEAN NOT NULL,
                    price DOUBLE PRECISION NOT NULL,
                    volume_total INTEGER NOT NULL,
                    volume_remain INTEGER NOT NULL,
                    min_volume INTEGER NOT NULL,
                    order_range TEXT NOT NULL,
                    issued TIMESTAMP WITH TIME ZONE NOT NULL,
                    duration INTEGER NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
                ) ON COMMIT DROP
                """
            )
        )
        session.execute(text("TRUNCATE TABLE esi_market_orders_valid_stage"))

    def _materialize_valid_stage(self, session: Session) -> None:
        session.execute(
            text(
                """
                INSERT INTO esi_market_orders_valid_stage (
                    order_id,
                    region_id,
                    location_id,
                    type_id,
                    system_id,
                    is_buy_order,
                    price,
                    volume_total,
                    volume_remain,
                    min_volume,
                    order_range,
                    issued,
                    duration,
                    updated_at
                )
                SELECT DISTINCT ON (stage.order_id)
                    stage.order_id,
                    stage.region_id,
                    locations.id,
                    items.id,
                    locations.system_id,
                    stage.is_buy_order,
                    stage.price,
                    stage.volume_total,
                    stage.volume_remain,
                    stage.min_volume,
                    stage.order_range,
                    stage.issued,
                    stage.duration,
                    :updated_at
                FROM esi_market_orders_stage AS stage
                JOIN items
                  ON items.type_id = stage.external_type_id
                JOIN locations
                  ON locations.location_id = stage.external_location_id
                ORDER BY stage.order_id, stage.issued DESC, stage.region_id DESC, locations.id DESC
                """
            ),
            {
                "updated_at": datetime.now(UTC),
            },
        )

    @staticmethod
    def _collect_unique_station_rows(
        region_batches: Sequence[EsiRegionOrderBatch],
    ) -> list[tuple[int, int, int]]:
        unique_rows: dict[int, tuple[int, int, int]] = {}
        for batch in region_batches:
            for record in batch.records:
                location_id = record["location_id"]
                if location_id in unique_rows:
                    continue
                unique_rows[location_id] = (batch.eve_region_id, location_id, record["system_id"])
        return list(unique_rows.values())

    def _ensure_station_locations_for_batches(
        self,
        session: Session,
        *,
        station_rows: Sequence[tuple[int, int, int]],
        universe_client: OrderMetadataCapableUniverseClient,
        cancellation_check: Callable[[], None] | None = None,
    ) -> int:
        if not station_rows:
            return 0

        existing_locations = {
            location.location_id: location
            for location in session.scalars(
                select(Location).where(Location.location_id.in_([station_id for _, station_id, _ in station_rows]))
            ).all()
        }
        created = 0
        for eve_region_id, station_id, system_id in station_rows:
            if cancellation_check is not None:
                cancellation_check()
            if station_id in existing_locations:
                continue
            if station_id >= 1_000_000_000_000:
                location = self._ensure_structure_location(
                    session,
                    structure_id=station_id,
                    system_id=system_id,
                )
                if location is not None:
                    existing_locations[station_id] = location
                continue
            location, station_was_created = self._ensure_station_location(
                session,
                eve_region_id=eve_region_id,
                station_id=station_id,
                system_id=system_id,
                universe_client=universe_client,
            )
            if location is not None:
                existing_locations[station_id] = location
            created += int(station_was_created)
        return created

    def _ensure_structure_location(
        self,
        session: Session,
        *,
        structure_id: int,
        system_id: int,
    ) -> Location | None:
        existing_location = session.scalar(select(Location).where(Location.location_id == structure_id))
        if existing_location is not None:
            return existing_location

        system = session.scalar(select(System).where(System.system_id == system_id))
        if system is None:
            return None

        location = Location(
            location_id=structure_id,
            location_type=LocationType.STRUCTURE.value,
            system_id=system.id,
            region_id=system.region_id,
            name=f"Structure {structure_id}",
        )
        session.add(location)
        session.flush()
        return location

    def _delete_stale_orders(self, session: Session, *, region_id: int, seen_order_ids: set[int]) -> int:
        existing_order_ids = list(
            session.scalars(select(EsiMarketOrder.order_id).where(EsiMarketOrder.region_id == region_id)).all()
        )
        stale_order_ids = [order_id for order_id in existing_order_ids if order_id not in seen_order_ids]
        if not stale_order_ids:
            return 0

        self._delete_orders_by_ids(session, order_ids=stale_order_ids)
        return len(stale_order_ids)

    def _delete_orders_by_ids(self, session: Session, *, order_ids: set[int] | list[int]) -> None:
        normalized_ids = list(order_ids)
        for start in range(0, len(normalized_ids), self.DELETE_BATCH_SIZE):
            batch = normalized_ids[start : start + self.DELETE_BATCH_SIZE]
            session.execute(delete(EsiMarketOrder).where(EsiMarketOrder.order_id.in_(batch)))

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
