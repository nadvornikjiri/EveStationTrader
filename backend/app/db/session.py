from collections.abc import Generator
from pathlib import Path
from time import sleep

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, future=True)
DATABASE_STARTUP_RETRY_ATTEMPTS = 60
DATABASE_STARTUP_RETRY_DELAY_SECONDS = 1.0

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_database() -> None:
    from app.services.sync.foundation_data import FoundationDataService
    from app.services.settings_service import SettingsService

    wait_for_database()
    run_migrations()
    session = SessionLocal()
    try:
        FoundationDataService().bootstrap(session)
    finally:
        session.close()
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
