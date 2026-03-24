from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import LocationType
from app.models.all_models import Item, Location, Region, Station, System, TrackedStructure, UserSetting
from app.repositories.seed_data import DEFAULT_FOUNDATION_SEED_SOURCE, FoundationSeedSource, StationSeed


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
    CHECKPOINT_INTERVAL = 100

    def __init__(self, seed_source: FoundationSeedSource = DEFAULT_FOUNDATION_SEED_SOURCE) -> None:
        self.seed_source = seed_source

    def bootstrap(self, session: Session, cancellation_check: Callable[[], None] | None = None) -> FoundationSeedResult:
        result = FoundationSeedResult()

        self._seed_regions(session, result, cancellation_check)
        region_lookup = self._build_region_lookup(session)

        self._seed_systems(session, result, region_lookup, cancellation_check)
        system_lookup = self._build_system_lookup(session)

        self._seed_locations(session, result, region_lookup, system_lookup, cancellation_check)
        self._seed_items(session, result, cancellation_check)
        self._seed_tracked_structures(session, result, region_lookup, system_lookup, cancellation_check)
        self._seed_defaults(session, result)

        session.commit()
        return result

    def _seed_regions(
        self,
        session: Session,
        result: FoundationSeedResult,
        cancellation_check: Callable[[], None] | None,
    ) -> None:
        for index, region in enumerate(self.seed_source.regions(), start=1):
            if cancellation_check is not None:
                cancellation_check()
            region_instance = session.scalar(select(Region).where(Region.region_id == region.region_id))
            if region_instance is None:
                session.add(Region(region_id=region.region_id, name=region.name))
                result.regions += 1
            self._maybe_checkpoint(session, index)

        session.flush()

    def _build_region_lookup(self, session: Session) -> dict[int, int]:
        return {row.region_id: row.id for row in session.scalars(select(Region)).all()}

    def _seed_systems(
        self,
        session: Session,
        result: FoundationSeedResult,
        region_lookup: dict[int, int],
        cancellation_check: Callable[[], None] | None,
    ) -> None:
        for index, system in enumerate(self.seed_source.systems(), start=1):
            if cancellation_check is not None:
                cancellation_check()
            system_instance = session.scalar(select(System).where(System.system_id == system.system_id))
            if system_instance is None:
                session.add(
                    System(
                        system_id=system.system_id,
                        region_id=region_lookup[system.region_id],
                        name=system.name,
                        security_status=system.security_status,
                    )
                )
                result.systems += 1
            self._maybe_checkpoint(session, index)

        session.flush()

    def _build_system_lookup(self, session: Session) -> dict[int, int]:
        return {row.system_id: row.id for row in session.scalars(select(System)).all()}

    def _seed_locations(
        self,
        session: Session,
        result: FoundationSeedResult,
        region_lookup: dict[int, int],
        system_lookup: dict[int, int],
        cancellation_check: Callable[[], None] | None,
    ) -> None:
        for index, station in enumerate(self.seed_source.stations(), start=1):
            if cancellation_check is not None:
                cancellation_check()
            self._seed_station(session, result, station, region_lookup, system_lookup)
            self._maybe_checkpoint(session, index)

        for index, (structure_id, metadata) in enumerate(self.seed_source.structure_locations().items(), start=1):
            if cancellation_check is not None:
                cancellation_check()
            location = session.scalar(select(Location).where(Location.location_id == structure_id))
            if location is None:
                session.add(
                    Location(
                        location_id=structure_id,
                        location_type=LocationType.STRUCTURE.value,
                        system_id=system_lookup[metadata.system_id],
                        region_id=region_lookup[metadata.region_id],
                        name=metadata.name,
                    )
                )
                result.locations += 1
            self._maybe_checkpoint(session, index)

    def _seed_station(
        self,
        session: Session,
        result: FoundationSeedResult,
        station: StationSeed,
        region_lookup: dict[int, int],
        system_lookup: dict[int, int],
    ) -> None:
        station_instance = session.scalar(select(Station).where(Station.station_id == station.station_id))
        if station_instance is None:
            session.add(
                Station(
                    station_id=station.station_id,
                    system_id=system_lookup[station.system_id],
                    region_id=region_lookup[station.region_id],
                    name=station.name,
                )
            )
            result.stations += 1

        location = session.scalar(select(Location).where(Location.location_id == station.station_id))
        if location is None:
            session.add(
                Location(
                    location_id=station.station_id,
                    location_type=LocationType.NPC_STATION.value,
                    system_id=system_lookup[station.system_id],
                    region_id=region_lookup[station.region_id],
                    name=station.name,
                )
            )
            result.locations += 1

    def _seed_items(
        self,
        session: Session,
        result: FoundationSeedResult,
        cancellation_check: Callable[[], None] | None,
    ) -> None:
        for index, item in enumerate(self.seed_source.items(), start=1):
            if cancellation_check is not None:
                cancellation_check()
            item_instance = session.scalar(select(Item).where(Item.type_id == item.type_id))
            if item_instance is None:
                session.add(
                    Item(
                        type_id=item.type_id,
                        name=item.name,
                        volume_m3=item.volume_m3,
                        group_name=item.group_name,
                        category_name=item.category_name,
                    )
                )
                result.items += 1
            self._maybe_checkpoint(session, index)

    def _seed_tracked_structures(
        self,
        session: Session,
        result: FoundationSeedResult,
        region_lookup: dict[int, int],
        system_lookup: dict[int, int],
        cancellation_check: Callable[[], None] | None,
    ) -> None:
        structure_locations = self.seed_source.structure_locations()
        tracked_structures = {seed.structure_id: seed for seed in self.seed_source.tracked_structures()}

        for index, (structure_id, tracked_seed) in enumerate(tracked_structures.items(), start=1):
            if cancellation_check is not None:
                cancellation_check()
            metadata = structure_locations[structure_id]
            tracked = session.scalar(select(TrackedStructure).where(TrackedStructure.structure_id == structure_id))
            if tracked is None:
                session.add(
                    TrackedStructure(
                        structure_id=structure_id,
                        name=tracked_seed.name,
                        system_id=system_lookup[metadata.system_id],
                        region_id=region_lookup[metadata.region_id],
                        tracking_tier=tracked_seed.tracking_tier,
                        poll_interval_minutes=10 if tracked_seed.tracking_tier == "core" else 30,
                        is_enabled=True,
                        notes="Seeded built-in trade hub",
                    )
                )
                result.tracked_structures += 1
            self._maybe_checkpoint(session, index)

    def _seed_defaults(self, session: Session, result: FoundationSeedResult) -> None:
        existing_defaults = session.scalar(select(UserSetting).where(UserSetting.user_id.is_(None)))
        if existing_defaults is None:
            session.add(UserSetting(user_id=None, key="defaults", value=dict(self.seed_source.default_user_settings())))
            result.default_settings += 1

    def _maybe_checkpoint(self, session: Session, iteration: int) -> None:
        if iteration % self.CHECKPOINT_INTERVAL == 0:
            session.commit()
