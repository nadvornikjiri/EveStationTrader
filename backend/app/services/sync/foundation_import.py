import io
import json
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar, cast

import httpx
from psycopg import Connection as PsycopgConnection
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories.seed_data import (
    CURATED_DEFAULT_USER_SETTINGS,
    CURATED_STRUCTURE_LOCATIONS,
    CURATED_TRACKED_STRUCTURES,
    FoundationSeedSource,
    ItemSeed,
    RegionSeed,
    StaticFoundationSeedSource,
    StationSeed,
    SystemSeed,
)
from app.services.sync.foundation_data import FoundationDataService, FoundationSeedResult


@dataclass(frozen=True)
class FoundationImportResult:
    records_processed: int
    result: FoundationSeedResult


T = TypeVar("T")


class CcpSdeClient:
    def __init__(self, static_data_jsonl_url: str | None = None) -> None:
        self.settings = get_settings()
        self.static_data_jsonl_url = static_data_jsonl_url or self.settings.ccp_static_data_jsonl_url

    def build_seed_source(self) -> FoundationSeedSource:
        zip_bytes = self._download_zip_bytes()
        return self._load_seed_source_from_zip_bytes(zip_bytes)

    def _download_zip_bytes(self) -> bytes:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            response = client.get(self.static_data_jsonl_url)
            response.raise_for_status()
            return response.content

    def _load_seed_source_from_zip_bytes(self, zip_bytes: bytes) -> FoundationSeedSource:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            regions = self._load_regions(self._read_jsonl_records(archive, "mapRegions.jsonl"))
            systems = self._load_systems(self._read_jsonl_records(archive, "mapSolarSystems.jsonl"))
            stations = self._load_stations(self._read_jsonl_records(archive, "npcStations.jsonl"), systems)
            categories = self._load_name_lookup(self._read_jsonl_records(archive, "categories.jsonl"))
            groups = self._load_group_lookup(self._read_jsonl_records(archive, "groups.jsonl"), categories)
            items = self._load_items(self._read_jsonl_records(archive, "types.jsonl"), groups)
            return StaticFoundationSeedSource(
                regions_data=regions,
                systems_data=systems,
                stations_data=stations,
                items_data=items,
                structure_locations_data=CURATED_STRUCTURE_LOCATIONS,
                tracked_structures_data=CURATED_TRACKED_STRUCTURES,
                default_user_settings_data=CURATED_DEFAULT_USER_SETTINGS,
            )

    def _read_jsonl_records(self, archive: zipfile.ZipFile, filename: str) -> list[dict[str, object]]:
        archive_name = self._find_archive_member(archive, filename)
        with archive.open(archive_name, "r") as handle:
            records: list[dict[str, object]] = []
            for raw_line in handle:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError(f"{filename} must contain JSON objects per line.")
                records.append(payload)
            return records

    def _find_archive_member(self, archive: zipfile.ZipFile, filename: str) -> str:
        for member_name in archive.namelist():
            if member_name == filename or member_name.endswith(f"/{filename}"):
                return member_name
        raise KeyError(f"Archive is missing required file {filename}.")

    def _load_regions(self, records: Iterable[dict[str, object]]) -> tuple[RegionSeed, ...]:
        rows = []
        for record in records:
            region_id = self._require_int(record, "_key")
            name = self._require_name(record.get("name"), fallback_key="regionName")
            rows.append(RegionSeed(region_id=region_id, name=name))
        return tuple(sorted(rows, key=lambda row: row.region_id))

    def _load_systems(self, records: Iterable[dict[str, object]]) -> tuple[SystemSeed, ...]:
        rows = []
        for record in records:
            system_id = self._require_int(record, "_key")
            region_id = self._require_int(record, "regionID")
            name = self._require_name(record.get("name"), fallback_key="solarSystemName")
            security_status = self._require_float(record, "securityStatus", fallback_key="security")
            rows.append(
                SystemSeed(
                    system_id=system_id,
                    region_id=region_id,
                    name=name,
                    security_status=security_status,
                )
            )
        return tuple(sorted(rows, key=lambda row: row.system_id))

    def _load_stations(
        self,
        records: Iterable[dict[str, object]],
        systems: tuple[SystemSeed, ...],
    ) -> tuple[StationSeed, ...]:
        system_region_ids = {system.system_id: system.region_id for system in systems}
        rows = []
        for record in records:
            station_id = self._require_int(record, "_key")
            system_id = self._require_int(record, "solarSystemID", fallback_key="systemID")
            region_id = system_region_ids.get(system_id)
            if region_id is None:
                continue
            rows.append(
                StationSeed(
                    station_id=station_id,
                    system_id=system_id,
                    region_id=region_id,
                    name=self._optional_name(record.get("name")) or f"Station {station_id}",
                )
            )
        return tuple(sorted(rows, key=lambda row: row.station_id))

    def _load_name_lookup(self, records: Iterable[dict[str, object]]) -> dict[int, str]:
        return {
            self._require_int(record, "_key"): self._require_name(record.get("name"))
            for record in records
        }

    def _load_group_lookup(
        self,
        records: Iterable[dict[str, object]],
        categories: dict[int, str],
    ) -> dict[int, tuple[str | None, str | None]]:
        lookup: dict[int, tuple[str | None, str | None]] = {}
        for record in records:
            group_id = self._require_int(record, "_key")
            category_id = self._require_int(record, "categoryID")
            lookup[group_id] = (
                self._require_name(record.get("name")),
                categories.get(category_id),
            )
        return lookup

    def _load_items(
        self,
        records: Iterable[dict[str, object]],
        groups: dict[int, tuple[str | None, str | None]],
    ) -> tuple[ItemSeed, ...]:
        rows = []
        for record in records:
            if not self._is_truthy(record.get("published")):
                continue
            if record.get("marketGroupID") is None:
                continue
            type_id = self._require_int(record, "_key")
            group_id = self._require_int(record, "groupID")
            group_name, category_name = groups.get(group_id, (None, None))
            if category_name == "Blueprint":
                continue
            rows.append(
                ItemSeed(
                    type_id=type_id,
                    name=self._require_name(record.get("name"), fallback_key="typeName"),
                    volume_m3=self._require_float(record, "volume"),
                    group_name=group_name,
                    category_name=category_name,
                )
            )
        return tuple(sorted(rows, key=lambda row: row.type_id))

    def _require_int(self, record: dict[str, object], key: str, *, fallback_key: str | None = None) -> int:
        value = record.get(key, record.get(fallback_key) if fallback_key else None)
        if isinstance(value, int):
            return value
        raise ValueError(f"Expected integer field '{key}'.")

    def _require_float(self, record: dict[str, object], key: str, *, fallback_key: str | None = None) -> float:
        value = record.get(key, record.get(fallback_key) if fallback_key else None)
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    def _require_name(self, value: object, *, fallback_key: str | None = None) -> str:
        name = self._optional_name(value)
        if name:
            return name
        if fallback_key is not None and isinstance(value, dict):
            fallback_value = value.get(fallback_key)
            if isinstance(fallback_value, str) and fallback_value:
                return fallback_value
        raise ValueError("Expected localized name payload.")

    def _optional_name(self, value: object) -> str | None:
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            english = value.get("en")
            if isinstance(english, str) and english:
                return english
        return None

    def _is_truthy(self, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        return False


class FoundationImportService:
    CANCELLATION_CHECK_INTERVAL = 100

    def import_from_seed_source(
        self,
        session: Session,
        *,
        seed_source: FoundationSeedSource,
        cancellation_check: Callable[[], None] | None = None,
    ) -> FoundationImportResult:
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            foundation_result = self._import_via_postgres_copy(
                session,
                seed_source=seed_source,
                cancellation_check=cancellation_check,
            )
        else:
            foundation_result = FoundationDataService(seed_source=seed_source).bootstrap(
                session,
                cancellation_check=cancellation_check,
            )
        return FoundationImportResult(
            records_processed=foundation_result.records_processed,
            result=foundation_result,
        )

    def _import_via_postgres_copy(
        self,
        session: Session,
        *,
        seed_source: FoundationSeedSource,
        cancellation_check: Callable[[], None] | None,
    ) -> FoundationSeedResult:
        result = FoundationSeedResult()
        connection = session.connection()
        raw_connection = cast(PsycopgConnection, connection.connection.driver_connection)
        cursor = raw_connection.cursor()

        regions = self._materialize(seed_source.regions(), cancellation_check=cancellation_check)
        systems = self._materialize(seed_source.systems(), cancellation_check=cancellation_check)
        stations = self._materialize(seed_source.stations(), cancellation_check=cancellation_check)
        items = self._materialize(seed_source.items(), cancellation_check=cancellation_check)
        structure_locations = self._materialize(
            seed_source.structure_locations().items(),
            cancellation_check=cancellation_check,
        )
        tracked_structures = self._materialize(seed_source.tracked_structures(), cancellation_check=cancellation_check)

        self._create_staging_tables(cursor)

        self._copy_rows(
            cursor,
            "tmp_foundation_regions",
            ("region_id", "name"),
            ((row.region_id, row.name) for row in regions),
            cancellation_check=cancellation_check,
        )
        self._copy_rows(
            cursor,
            "tmp_foundation_systems",
            ("system_id", "region_id", "name", "security_status"),
            ((row.system_id, row.region_id, row.name, row.security_status) for row in systems),
            cancellation_check=cancellation_check,
        )
        self._copy_rows(
            cursor,
            "tmp_foundation_stations",
            ("station_id", "system_id", "region_id", "name"),
            ((row.station_id, row.system_id, row.region_id, row.name) for row in stations),
            cancellation_check=cancellation_check,
        )
        self._copy_rows(
            cursor,
            "tmp_foundation_items",
            ("type_id", "name", "volume_m3", "group_name", "category_name"),
            ((row.type_id, row.name, row.volume_m3, row.group_name, row.category_name) for row in items),
            cancellation_check=cancellation_check,
        )
        self._copy_rows(
            cursor,
            "tmp_foundation_structure_locations",
            ("structure_id", "system_id", "region_id", "name"),
            (
                (structure_id, metadata.system_id, metadata.region_id, metadata.name)
                for structure_id, metadata in structure_locations
            ),
            cancellation_check=cancellation_check,
        )
        self._copy_rows(
            cursor,
            "tmp_foundation_tracked_structures",
            ("structure_id", "name", "tracking_tier", "poll_interval_minutes", "notes"),
            (
                (
                    row.structure_id,
                    row.name,
                    row.tracking_tier,
                    10 if row.tracking_tier == "core" else 30,
                    "Seeded built-in trade hub",
                )
                for row in tracked_structures
            ),
            cancellation_check=cancellation_check,
        )

        result.regions = self._count_inserted(
            connection,
            """
            WITH inserted AS (
                INSERT INTO regions (region_id, name)
                SELECT region_id, name
                FROM tmp_foundation_regions
                ON CONFLICT (region_id) DO NOTHING
                RETURNING 1
            )
            SELECT count(*) FROM inserted
            """,
        )
        result.systems = self._count_inserted(
            connection,
            """
            WITH inserted AS (
                INSERT INTO systems (system_id, region_id, name, security_status)
                SELECT staging.system_id, regions.id, staging.name, staging.security_status
                FROM tmp_foundation_systems AS staging
                JOIN regions ON regions.region_id = staging.region_id
                ON CONFLICT (system_id) DO NOTHING
                RETURNING 1
            )
            SELECT count(*) FROM inserted
            """,
        )
        result.stations = self._count_inserted(
            connection,
            """
            WITH inserted AS (
                INSERT INTO stations (station_id, system_id, region_id, name)
                SELECT staging.station_id, systems.id, regions.id, staging.name
                FROM tmp_foundation_stations AS staging
                JOIN systems ON systems.system_id = staging.system_id
                JOIN regions ON regions.region_id = staging.region_id
                ON CONFLICT (station_id) DO NOTHING
                RETURNING 1
            )
            SELECT count(*) FROM inserted
            """,
        )
        result.locations = self._count_inserted(
            connection,
            """
            WITH inserted AS (
                INSERT INTO locations (location_id, location_type, system_id, region_id, name)
                SELECT staging.station_id, 'npc_station', systems.id, regions.id, staging.name
                FROM tmp_foundation_stations AS staging
                JOIN systems ON systems.system_id = staging.system_id
                JOIN regions ON regions.region_id = staging.region_id
                ON CONFLICT (location_id) DO NOTHING
                RETURNING 1
            )
            SELECT count(*) FROM inserted
            """,
        )
        result.items = self._count_inserted(
            connection,
            """
            WITH inserted AS (
                INSERT INTO items (type_id, name, volume_m3, group_name, category_name)
                SELECT type_id, name, volume_m3, group_name, category_name
                FROM tmp_foundation_items
                ON CONFLICT (type_id) DO NOTHING
                RETURNING 1
            )
            SELECT count(*) FROM inserted
            """,
        )
        result.locations += self._count_inserted(
            connection,
            """
            WITH inserted AS (
                INSERT INTO locations (location_id, location_type, system_id, region_id, name)
                SELECT staging.structure_id, 'structure', systems.id, regions.id, staging.name
                FROM tmp_foundation_structure_locations AS staging
                JOIN systems ON systems.system_id = staging.system_id
                JOIN regions ON regions.region_id = staging.region_id
                ON CONFLICT (location_id) DO NOTHING
                RETURNING 1
            )
            SELECT count(*) FROM inserted
            """,
        )
        result.tracked_structures = self._count_inserted(
            connection,
            """
            WITH inserted AS (
                INSERT INTO tracked_structures (
                    structure_id,
                    name,
                    system_id,
                    region_id,
                    tracking_tier,
                    poll_interval_minutes,
                    is_enabled,
                    confidence_score,
                    notes
                )
                SELECT
                    tracked.structure_id,
                    tracked.name,
                    systems.id,
                    regions.id,
                    tracked.tracking_tier,
                    tracked.poll_interval_minutes,
                    TRUE,
                    0.0,
                    tracked.notes
                FROM tmp_foundation_tracked_structures AS tracked
                JOIN tmp_foundation_structure_locations AS locations
                    ON locations.structure_id = tracked.structure_id
                JOIN systems ON systems.system_id = locations.system_id
                JOIN regions ON regions.region_id = locations.region_id
                ON CONFLICT (structure_id) DO NOTHING
                RETURNING 1
            )
            SELECT count(*) FROM inserted
            """,
        )

        existing_defaults = connection.exec_driver_sql(
            "SELECT 1 FROM user_settings WHERE user_id IS NULL AND key = 'defaults'"
        ).scalar()
        if existing_defaults is None:
            connection.exec_driver_sql(
                """
                INSERT INTO user_settings (user_id, key, value, updated_at)
                VALUES (NULL, 'defaults', %(value)s::jsonb, NOW())
                """,
                {"value": json.dumps(dict(seed_source.default_user_settings()))},
            )
            result.default_settings = 1

        session.commit()
        session.expire_all()
        return result

    def _create_staging_tables(self, cursor) -> None:
        cursor.execute(
            """
            CREATE TEMP TABLE tmp_foundation_regions (
                region_id INTEGER NOT NULL,
                name TEXT NOT NULL
            ) ON COMMIT DROP;

            CREATE TEMP TABLE tmp_foundation_systems (
                system_id INTEGER NOT NULL,
                region_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                security_status DOUBLE PRECISION NOT NULL
            ) ON COMMIT DROP;

            CREATE TEMP TABLE tmp_foundation_stations (
                station_id BIGINT NOT NULL,
                system_id INTEGER NOT NULL,
                region_id INTEGER NOT NULL,
                name TEXT NOT NULL
            ) ON COMMIT DROP;

            CREATE TEMP TABLE tmp_foundation_items (
                type_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                volume_m3 DOUBLE PRECISION NOT NULL,
                group_name TEXT NULL,
                category_name TEXT NULL
            ) ON COMMIT DROP;

            CREATE TEMP TABLE tmp_foundation_structure_locations (
                structure_id BIGINT NOT NULL,
                system_id INTEGER NOT NULL,
                region_id INTEGER NOT NULL,
                name TEXT NOT NULL
            ) ON COMMIT DROP;

            CREATE TEMP TABLE tmp_foundation_tracked_structures (
                structure_id BIGINT NOT NULL,
                name TEXT NOT NULL,
                tracking_tier TEXT NOT NULL,
                poll_interval_minutes INTEGER NOT NULL,
                notes TEXT NOT NULL
            ) ON COMMIT DROP;
            """
        )

    def _copy_rows(
        self,
        cursor,
        table_name: str,
        columns: tuple[str, ...],
        rows,
        *,
        cancellation_check: Callable[[], None] | None,
    ) -> None:
        copy_sql = f"COPY {table_name} ({', '.join(columns)}) FROM STDIN"
        with cursor.copy(copy_sql) as copy:
            for index, row in enumerate(rows, start=1):
                if cancellation_check is not None and index % self.CANCELLATION_CHECK_INTERVAL == 0:
                    cancellation_check()
                copy.write_row(row)

    def _count_inserted(self, connection, sql: str) -> int:
        value = connection.exec_driver_sql(sql).scalar()
        return int(value or 0)

    def _materialize(
        self,
        rows: Iterable[T],
        *,
        cancellation_check: Callable[[], None] | None,
    ) -> list[T]:
        materialized: list[T] = []
        for index, row in enumerate(rows, start=1):
            if cancellation_check is not None and index % self.CANCELLATION_CHECK_INTERVAL == 0:
                cancellation_check()
            materialized.append(row)
        return materialized
