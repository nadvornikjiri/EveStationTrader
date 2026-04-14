import os
from functools import lru_cache
from pathlib import Path
import subprocess
import time
import weakref
from weakref import WeakSet

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.db.base import Base

DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://eve_trader:eve_trader@localhost:5432/eve_trader_test"
POSTGRES_UNAVAILABLE_MESSAGE = (
    "Postgres test database is unavailable. Start PostgreSQL on localhost:5432 "
    "or run `docker compose up -d postgres` before running tests."
)
DOCKER_STARTUP_TIMEOUT_SECONDS = 60
REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SERVICES = ("postgres",)
_ACTIVE_TEST_SESSIONS: WeakSet[Session] = WeakSet()


def get_test_database_url() -> str:
    return os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def should_start_local_test_services(database_url: str) -> bool:
    url = make_url(database_url)
    return url.host in {None, "localhost", "127.0.0.1"} and url.port in {None, 5432}


def start_local_test_services() -> None:
    try:
        subprocess.run(
            ["docker", "compose", "up", "-d", *COMPOSE_SERVICES],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Docker CLI is unavailable. Install Docker or start PostgreSQL manually before running integration tests."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        details = stderr or stdout or "docker compose up failed"
        raise RuntimeError(f"Failed to start test services via Docker Compose: {details}") from exc


def _build_admin_engine() -> tuple[Engine, str]:
    database_url = get_test_database_url()
    url = make_url(database_url)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError(f"Postgres-backed tests require a PostgreSQL URL, got {database_url!r}.")
    database_name = url.database
    if not database_name:
        raise RuntimeError(f"Postgres-backed tests require a database name, got {database_url!r}.")
    if database_name == "postgres":
        raise RuntimeError(
            "Postgres-backed tests must target a dedicated test database, not the admin 'postgres' database."
        )
    admin_engine = create_engine(
        url.set(database="postgres"),
        future=True,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )
    return admin_engine, database_name


def _terminate_test_database_connections() -> None:
    admin_engine, database_name = _build_admin_engine()
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %(database_name)s
                  AND pid <> pg_backend_pid()
                """,
                {"database_name": database_name},
            )
    finally:
        admin_engine.dispose()


def _close_active_test_sessions() -> None:
    sessions = tuple(_ACTIVE_TEST_SESSIONS)
    for session in sessions:
        session.close()
    _ACTIVE_TEST_SESSIONS.clear()


def _ensure_database_exists(admin_engine: Engine, database_name: str) -> None:
    with admin_engine.connect() as connection:
        exists = connection.exec_driver_sql(
            "SELECT 1 FROM pg_database WHERE datname = %(database_name)s",
            {"database_name": database_name},
        ).scalar()
        if exists is None:
            connection.exec_driver_sql(f"CREATE DATABASE {_quote_identifier(database_name)}")


def _wait_for_database(admin_engine: Engine, database_name: str) -> None:
    deadline = time.monotonic() + DOCKER_STARTUP_TIMEOUT_SECONDS
    last_error: OperationalError | None = None

    while time.monotonic() < deadline:
        try:
            _ensure_database_exists(admin_engine, database_name)
            return
        except OperationalError as exc:
            last_error = exc
            time.sleep(1)

    raise RuntimeError(POSTGRES_UNAVAILABLE_MESSAGE) from last_error


def ensure_test_database() -> None:
    admin_engine, database_name = _build_admin_engine()
    try:
        _ensure_database_exists(admin_engine, database_name)
    except OperationalError as exc:
        if not should_start_local_test_services(get_test_database_url()):
            raise RuntimeError(POSTGRES_UNAVAILABLE_MESSAGE) from exc

        start_local_test_services()
        _wait_for_database(admin_engine, database_name)
    finally:
        admin_engine.dispose()


def recreate_test_database() -> None:
    admin_engine, database_name = _build_admin_engine()
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %(database_name)s
                  AND pid <> pg_backend_pid()
                """,
                {"database_name": database_name},
            )
            connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {_quote_identifier(database_name)}")
            connection.exec_driver_sql(f"CREATE DATABASE {_quote_identifier(database_name)}")
    except OperationalError as exc:
        raise RuntimeError(POSTGRES_UNAVAILABLE_MESSAGE) from exc
    finally:
        admin_engine.dispose()


@lru_cache(maxsize=1)
def create_test_engine() -> Engine:
    ensure_test_database()
    return create_engine(
        get_test_database_url(),
        future=True,
        pool_pre_ping=True,
        poolclass=NullPool,
        connect_args={"connect_timeout": 5},
    )


_schema_initialized = False


def _rebuild_schema(engine: Engine) -> None:
    for attempt in range(3):
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
                connection.exec_driver_sql("CREATE SCHEMA public")
                Base.metadata.create_all(connection)
            break
        except OperationalError:
            if attempt == 2:
                raise
            engine.dispose()
            time.sleep(0.1)
    alembic_cfg = AlembicConfig(REPO_ROOT / "backend" / "alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url))
    alembic_command.stamp(alembic_cfg, "head")


def _ensure_schema(engine: Engine) -> None:
    global _schema_initialized
    if _schema_initialized:
        return
    _terminate_test_database_connections()
    _rebuild_schema(engine)
    _schema_initialized = True


def reset_schema(engine: Engine) -> None:
    _close_active_test_sessions()
    engine.dispose()
    _terminate_test_database_connections()
    engine.dispose()
    _rebuild_schema(engine)


@lru_cache(maxsize=1)
def _get_test_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=create_test_engine(), expire_on_commit=False)


def build_test_session() -> Session:
    engine = create_test_engine()
    reset_schema(engine)
    session = _get_test_sessionmaker()()
    _ACTIVE_TEST_SESSIONS.add(session)
    weakref.finalize(session, session.close)
    return session
