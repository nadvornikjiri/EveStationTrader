from collections.abc import Mapping, Sequence

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.all_models import Item, Location, Region, Station, System, TrackedStructure, UserSetting
from app.repositories.seed_data import (
    ItemSeed,
    RegionSeed,
    StationSeed,
    StructureLocationSeed,
    TrackedStructureSeed,
    SystemSeed,
)
from app.services.sync.foundation_data import FoundationDataService


class MockFoundationSeedSource:
    def regions(self) -> Sequence[RegionSeed]:
        return (RegionSeed(region_id=99900001, name="Mock Region"),)

    def systems(self) -> Sequence[SystemSeed]:
        return (SystemSeed(system_id=99910001, region_id=99900001, name="Mock System", security_status=0.6),)

    def stations(self) -> Sequence[StationSeed]:
        return (
            StationSeed(
                station_id=99920001,
                system_id=99910001,
                region_id=99900001,
                name="Mock Station",
            ),
        )

    def items(self) -> Sequence[ItemSeed]:
        return (ItemSeed(type_id=99930001, name="Mock Item", volume_m3=1.5, group_name="Test", category_name="Test"),)

    def structure_locations(self) -> Mapping[int, StructureLocationSeed]:
        return {
            99940001: StructureLocationSeed(system_id=99910001, region_id=99900001, name="Mock Structure"),
        }

    def tracked_structures(self) -> Sequence[TrackedStructureSeed]:
        return (TrackedStructureSeed(structure_id=99940001, name="Mock Structure", tracking_tier="secondary"),)

    def default_user_settings(self) -> Mapping[str, object]:
        return {"default_analysis_period_days": 7, "warning_enabled": True}


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_foundation_data_bootstrap_is_idempotent() -> None:
    session = build_session()
    service = FoundationDataService()

    first = service.bootstrap(session)
    second = service.bootstrap(session)

    assert first.records_processed > 0
    assert second.records_processed == 0


def test_foundation_data_bootstrap_seeds_core_entities() -> None:
    session = build_session()
    FoundationDataService().bootstrap(session)

    assert session.scalar(select(Region).where(Region.region_id == 10000002)) is not None
    assert session.scalar(select(System).where(System.system_id == 30000142)) is not None
    assert session.scalar(select(Station).where(Station.station_id == 60003760)) is not None
    assert session.scalar(select(Item).where(Item.type_id == 34)) is not None
    assert session.scalar(select(Location).where(Location.location_id == 60003760)) is not None
    assert session.scalar(select(TrackedStructure).where(TrackedStructure.structure_id == 1022734985679)) is not None
    defaults = session.scalar(select(UserSetting).where(UserSetting.user_id.is_(None)))
    assert defaults is not None
    assert defaults.key == "defaults"


def test_foundation_data_bootstrap_uses_a_mock_source() -> None:
    session = build_session()
    service = FoundationDataService(seed_source=MockFoundationSeedSource())

    result = service.bootstrap(session)

    assert result.records_processed == 8
    assert session.scalar(select(Region).where(Region.region_id == 99900001)) is not None
    assert session.scalar(select(System).where(System.system_id == 99910001)) is not None
    assert session.scalar(select(Station).where(Station.station_id == 99920001)) is not None
    assert session.scalar(select(Location).where(Location.location_id == 99920001)) is not None
    assert session.scalar(select(Location).where(Location.location_id == 99940001)) is not None
    assert session.scalar(select(Item).where(Item.type_id == 99930001)) is not None
    assert session.scalar(select(TrackedStructure).where(TrackedStructure.structure_id == 99940001)) is not None
    defaults = session.scalar(select(UserSetting).where(UserSetting.user_id.is_(None)))
    assert defaults is not None
    assert defaults.value["default_analysis_period_days"] == 7
