from dataclasses import dataclass
from typing import TypedDict, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import LocationType
from app.models.all_models import Item, Location, Region, Station, System, TrackedStructure, UserSetting
from app.repositories.seed_data import BUILTIN_TRACKED_STRUCTURES


class RegionSeed(TypedDict):
    region_id: int
    name: str


class SystemSeed(TypedDict):
    system_id: int
    region_id: int
    name: str
    security_status: float


class StationSeed(TypedDict):
    station_id: int
    system_id: int
    region_id: int
    name: str


class ItemSeed(TypedDict):
    type_id: int
    name: str
    volume_m3: float
    group_name: str
    category_name: str


class StructureLocationSeed(TypedDict):
    system_id: int
    region_id: int
    name: str


SEED_REGIONS: list[RegionSeed] = [
    {"region_id": 10000002, "name": "The Forge"},
    {"region_id": 10000043, "name": "Domain"},
    {"region_id": 10000032, "name": "Sinq Laison"},
]

SEED_SYSTEMS: list[SystemSeed] = [
    {"system_id": 30000142, "region_id": 10000002, "name": "Jita", "security_status": 0.9},
    {"system_id": 30000144, "region_id": 10000002, "name": "Perimeter", "security_status": 0.9},
    {"system_id": 30002187, "region_id": 10000043, "name": "Amarr", "security_status": 1.0},
    {"system_id": 30002659, "region_id": 10000032, "name": "Dodixie", "security_status": 0.9},
    {"system_id": 30002510, "region_id": 10000043, "name": "Ashab", "security_status": 0.7},
    {"system_id": 30045339, "region_id": 10000002, "name": "Amamake", "security_status": 0.4},
]

SEED_STATIONS: list[StationSeed] = [
    {
        "station_id": 60003760,
        "system_id": 30000142,
        "region_id": 10000002,
        "name": "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    },
    {
        "station_id": 60008494,
        "system_id": 30002187,
        "region_id": 10000043,
        "name": "Amarr VIII (Oris) - Emperor Family Academy",
    },
    {
        "station_id": 60004588,
        "system_id": 30002659,
        "region_id": 10000032,
        "name": "Dodixie IX - Moon 20 - Federation Navy Assembly Plant",
    },
]

SEED_ITEMS: list[ItemSeed] = [
    {"type_id": 34, "name": "Tritanium", "volume_m3": 0.01, "group_name": "Mineral", "category_name": "Material"},
    {"type_id": 35, "name": "Pyerite", "volume_m3": 0.01, "group_name": "Mineral", "category_name": "Material"},
    {"type_id": 36, "name": "Mexallon", "volume_m3": 0.01, "group_name": "Mineral", "category_name": "Material"},
]

DEFAULT_USER_SETTINGS = {
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

STRUCTURE_SYSTEM_REGION_MAP: dict[int, StructureLocationSeed] = {
    1022734985679: {"system_id": 30000144, "region_id": 10000002, "name": "Perimeter Market Keepstar"},
    1028858195912: {"system_id": 30000144, "region_id": 10000002, "name": "Tranquility Trading Tower"},
    1021024456781: {"system_id": 30002187, "region_id": 10000043, "name": "Amarr Trade Fortizar"},
    1023344556677: {"system_id": 30002510, "region_id": 10000043, "name": "Ashab Commerce Hub"},
    1029876543210: {"system_id": 30045339, "region_id": 10000002, "name": "Amamake Exchange"},
    1021111111111: {"system_id": 30002659, "region_id": 10000032, "name": "Dodixie Relay"},
    1022222222222: {"system_id": 30002659, "region_id": 10000032, "name": "Hek Trade Port"},
    1023333333333: {"system_id": 30002659, "region_id": 10000032, "name": "Rens Market Nexus"},
    1024444444444: {"system_id": 30000144, "region_id": 10000002, "name": "Jita Fringe Hub"},
    1025555555555: {"system_id": 30002187, "region_id": 10000043, "name": "Domain Logistics Center"},
}


@dataclass
class FoundationSeedResult:
    regions: int = 0
    systems: int = 0
    stations: int = 0
    items: int = 0
    locations: int = 0
    tracked_structures: int = 0
    default_settings: int = 0

    @property
    def records_processed(self) -> int:
        return (
            self.regions
            + self.systems
            + self.stations
            + self.items
            + self.locations
            + self.tracked_structures
            + self.default_settings
        )


class FoundationDataService:
    def bootstrap(self, session: Session) -> FoundationSeedResult:
        result = FoundationSeedResult()

        for region in SEED_REGIONS:
            region_instance = session.scalar(select(Region).where(Region.region_id == region["region_id"]))
            if region_instance is None:
                session.add(Region(**region))
                result.regions += 1

        session.flush()

        region_lookup = {
            row.region_id: row.id
            for row in session.scalars(select(Region)).all()
        }

        for system in SEED_SYSTEMS:
            system_instance = session.scalar(select(System).where(System.system_id == system["system_id"]))
            if system_instance is None:
                session.add(
                    System(
                        system_id=system["system_id"],
                        region_id=region_lookup[system["region_id"]],
                        name=system["name"],
                        security_status=system["security_status"],
                    )
                )
                result.systems += 1

        session.flush()

        system_lookup = {
            row.system_id: row.id
            for row in session.scalars(select(System)).all()
        }

        for station in SEED_STATIONS:
            station_instance = session.scalar(select(Station).where(Station.station_id == station["station_id"]))
            if station_instance is None:
                session.add(
                    Station(
                        station_id=station["station_id"],
                        system_id=system_lookup[station["system_id"]],
                        region_id=region_lookup[station["region_id"]],
                        name=station["name"],
                    )
                )
                result.stations += 1

            location = session.scalar(select(Location).where(Location.location_id == station["station_id"]))
            if location is None:
                session.add(
                    Location(
                        location_id=station["station_id"],
                        location_type=LocationType.NPC_STATION.value,
                        system_id=system_lookup[station["system_id"]],
                        region_id=region_lookup[station["region_id"]],
                        name=station["name"],
                    )
                )
                result.locations += 1

        for item in SEED_ITEMS:
            item_instance = session.scalar(select(Item).where(Item.type_id == item["type_id"]))
            if item_instance is None:
                session.add(Item(**item))
                result.items += 1

        for structure in BUILTIN_TRACKED_STRUCTURES:
            structure_id = cast(int, structure["structure_id"])
            metadata = STRUCTURE_SYSTEM_REGION_MAP[structure_id]
            location = session.scalar(select(Location).where(Location.location_id == structure_id))
            if location is None:
                session.add(
                    Location(
                        location_id=structure_id,
                        location_type=LocationType.STRUCTURE.value,
                        system_id=system_lookup[metadata["system_id"]],
                        region_id=region_lookup[metadata["region_id"]],
                        name=metadata["name"],
                    )
                )
                result.locations += 1

            tracked = session.scalar(
                select(TrackedStructure).where(TrackedStructure.structure_id == structure_id)
            )
            if tracked is None:
                session.add(
                    TrackedStructure(
                        structure_id=structure_id,
                        name=metadata["name"],
                        system_id=system_lookup[metadata["system_id"]],
                        region_id=region_lookup[metadata["region_id"]],
                        tracking_tier=structure["tracking_tier"],
                        poll_interval_minutes=10 if structure["tracking_tier"] == "core" else 30,
                        is_enabled=True,
                        notes="Seeded built-in trade hub",
                    )
                )
                result.tracked_structures += 1

        existing_defaults = session.scalar(select(UserSetting).where(UserSetting.user_id.is_(None)))
        if existing_defaults is None:
            session.add(UserSetting(user_id=None, key="defaults", value=DEFAULT_USER_SETTINGS))
            result.default_settings += 1

        session.commit()
        return result
