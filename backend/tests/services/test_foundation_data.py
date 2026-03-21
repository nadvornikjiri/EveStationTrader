from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.all_models import Location, Region, TrackedStructure, UserSetting
from app.services.sync.foundation_data import FoundationDataService


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_foundation_data_bootstrap_is_idempotent() -> None:
    session = build_session()
    service = FoundationDataService()

    first = service.bootstrap(session)
    second = service.bootstrap(session)

    assert first.records_processed > 0
    assert second.records_processed == 0


def test_foundation_data_bootstrap_seeds_core_entities() -> None:
    session = build_session()
    FoundationDataService().bootstrap(session)

    assert session.scalar(select(Region).where(Region.region_id == 10000002)) is not None
    assert session.scalar(select(Location).where(Location.location_id == 60003760)) is not None
    assert session.scalar(select(TrackedStructure).where(TrackedStructure.structure_id == 1022734985679)) is not None
    defaults = session.scalar(select(UserSetting).where(UserSetting.user_id.is_(None)))
    assert defaults is not None
    assert defaults.key == "defaults"
