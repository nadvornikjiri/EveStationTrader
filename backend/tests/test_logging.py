import logging
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.core.logging import configure_logging, request_logger
from app.db import session as db_session
from app.db.session import SessionLocal

pytestmark = pytest.mark.integration


def test_request_logging_emits_http_request_line(client) -> None:
    with patch.object(request_logger, "info") as mock_info:
        response = client.get("/health")

    assert response.status_code == 200
    assert mock_info.called
    assert mock_info.call_args[0][0] == "%s %s -> %s (%.2f ms)"
    assert mock_info.call_args[0][1:4] == ("GET", "/health", 200)


def test_sql_logging_emits_query_line() -> None:
    session = SessionLocal()
    try:
        with patch.object(db_session.sql_logger, "info") as mock_info:
            session.execute(text("SELECT 1"))
    finally:
        session.close()

    assert mock_info.called
    assert mock_info.call_args[0][0] == "SQL %s params=%s (%.2f ms)"
    assert mock_info.call_args[0][1] == "SELECT 1"


def test_configure_logging_keeps_uvicorn_access_visible() -> None:
    configure_logging()

    logger = logging.getLogger("uvicorn.access")

    assert logger.level == logging.INFO
    assert logger.propagate is False
    assert any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers)
