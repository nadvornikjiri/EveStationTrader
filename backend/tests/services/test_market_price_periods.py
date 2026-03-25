from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import EsiHistoryDaily, Item, Location, MarketPricePeriod, Region, System
from app.services.pricing.market_price_periods import MarketPricePeriodService
from tests.db_test_utils import build_test_session


def build_session() -> Session:
    return build_test_session()


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


def seed_second_location(session: Session, *, region_id: int) -> int:
    system = session.scalar(select(System).where(System.region_id == region_id))
    assert system is not None
    location = Location(
        location_id=60008494,
        location_type="npc_station",
        system_id=system.id,
        region_id=region_id,
        name="Amarr VIII - Emperor Family Academy",
    )
    session.add(location)
    session.commit()
    return location.id


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
    )

    assert result.created is True
    assert result.history_points_used == 3
    assert result.row is not None
    assert result.row.current_price == 100.0
    assert result.row.period_avg_price == 100.0
    assert result.row.price_min == 80.0
    assert result.row.price_max == 130.0


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
    )

    assert result.row is not None
    assert result.history_points_used == 2
    assert result.row.period_avg_price == 150.0
    assert result.row.current_price == 100.0


def test_upsert_market_price_period_reuses_existing_row_without_risk_fields() -> None:
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
    )

    assert result.row is not None
    assert result.row.period_avg_price == 150.0
    assert result.row.current_price == 100.0


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


def test_refresh_region_from_history_computes_once_and_writes_all_locations() -> None:
    session = build_session()
    first_location_id, item_id, region_id = seed_location_and_item(session)
    second_location_id = seed_second_location(session, region_id=region_id)
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

    refreshed_count = MarketPricePeriodService().refresh_region_from_history(
        session,
        region_id=region_id,
        location_ids=[first_location_id, second_location_id],
        type_ids=[item_id],
        period_days=3,
    )
    rows = list(
        session.scalars(
            select(MarketPricePeriod).order_by(MarketPricePeriod.location_id.asc())
        ).all()
    )

    assert refreshed_count == 2
    assert len(rows) == 2
    assert [row.location_id for row in rows] == [first_location_id, second_location_id]
    assert all(row.current_price == 100.0 for row in rows)
    assert all(row.period_avg_price == 100.0 for row in rows)
    assert all(row.price_min == 80.0 for row in rows)
    assert all(row.price_max == 130.0 for row in rows)
