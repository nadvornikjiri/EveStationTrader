from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class RegionSeed:
    region_id: int
    name: str


@dataclass(frozen=True)
class SystemSeed:
    system_id: int
    region_id: int
    name: str
    security_status: float


@dataclass(frozen=True)
class StationSeed:
    station_id: int
    system_id: int
    region_id: int
    name: str


@dataclass(frozen=True)
class ItemSeed:
    type_id: int
    name: str
    volume_m3: float
    group_name: str | None
    category_name: str | None


@dataclass(frozen=True)
class StructureLocationSeed:
    system_id: int
    region_id: int
    name: str


@dataclass(frozen=True)
class TrackedStructureSeed:
    structure_id: int
    name: str
    tracking_tier: str


class FoundationSeedSource(Protocol):
    def regions(self) -> Sequence[RegionSeed]: ...

    def systems(self) -> Sequence[SystemSeed]: ...

    def stations(self) -> Sequence[StationSeed]: ...

    def items(self) -> Sequence[ItemSeed]: ...

    def structure_locations(self) -> Mapping[int, StructureLocationSeed]: ...

    def tracked_structures(self) -> Sequence[TrackedStructureSeed]: ...

    def default_user_settings(self) -> Mapping[str, object]: ...


class FoundationSnapshotError(ValueError):
    pass


@dataclass(frozen=True)
class _FoundationSnapshot:
    regions: tuple[RegionSeed, ...]
    systems: tuple[SystemSeed, ...]
    stations: tuple[StationSeed, ...]
    items: tuple[ItemSeed, ...]
    structure_locations: dict[int, StructureLocationSeed]
    tracked_structures: tuple[TrackedStructureSeed, ...]
    default_user_settings: dict[str, object]


VALID_TRACKING_TIERS = {"core", "secondary"}


def _require_mapping(snapshot: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = snapshot.get(key)
    if not isinstance(value, Mapping):
        raise FoundationSnapshotError(f"Foundation snapshot section '{key}' must be an object.")
    return value


def _require_sequence(snapshot: Mapping[str, object], key: str) -> Sequence[object]:
    value = snapshot.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise FoundationSnapshotError(f"Foundation snapshot section '{key}' must be an array.")
    return value


def _load_int(entry: Mapping[str, object], key: str, section: str) -> int:
    value = entry.get(key)
    if not isinstance(value, int):
        raise FoundationSnapshotError(f"Foundation snapshot '{section}' entry requires integer '{key}'.")
    return value


def _load_float(entry: Mapping[str, object], key: str, section: str) -> float:
    value = entry.get(key)
    if not isinstance(value, (int, float)):
        raise FoundationSnapshotError(f"Foundation snapshot '{section}' entry requires numeric '{key}'.")
    return float(value)


def _load_str(entry: Mapping[str, object], key: str, section: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str):
        raise FoundationSnapshotError(f"Foundation snapshot '{section}' entry requires string '{key}'.")
    return value


def _load_optional_str(entry: Mapping[str, object], key: str) -> str | None:
    value = entry.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise FoundationSnapshotError(f"Foundation snapshot entry field '{key}' must be a string or null.")
    return value


def _load_foundation_snapshot(snapshot_path: Path) -> _FoundationSnapshot:
    try:
        raw_document = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FoundationSnapshotError(f"Foundation snapshot file not found: {snapshot_path}") from exc
    except json.JSONDecodeError as exc:
        raise FoundationSnapshotError(f"Foundation snapshot file is not valid JSON: {snapshot_path}") from exc

    if not isinstance(raw_document, Mapping):
        raise FoundationSnapshotError("Foundation snapshot root must be a JSON object.")

    snapshot = raw_document

    regions = tuple(
        RegionSeed(
            region_id=_load_int(entry, "region_id", "regions"),
            name=_load_str(entry, "name", "regions"),
        )
        for entry in _require_sequence(snapshot, "regions")
        if isinstance(entry, Mapping)
    )
    _validate_entry_count(snapshot, "regions", regions)
    _validate_unique_ids(regions, "region_id", "regions")

    systems = tuple(
        SystemSeed(
            system_id=_load_int(entry, "system_id", "systems"),
            region_id=_load_int(entry, "region_id", "systems"),
            name=_load_str(entry, "name", "systems"),
            security_status=_load_float(entry, "security_status", "systems"),
        )
        for entry in _require_sequence(snapshot, "systems")
        if isinstance(entry, Mapping)
    )
    _validate_entry_count(snapshot, "systems", systems)
    _validate_unique_ids(systems, "system_id", "systems")

    stations = tuple(
        StationSeed(
            station_id=_load_int(entry, "station_id", "stations"),
            system_id=_load_int(entry, "system_id", "stations"),
            region_id=_load_int(entry, "region_id", "stations"),
            name=_load_str(entry, "name", "stations"),
        )
        for entry in _require_sequence(snapshot, "stations")
        if isinstance(entry, Mapping)
    )
    _validate_entry_count(snapshot, "stations", stations)
    _validate_unique_ids(stations, "station_id", "stations")

    items = tuple(
        ItemSeed(
            type_id=_load_int(entry, "type_id", "items"),
            name=_load_str(entry, "name", "items"),
            volume_m3=_load_float(entry, "volume_m3", "items"),
            group_name=_load_optional_str(entry, "group_name"),
            category_name=_load_optional_str(entry, "category_name"),
        )
        for entry in _require_sequence(snapshot, "items")
        if isinstance(entry, Mapping)
    )
    _validate_entry_count(snapshot, "items", items)
    _validate_unique_ids(items, "type_id", "items")

    structure_locations: dict[int, StructureLocationSeed] = {}
    for entry in _require_sequence(snapshot, "structure_locations"):
        if not isinstance(entry, Mapping):
            raise FoundationSnapshotError("Foundation snapshot 'structure_locations' entries must be objects.")
        structure_id = _load_int(entry, "structure_id", "structure_locations")
        if structure_id in structure_locations:
            raise FoundationSnapshotError(f"Foundation snapshot contains duplicate structure_id {structure_id}.")
        structure_locations[structure_id] = StructureLocationSeed(
            system_id=_load_int(entry, "system_id", "structure_locations"),
            region_id=_load_int(entry, "region_id", "structure_locations"),
            name=_load_str(entry, "name", "structure_locations"),
        )

    tracked_structures = tuple(
        TrackedStructureSeed(
            structure_id=_load_int(entry, "structure_id", "tracked_structures"),
            name=_load_str(entry, "name", "tracked_structures"),
            tracking_tier=_load_str(entry, "tracking_tier", "tracked_structures"),
        )
        for entry in _require_sequence(snapshot, "tracked_structures")
        if isinstance(entry, Mapping)
    )
    _validate_entry_count(snapshot, "tracked_structures", tracked_structures)
    _validate_unique_ids(tracked_structures, "structure_id", "tracked_structures")

    default_user_settings = _require_mapping(snapshot, "default_user_settings")

    region_ids = {region.region_id for region in regions}
    system_ids = {system.system_id for system in systems}

    for system in systems:
        if system.region_id not in region_ids:
            raise FoundationSnapshotError(
                f"Foundation snapshot system {system.system_id} references unknown region_id {system.region_id}."
            )

    for station in stations:
        if station.region_id not in region_ids:
            raise FoundationSnapshotError(
                f"Foundation snapshot station {station.station_id} references unknown region_id {station.region_id}."
            )
        if station.system_id not in system_ids:
            raise FoundationSnapshotError(
                f"Foundation snapshot station {station.station_id} references unknown system_id {station.system_id}."
            )

    for structure_id, metadata in structure_locations.items():
        if metadata.region_id not in region_ids:
            raise FoundationSnapshotError(
                f"Foundation snapshot structure {structure_id} references unknown region_id {metadata.region_id}."
            )
        if metadata.system_id not in system_ids:
            raise FoundationSnapshotError(
                f"Foundation snapshot structure {structure_id} references unknown system_id {metadata.system_id}."
            )

    for tracked_structure in tracked_structures:
        if tracked_structure.structure_id not in structure_locations:
            raise FoundationSnapshotError(
                f"Foundation snapshot tracked structure {tracked_structure.structure_id} has no matching structure location."
            )
        if tracked_structure.tracking_tier not in VALID_TRACKING_TIERS:
            raise FoundationSnapshotError(
                "Foundation snapshot tracked structure "
                f"{tracked_structure.structure_id} uses unsupported tracking_tier '{tracked_structure.tracking_tier}'."
            )

    return _FoundationSnapshot(
        regions=regions,
        systems=systems,
        stations=stations,
        items=items,
        structure_locations=structure_locations,
        tracked_structures=tracked_structures,
        default_user_settings=dict(default_user_settings),
    )


def _validate_entry_count(snapshot: Mapping[str, object], key: str, entries: Sequence[object]) -> None:
    if len(entries) != len(_require_sequence(snapshot, key)):
        raise FoundationSnapshotError(f"Foundation snapshot section '{key}' entries must be objects.")


def _validate_unique_ids(entries: Sequence[object], key: str, section: str) -> None:
    seen_ids: set[int] = set()
    for entry in entries:
        entry_id = getattr(entry, key)
        if entry_id in seen_ids:
            raise FoundationSnapshotError(f"Foundation snapshot contains duplicate {key} {entry_id} in '{section}'.")
        seen_ids.add(entry_id)


class FileFoundationSeedSource:
    def __init__(self, snapshot_path: str | Path) -> None:
        self.snapshot_path = Path(snapshot_path)
        snapshot = _load_foundation_snapshot(self.snapshot_path)
        self._regions = snapshot.regions
        self._systems = snapshot.systems
        self._stations = snapshot.stations
        self._items = snapshot.items
        self._structure_locations = snapshot.structure_locations
        self._tracked_structures = snapshot.tracked_structures
        self._default_user_settings = snapshot.default_user_settings

    def regions(self) -> Sequence[RegionSeed]:
        return self._regions

    def systems(self) -> Sequence[SystemSeed]:
        return self._systems

    def stations(self) -> Sequence[StationSeed]:
        return self._stations

    def items(self) -> Sequence[ItemSeed]:
        return self._items

    def structure_locations(self) -> Mapping[int, StructureLocationSeed]:
        return self._structure_locations

    def tracked_structures(self) -> Sequence[TrackedStructureSeed]:
        return self._tracked_structures

    def default_user_settings(self) -> Mapping[str, object]:
        return self._default_user_settings


@dataclass(frozen=True)
class StaticFoundationSeedSource:
    regions_data: Sequence[RegionSeed]
    systems_data: Sequence[SystemSeed]
    stations_data: Sequence[StationSeed] = field(default_factory=tuple)
    items_data: Sequence[ItemSeed] = field(default_factory=tuple)
    structure_locations_data: Mapping[int, StructureLocationSeed] = field(default_factory=dict)
    tracked_structures_data: Sequence[TrackedStructureSeed] = field(default_factory=tuple)
    default_user_settings_data: Mapping[str, object] = field(default_factory=dict)

    def regions(self) -> Sequence[RegionSeed]:
        return self.regions_data

    def systems(self) -> Sequence[SystemSeed]:
        return self.systems_data

    def stations(self) -> Sequence[StationSeed]:
        return self.stations_data

    def items(self) -> Sequence[ItemSeed]:
        return self.items_data

    def structure_locations(self) -> Mapping[int, StructureLocationSeed]:
        return self.structure_locations_data

    def tracked_structures(self) -> Sequence[TrackedStructureSeed]:
        return self.tracked_structures_data

    def default_user_settings(self) -> Mapping[str, object]:
        return self.default_user_settings_data


CURATED_REGIONS: tuple[RegionSeed, ...] = (
    RegionSeed(region_id=10000002, name="The Forge"),
    RegionSeed(region_id=10000043, name="Domain"),
    RegionSeed(region_id=10000032, name="Sinq Laison"),
)

CURATED_SYSTEMS: tuple[SystemSeed, ...] = (
    SystemSeed(system_id=30000142, region_id=10000002, name="Jita", security_status=0.9),
    SystemSeed(system_id=30000144, region_id=10000002, name="Perimeter", security_status=0.9),
    SystemSeed(system_id=30002187, region_id=10000043, name="Amarr", security_status=1.0),
    SystemSeed(system_id=30002659, region_id=10000032, name="Dodixie", security_status=0.9),
    SystemSeed(system_id=30002510, region_id=10000043, name="Ashab", security_status=0.7),
    SystemSeed(system_id=30045339, region_id=10000002, name="Amamake", security_status=0.4),
)

CURATED_STATIONS: tuple[StationSeed, ...] = (
    StationSeed(
        station_id=60003760,
        system_id=30000142,
        region_id=10000002,
        name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    ),
    StationSeed(
        station_id=60008494,
        system_id=30002187,
        region_id=10000043,
        name="Amarr VIII (Oris) - Emperor Family Academy",
    ),
    StationSeed(
        station_id=60004588,
        system_id=30002659,
        region_id=10000032,
        name="Dodixie IX - Moon 20 - Federation Navy Assembly Plant",
    ),
)

CURATED_ITEMS: tuple[ItemSeed, ...] = (
    ItemSeed(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material"),
    ItemSeed(type_id=35, name="Pyerite", volume_m3=0.01, group_name="Mineral", category_name="Material"),
    ItemSeed(type_id=36, name="Mexallon", volume_m3=0.01, group_name="Mineral", category_name="Material"),
)

CURATED_DEFAULT_USER_SETTINGS: dict[str, object] = {
    "default_analysis_period_days": 14,
    "warning_threshold_pct": 0.5,
    "warning_enabled": True,
    "sales_tax_rate": 0.036,
    "broker_fee_rate": 0.03,
    "min_confidence_for_local_structure_demand": 0.75,
    "default_user_structure_poll_interval_minutes": 30,
    "snapshot_retention_days": 30,
    "fallback_policy": "regional_fallback",
    "shipping_cost_per_m3": 350.0,
    "default_filters": {
        "min_item_profit": 15_000_000,
        "min_order_margin_pct": 0.20,
        "roi_now": 0.05,
        "target_demand_day": 1,
    },
}

CURATED_STRUCTURE_LOCATIONS: dict[int, StructureLocationSeed] = {
    1022734985679: StructureLocationSeed(system_id=30000144, region_id=10000002, name="Perimeter Market Keepstar"),
    1028858195912: StructureLocationSeed(system_id=30000144, region_id=10000002, name="Tranquility Trading Tower"),
    1021024456781: StructureLocationSeed(system_id=30002187, region_id=10000043, name="Amarr Trade Fortizar"),
    1023344556677: StructureLocationSeed(system_id=30002510, region_id=10000043, name="Ashab Commerce Hub"),
    1029876543210: StructureLocationSeed(system_id=30045339, region_id=10000002, name="Amamake Exchange"),
    1021111111111: StructureLocationSeed(system_id=30002659, region_id=10000032, name="Dodixie Relay"),
    1022222222222: StructureLocationSeed(system_id=30002659, region_id=10000032, name="Hek Trade Port"),
    1023333333333: StructureLocationSeed(system_id=30002659, region_id=10000032, name="Rens Market Nexus"),
    1024444444444: StructureLocationSeed(system_id=30000144, region_id=10000002, name="Jita Fringe Hub"),
    1025555555555: StructureLocationSeed(system_id=30002187, region_id=10000043, name="Domain Logistics Center"),
}

CURATED_TRACKED_STRUCTURES: tuple[TrackedStructureSeed, ...] = (
    TrackedStructureSeed(structure_id=1028858195912, name="Tranquility Trading Tower", tracking_tier="core"),
    TrackedStructureSeed(structure_id=1022734985679, name="Perimeter Market Keepstar", tracking_tier="core"),
    TrackedStructureSeed(structure_id=1021024456781, name="Amarr Trade Fortizar", tracking_tier="core"),
    TrackedStructureSeed(structure_id=1023344556677, name="Ashab Commerce Hub", tracking_tier="secondary"),
    TrackedStructureSeed(structure_id=1029876543210, name="Amamake Exchange", tracking_tier="secondary"),
    TrackedStructureSeed(structure_id=1021111111111, name="Dodixie Relay", tracking_tier="secondary"),
    TrackedStructureSeed(structure_id=1022222222222, name="Hek Trade Port", tracking_tier="secondary"),
    TrackedStructureSeed(structure_id=1023333333333, name="Rens Market Nexus", tracking_tier="secondary"),
    TrackedStructureSeed(structure_id=1024444444444, name="Jita Fringe Hub", tracking_tier="core"),
    TrackedStructureSeed(structure_id=1025555555555, name="Domain Logistics Center", tracking_tier="secondary"),
)


class CuratedFoundationSeedSource:
    def regions(self) -> Sequence[RegionSeed]:
        return CURATED_REGIONS

    def systems(self) -> Sequence[SystemSeed]:
        return CURATED_SYSTEMS

    def stations(self) -> Sequence[StationSeed]:
        return CURATED_STATIONS

    def items(self) -> Sequence[ItemSeed]:
        return CURATED_ITEMS

    def structure_locations(self) -> Mapping[int, StructureLocationSeed]:
        return CURATED_STRUCTURE_LOCATIONS

    def tracked_structures(self) -> Sequence[TrackedStructureSeed]:
        return CURATED_TRACKED_STRUCTURES

    def default_user_settings(self) -> Mapping[str, object]:
        return CURATED_DEFAULT_USER_SETTINGS


DEFAULT_FOUNDATION_SEED_SOURCE = CuratedFoundationSeedSource()
