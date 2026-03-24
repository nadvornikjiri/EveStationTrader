import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from tests.db_test_utils import ensure_test_database, get_test_database_url, reset_schema

os.environ["DATABASE_URL"] = get_test_database_url()
ensure_test_database()

from app.main import app  # noqa: E402
from app.db.session import engine as app_engine  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.sync.foundation_data import FoundationDataService  # noqa: E402


def _bootstrap_baseline() -> None:
    session = SessionLocal()
    try:
        FoundationDataService().bootstrap(session)
    finally:
        session.close()


@pytest.fixture(scope="session")
def _shared_client() -> Generator[TestClient, None, None]:
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
