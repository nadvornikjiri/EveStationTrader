from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
    group_name: str
    category_name: str


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
