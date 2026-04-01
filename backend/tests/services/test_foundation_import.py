import io
import json
import zipfile

import pytest
from sqlalchemy import select

from app.models.all_models import Location, Region, Station, System
from app.repositories.seed_data import RegionSeed, StaticFoundationSeedSource, StationSeed, SystemSeed
from app.services.sync.foundation_import import CcpSdeClient
from app.services.sync.foundation_import import FoundationImportService
from tests.db_test_utils import build_test_session


def _build_fixture_zip(*, include_station_names: bool) -> bytes:
    payloads = {
        "mapRegions.jsonl": [
            {"_key": 10000002, "name": {"en": "The Forge"}},
        ],
        "mapSolarSystems.jsonl": [
            {"_key": 30000142, "regionID": 10000002, "name": {"en": "Jita"}, "securityStatus": 0.9},
        ],
        "npcStations.jsonl": [
            {
                "_key": 60003760,
                "solarSystemID": 30000142,
                **({"name": {"en": "Jita IV - Moon 4 - Caldari Navy Assembly Plant"}} if include_station_names else {}),
            },
        ],
        "categories.jsonl": [
            {"_key": 4, "name": {"en": "Material"}},
            {"_key": 9, "name": {"en": "Blueprint"}},
        ],
        "groups.jsonl": [
            {"_key": 18, "categoryID": 4, "name": {"en": "Mineral"}},
            {"_key": 160, "categoryID": 9, "name": {"en": "Blueprint"}},
        ],
        "types.jsonl": [
            {
                "_key": 34,
                "groupID": 18,
                "name": {"en": "Tritanium"},
                "volume": 0.01,
                "published": True,
                "marketGroupID": 54,
            },
            {
                "_key": 35,
                "groupID": 18,
                "name": {"en": "Pyerite"},
                "volume": 0.01,
                "published": True,
                "marketGroupID": None,
            },
            {
                "_key": 28503,
                "groupID": 160,
                "name": {"en": "Bowhead Blueprint"},
                "volume": 0.01,
                "published": True,
                "marketGroupID": 2,
            },
        ],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, records in payloads.items():
            archive.writestr(name, "".join(json.dumps(record) + "\n" for record in records))
    return buffer.getvalue()


class StubCcpSdeClient(CcpSdeClient):
    def __init__(self, *, download: bytes | None) -> None:
        super().__init__(static_data_jsonl_url="https://example.invalid/eve-online-static-data-latest-jsonl.zip")
        self.download = download

    def _download_zip_bytes(self) -> bytes:
        if self.download is None:
            raise ValueError("Unable to download CCP SDE zip from latest JSONL archive URL.")
        return self.download


def test_ccp_sde_client_builds_seed_source_from_bulk_jsonl_zip() -> None:
    client = StubCcpSdeClient(download=_build_fixture_zip(include_station_names=True))

    source = client.build_seed_source()

    assert source.regions()[0].region_id == 10000002
    assert source.systems()[0].system_id == 30000142
    assert source.stations()[0].station_id == 60003760
    assert source.stations()[0].name == "Jita IV - Moon 4 - Caldari Navy Assembly Plant"
    assert [item.type_id for item in source.items()] == [34, 35, 28503]
    assert source.items()[0].group_name == "Mineral"
    assert source.items()[0].category_name == "Material"
    assert source.items()[1].name == "Pyerite"
    assert source.items()[2].category_name == "Blueprint"


def test_ccp_sde_client_uses_plain_jsonl_zip_without_station_names() -> None:
    client = StubCcpSdeClient(download=_build_fixture_zip(include_station_names=False))

    source = client.build_seed_source()

    assert source.stations()[0].name == "Station 60003760"


def test_ccp_sde_client_surfaces_download_failures() -> None:
    client = StubCcpSdeClient(download=None)

    with pytest.raises(ValueError, match="Unable to download CCP SDE zip"):
        client.build_seed_source()


def test_foundation_import_service_backfills_placeholder_station_names() -> None:
    session = build_test_session()
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()
    system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    session.add(system)
    session.flush()
    session.add(
        Station(
            station_id=60003760,
            system_id=system.id,
            region_id=region.id,
            name="Station 60003760",
        )
    )
    session.add(
        Location(
            location_id=60003760,
            location_type="npc_station",
            system_id=system.id,
            region_id=region.id,
            name="Station 60003760",
        )
    )
    session.commit()

    seed_source = StaticFoundationSeedSource(
        regions_data=(RegionSeed(region_id=10000002, name="The Forge"),),
        systems_data=(SystemSeed(system_id=30000142, region_id=10000002, name="Jita", security_status=0.9),),
        stations_data=(
            StationSeed(
                station_id=60003760,
                system_id=30000142,
                region_id=10000002,
                name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            ),
        ),
    )

    FoundationImportService().import_from_seed_source(session, seed_source=seed_source)

    station = session.scalar(select(Station).where(Station.station_id == 60003760))
    location = session.scalar(select(Location).where(Location.location_id == 60003760))
    assert station is not None
    assert location is not None
    assert station.name == "Jita IV - Moon 4 - Caldari Navy Assembly Plant"
    assert location.name == "Jita IV - Moon 4 - Caldari Navy Assembly Plant"


def test_foundation_import_service_preserves_resolved_station_name_when_seed_is_placeholder() -> None:
    session = build_test_session()
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()
    system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    session.add(system)
    session.flush()
    session.add(
        Station(
            station_id=60003760,
            system_id=system.id,
            region_id=region.id,
            name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
        )
    )
    session.add(
        Location(
            location_id=60003760,
            location_type="npc_station",
            system_id=system.id,
            region_id=region.id,
            name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
        )
    )
    session.commit()

    seed_source = StaticFoundationSeedSource(
        regions_data=(RegionSeed(region_id=10000002, name="The Forge"),),
        systems_data=(SystemSeed(system_id=30000142, region_id=10000002, name="Jita", security_status=0.9),),
        stations_data=(
            StationSeed(
                station_id=60003760,
                system_id=30000142,
                region_id=10000002,
                name="Station 60003760",
            ),
        ),
    )

    FoundationImportService().import_from_seed_source(session, seed_source=seed_source)

    station = session.scalar(select(Station).where(Station.station_id == 60003760))
    location = session.scalar(select(Location).where(Location.location_id == 60003760))
    assert station is not None
    assert location is not None
    assert station.name == "Jita IV - Moon 4 - Caldari Navy Assembly Plant"
    assert location.name == "Jita IV - Moon 4 - Caldari Navy Assembly Plant"
