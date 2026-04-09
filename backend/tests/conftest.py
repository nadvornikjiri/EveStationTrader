import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from tests.db_test_utils import ensure_test_database, get_test_database_url, reset_schema

os.environ["DATABASE_URL"] = get_test_database_url()

from app.main import app  # noqa: E402
from app.db.session import engine as app_engine  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.repositories.seed_data import ItemSeed, RegionSeed, StationSeed, StaticFoundationSeedSource, SystemSeed  # noqa: E402
from app.services.sync.foundation_import import FoundationImportService  # noqa: E402


TEST_FOUNDATION_SOURCE = StaticFoundationSeedSource(
    regions_data=(
        RegionSeed(region_id=10000002, name="The Forge"),
        RegionSeed(region_id=10000043, name="Domain"),
    ),
    systems_data=(
        SystemSeed(system_id=30000142, region_id=10000002, name="Jita", security_status=0.9),
        SystemSeed(system_id=30002187, region_id=10000043, name="Amarr", security_status=1.0),
    ),
    stations_data=(
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
    ),
    items_data=(
        ItemSeed(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material"),
    ),
)


def _bootstrap_baseline() -> None:
    session = SessionLocal()
    try:
        FoundationImportService().import_from_seed_source(session, seed_source=TEST_FOUNDATION_SOURCE)
    finally:
        session.close()


@pytest.fixture(scope="session")
def _shared_client() -> Generator[TestClient, None, None]:
    ensure_test_database()
    app_engine.dispose()
    reset_schema(app_engine)
    _bootstrap_baseline()
    with TestClient(app) as shared_client:
        yield shared_client
    app_engine.dispose()


@pytest.fixture
def client(_shared_client: TestClient) -> Generator[TestClient, None, None]:
    app_engine.dispose()
    reset_schema(app_engine)
    _bootstrap_baseline()
    yield _shared_client
    app_engine.dispose()
