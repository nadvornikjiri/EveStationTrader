from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.all_models import EsiHistoryDaily, Item, Location, MarketPricePeriod, Region, System
from app.services.pricing.market_price_periods import MarketPricePeriodService


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def seed_location_and_item(session: Session) -> tuple[int, int, int]:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    session.add(system)
    session.flush()

    location = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=system.id,
        region_id=region.id,
        name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    )
    item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all([location, item])
    session.commit()
    return location.id, item.id, region.id


def add_history(
    session: Session,
    *,
    region_id: int,
    type_id: int,
    rows: list[tuple[str, float, float, float]],
) -> None:
    for row_date, average, highest, lowest in rows:
        session.add(
            EsiHistoryDaily(
                region_id=region_id,
                type_id=type_id,
                date=date.fromisoformat(row_date),
                average=average,
                highest=highest,
                lowest=lowest,
                order_count=10,
                volume=1000,
            )
        )
    session.commit()


def test_upsert_market_price_period_from_history() -> None:
    session = build_session()
    location_id, item_id, region_id = seed_location_and_item(session)
    add_history(
        session,
        region_id=region_id,
        type_id=item_id,
        rows=[
            ("2026-03-20", 100.0, 120.0, 90.0),
            ("2026-03-19", 110.0, 130.0, 95.0),
            ("2026-03-18", 90.0, 105.0, 80.0),
        ],
    )

    result = MarketPricePeriodService().upsert_from_history(
        session,
        location_id=location_id,
        type_id=item_id,
        period_days=3,
        warning_threshold=0.05,
    )

    assert result.created is True
    assert result.history_points_used == 3
    assert result.row is not None
    assert result.row.current_price == 100.0
    assert result.row.period_avg_price == 100.0
    assert result.row.price_min == 80.0
    assert result.row.price_max == 130.0
    assert result.row.risk_pct == 0.0
    assert result.row.warning_flag is False


def test_upsert_market_price_period_uses_available_history_when_less_than_period() -> None:
    session = build_session()
    location_id, item_id, region_id = seed_location_and_item(session)
    add_history(
        session,
        region_id=region_id,
        type_id=item_id,
        rows=[
            ("2026-03-20", 100.0, 120.0, 90.0),
            ("2026-03-19", 200.0, 210.0, 180.0),
        ],
    )

    result = MarketPricePeriodService().upsert_from_history(
        session,
        location_id=location_id,
        type_id=item_id,
        period_days=5,
        warning_threshold=0.49,
    )

    assert result.row is not None
    assert result.history_points_used == 2
    assert result.row.period_avg_price == 150.0
    assert result.row.current_price == 100.0
    assert result.row.risk_pct == 0.5
    assert result.row.warning_flag is True


def test_upsert_market_price_period_threshold_boundary_is_not_warning() -> None:
    session = build_session()
    location_id, item_id, region_id = seed_location_and_item(session)
    add_history(
        session,
        region_id=region_id,
        type_id=item_id,
        rows=[
            ("2026-03-20", 100.0, 110.0, 90.0),
            ("2026-03-19", 200.0, 210.0, 180.0),
        ],
    )

    result = MarketPricePeriodService().upsert_from_history(
        session,
        location_id=location_id,
        type_id=item_id,
        period_days=2,
        warning_threshold=0.5,
    )

    assert result.row is not None
    assert result.row.risk_pct == 0.5
    assert result.row.warning_flag is False


def test_upsert_market_price_period_empty_history_returns_none_and_cleans_existing_row() -> None:
    session = build_session()
    location_id, item_id, _region_id = seed_location_and_item(session)
    session.add(
        MarketPricePeriod(
            location_id=location_id,
            type_id=item_id,
            period_days=14,
            current_price=10.0,
            period_avg_price=11.0,
            price_min=9.0,
            price_max=12.0,
            risk_pct=0.1,
            warning_flag=False,
        )
    )
    session.commit()

    result = MarketPricePeriodService().upsert_from_history(
        session,
        location_id=location_id,
        type_id=item_id,
        period_days=14,
    )

    assert result.created is False
    assert result.row is None
    assert result.history_points_used == 0
    assert session.query(MarketPricePeriod).count() == 0
