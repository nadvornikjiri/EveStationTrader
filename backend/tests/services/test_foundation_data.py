from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import Item, Location, Region, Station, System, TrackedStructure, UserSetting
from app.repositories.seed_data import (
    CuratedFoundationSeedSource,
    ItemSeed,
    DEFAULT_FOUNDATION_SEED_SOURCE,
    FileFoundationSeedSource,
    FoundationSnapshotError,
    RegionSeed,
    StationSeed,
    StructureLocationSeed,
    TrackedStructureSeed,
    SystemSeed,
)
from app.services.sync.foundation_data import FoundationDataService
from tests.db_test_utils import build_test_session

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
FOUNDATION_SNAPSHOT_PATH = FIXTURES_DIR / "foundation_snapshot.json"


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
    return build_test_session()


def test_foundation_data_bootstrap_is_idempotent() -> None:
    session = build_session()
    service = FoundationDataService()

    first = service.bootstrap(session)
    second = service.bootstrap(session)

    assert first.records_processed > 0
    assert second.records_processed == 0


def test_foundation_data_service_defaults_to_curated_source() -> None:
    service = FoundationDataService()

    assert service.seed_source is DEFAULT_FOUNDATION_SEED_SOURCE
    assert isinstance(service.seed_source, CuratedFoundationSeedSource)


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


def test_file_foundation_seed_source_loads_minimal_snapshot() -> None:
    source = FileFoundationSeedSource(FOUNDATION_SNAPSHOT_PATH)

    assert source.regions() == (RegionSeed(region_id=91000001, name="Snapshot Region"),)
    assert source.systems() == (
        SystemSeed(system_id=92000001, region_id=91000001, name="Snapshot System", security_status=0.4),
    )
    assert source.stations() == (
        StationSeed(
            station_id=93000001,
            system_id=92000001,
            region_id=91000001,
            name="Snapshot Station",
        ),
    )
    assert source.items() == (
        ItemSeed(
            type_id=94000001,
            name="Snapshot Item",
            volume_m3=1.25,
            group_name="Snapshot Group",
            category_name="Snapshot Category",
        ),
    )
    assert source.structure_locations() == {
        95000001: StructureLocationSeed(system_id=92000001, region_id=91000001, name="Snapshot Structure"),
    }
    assert source.tracked_structures() == (
        TrackedStructureSeed(structure_id=95000001, name="Snapshot Structure", tracking_tier="secondary"),
    )
    assert source.default_user_settings()["default_analysis_period_days"] == 21


def test_foundation_data_bootstrap_with_file_snapshot_is_idempotent() -> None:
    session = build_session()
    service = FoundationDataService(seed_source=FileFoundationSeedSource(FOUNDATION_SNAPSHOT_PATH))

    first = service.bootstrap(session)
    second = service.bootstrap(session)

    assert first.records_processed == 8
    assert second.records_processed == 0
    assert session.scalar(select(Region).where(Region.region_id == 91000001)) is not None
    assert session.scalar(select(System).where(System.system_id == 92000001)) is not None
    assert session.scalar(select(Station).where(Station.station_id == 93000001)) is not None
    assert session.scalar(select(Location).where(Location.location_id == 93000001)) is not None
    assert session.scalar(select(Location).where(Location.location_id == 95000001)) is not None
    assert session.scalar(select(Item).where(Item.type_id == 94000001)) is not None
    assert session.scalar(select(TrackedStructure).where(TrackedStructure.structure_id == 95000001)) is not None
    defaults = session.scalar(select(UserSetting).where(UserSetting.user_id.is_(None)))
    assert defaults is not None
    assert defaults.value["default_analysis_period_days"] == 21


@pytest.mark.parametrize(
    ("snapshot_text", "expected_message"),
    [
        (
            '{"regions": [], "systems": [], "stations": [], "items": [], "structure_locations": [], "default_user_settings": {}}',
            "tracked_structures",
        ),
        (
            '{"regions": [{"region_id": 1, "name": "R"}], "systems": [{"system_id": 1, "region_id": 1, "name": "S", "security_status": 0.1}], "stations": [], "items": [], "structure_locations": [{"structure_id": 2, "system_id": 999, "region_id": 1, "name": "Broken"}], "tracked_structures": [{"structure_id": 2, "name": "Broken", "tracking_tier": "secondary"}], "default_user_settings": {}}',
            "unknown system_id 999",
        ),
        (
            '{"regions": [{"region_id": 1, "name": "R"}, {"region_id": 1, "name": "Duplicate"}], "systems": [], "stations": [], "items": [], "structure_locations": [], "tracked_structures": [], "default_user_settings": {}}',
            "duplicate region_id 1",
        ),
        (
            '{"regions": [{"region_id": 1, "name": "R"}], "systems": [{"system_id": 1, "region_id": 1, "name": "S", "security_status": 0.1}], "stations": [], "items": [], "structure_locations": [{"structure_id": 2, "system_id": 1, "region_id": 1, "name": "Valid"}], "tracked_structures": [{"structure_id": 2, "name": "Valid", "tracking_tier": "tertiary"}], "default_user_settings": {}}',
            "unsupported tracking_tier 'tertiary'",
        ),
        ("not-json", "not valid JSON"),
    ],
)
def test_file_foundation_seed_source_rejects_invalid_snapshots(
    snapshot_text: str,
    expected_message: str,
    tmp_path: Path,
) -> None:
    snapshot_path = tmp_path / "foundation_snapshot.json"
    snapshot_path.write_text(snapshot_text, encoding="utf-8")

    with pytest.raises(FoundationSnapshotError, match=expected_message):
        FileFoundationSeedSource(snapshot_path)


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
