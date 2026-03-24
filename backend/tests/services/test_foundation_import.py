import io
import json
import zipfile

import pytest

from app.services.sync.foundation_import import CcpSdeClient


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
    assert [item.type_id for item in source.items()] == [34]
    assert source.items()[0].group_name == "Mineral"
    assert source.items()[0].category_name == "Material"


def test_ccp_sde_client_uses_plain_jsonl_zip_without_station_names() -> None:
    client = StubCcpSdeClient(download=_build_fixture_zip(include_station_names=False))

    source = client.build_seed_source()

    assert source.stations()[0].name == "Station 60003760"


def test_ccp_sde_client_surfaces_download_failures() -> None:
    client = StubCcpSdeClient(download=None)

    with pytest.raises(ValueError, match="Unable to download CCP SDE zip"):
        client.build_seed_source()
