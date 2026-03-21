from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_database() -> None:
    from app.models import all_models  # noqa: F401
    from app.services.sync.foundation_data import FoundationDataService

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        FoundationDataService().bootstrap(session)
    finally:
        session.close()
