from collections.abc import Generator
import logging
from pathlib import Path
from time import sleep
from time import perf_counter

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
sql_logger = logging.getLogger("app.db.queries")

engine = create_engine(settings.database_url, future=True)
DATABASE_STARTUP_RETRY_ATTEMPTS = 60
DATABASE_STARTUP_RETRY_DELAY_SECONDS = 1.0

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany) -> None:
    del cursor, context, executemany
    conn.info["_query_start_time"] = perf_counter()
    conn.info["_query_statement"] = " ".join(statement.split())
    conn.info["_query_parameters"] = parameters


@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany) -> None:
    del cursor, statement, parameters, context, executemany
    start_time = conn.info.pop("_query_start_time", None)
    normalized_statement = conn.info.pop("_query_statement", "")
    query_parameters = conn.info.pop("_query_parameters", None)
    duration_ms = ((perf_counter() - start_time) * 1000) if start_time is not None else 0.0
    formatted_parameters = _format_sql_parameters(query_parameters)
    sql_logger.debug(
        "SQL %s params=%s (%.2f ms)",
        normalized_statement,
        formatted_parameters,
        duration_ms,
    )


def _format_sql_parameters(parameters: object) -> str:
    rendered = repr(parameters)
    return rendered if len(rendered) <= 400 else f"{rendered[:397]}..."


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_database() -> None:
    from app.services.settings_service import SettingsService

    wait_for_database()
    run_migrations()
    SettingsService().get_settings()


def wait_for_database() -> None:
    last_error: OperationalError | None = None
    for attempt in range(DATABASE_STARTUP_RETRY_ATTEMPTS):
        try:
            with engine.connect() as connection:
                connection.exec_driver_sql("SELECT 1")
            return
        except OperationalError as exc:
            last_error = exc
            if attempt == DATABASE_STARTUP_RETRY_ATTEMPTS - 1:
                break
            sleep(DATABASE_STARTUP_RETRY_DELAY_SECONDS)

    if last_error is not None:
        raise last_error


def run_migrations() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    alembic_config = Config(str(backend_root / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(backend_root / "alembic"))
    alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_config, "head")
