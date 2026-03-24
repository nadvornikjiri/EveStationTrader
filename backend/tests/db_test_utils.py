import os
from functools import lru_cache
import weakref

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, close_all_sessions, sessionmaker
from sqlalchemy.pool import NullPool

from app.db.base import Base

DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://eve_trader:eve_trader@localhost:5432/eve_trader_test"
POSTGRES_UNAVAILABLE_MESSAGE = (
    "Postgres test database is unavailable. Start PostgreSQL on localhost:5432 "
    "or run `docker compose up -d postgres` before running tests."
)


def get_test_database_url() -> str:
    return os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


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


def ensure_test_database() -> None:
    admin_engine, database_name = _build_admin_engine()
    try:
        with admin_engine.connect() as connection:
            exists = connection.exec_driver_sql(
                "SELECT 1 FROM pg_database WHERE datname = %(database_name)s",
                {"database_name": database_name},
            ).scalar()
            if exists is None:
                connection.exec_driver_sql(f"CREATE DATABASE {_quote_identifier(database_name)}")
    except OperationalError as exc:
        raise RuntimeError(POSTGRES_UNAVAILABLE_MESSAGE) from exc
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


def reset_schema(engine: Engine) -> None:
    close_all_sessions()
    engine.dispose()
    with engine.begin() as connection:
        Base.metadata.create_all(connection)
        # `TRUNCATE ... CASCADE` doesn't need dependency ordering, so avoid
        # `sorted_tables` here and skip SQLAlchemy's cycle warning for the
        # mutually dependent `users` / `esi_characters` schema.
        table_names = [
            f'{_quote_identifier(table.schema)}.{_quote_identifier(table.name)}'
            if table.schema
            else _quote_identifier(table.name)
            for table in sorted(
                Base.metadata.tables.values(),
                key=lambda table: ((table.schema or ""), table.name),
            )
        ]
        if table_names:
            connection.exec_driver_sql(f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE")


@lru_cache(maxsize=1)
def _get_test_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=create_test_engine(), expire_on_commit=False)


def build_test_session() -> Session:
    engine = create_test_engine()
    reset_schema(engine)
    session = _get_test_sessionmaker()()
    weakref.finalize(session, session.close)
    return session
