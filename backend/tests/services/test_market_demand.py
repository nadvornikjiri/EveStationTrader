from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.all_models import (
    AdamNpcDemandDaily,
    Item,
    Location,
    MarketDemandResolved,
    Region,
    StructureDemandPeriod,
    System,
)
from app.services.demand.market_demand import MarketDemandResolutionService


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def seed_locations_and_item(session: Session) -> tuple[int, int, int]:
    region = Region(region_id=10000002, name="The Forge")
    session.add(region)
    session.flush()

    system = System(system_id=30000142, region_id=region.id, name="Jita", security_status=0.9)
    session.add(system)
    session.flush()

    npc_location = Location(
        location_id=60003760,
        location_type="npc_station",
        system_id=system.id,
        region_id=region.id,
        name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    )
    structure_location = Location(
        location_id=1022734985679,
        location_type="structure",
        system_id=system.id,
        region_id=region.id,
        name="Perimeter Market Keepstar",
    )
    item = Item(type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all([npc_location, structure_location, item])
    session.commit()
    return npc_location.id, structure_location.id, item.id


def add_adam_history(session: Session, *, location_id: int, type_id: int, values: list[tuple[str, float]]) -> None:
    for row_date, demand_day in values:
        session.add(
            AdamNpcDemandDaily(
                location_id=location_id,
                type_id=type_id,
                date=date.fromisoformat(row_date),
                demand_day=demand_day,
                source_label="adam4eve",
                raw_payload={"demand_day": demand_day},
            )
        )
    session.commit()


def test_upsert_market_demand_uses_adam4eve_for_npc_targets() -> None:
    session = build_session()
    npc_location_id, _structure_location_id, item_id = seed_locations_and_item(session)
    add_adam_history(
        session,
        location_id=npc_location_id,
        type_id=item_id,
        values=[("2026-03-20", 12.0), ("2026-03-19", 18.0)],
    )

    result = MarketDemandResolutionService().upsert_for_location(
        session,
        location_id=npc_location_id,
        type_id=item_id,
        period_days=2,
    )

    assert result.created is True
    assert result.points_used == 2
    assert result.row is not None
    assert result.row.demand_source == "adam4eve"
    assert result.row.confidence_score == 1.0
    assert result.row.demand_day == 15.0


def test_upsert_market_demand_uses_available_adam_history_when_less_than_period() -> None:
    session = build_session()
    npc_location_id, _structure_location_id, item_id = seed_locations_and_item(session)
    add_adam_history(
        session,
        location_id=npc_location_id,
        type_id=item_id,
        values=[("2026-03-20", 12.0)],
    )

    result = MarketDemandResolutionService().upsert_for_location(
        session,
        location_id=npc_location_id,
        type_id=item_id,
        period_days=14,
    )

    assert result.row is not None
    assert result.points_used == 1
    assert result.row.demand_day == 12.0


def test_upsert_market_demand_deletes_stale_npc_row_when_no_history_exists() -> None:
    session = build_session()
    npc_location_id, _structure_location_id, item_id = seed_locations_and_item(session)
    session.add(
        MarketDemandResolved(
            location_id=npc_location_id,
            type_id=item_id,
            period_days=14,
            demand_source="adam4eve",
            confidence_score=1.0,
            demand_day=12.0,
        )
    )
    session.commit()

    result = MarketDemandResolutionService().upsert_for_location(
        session,
        location_id=npc_location_id,
        type_id=item_id,
        period_days=14,
    )

    assert result.created is False
    assert result.row is None
    assert result.points_used == 0
    assert session.query(MarketDemandResolved).count() == 0


def test_upsert_market_demand_uses_local_structure_period_when_confidence_is_sufficient() -> None:
    session = build_session()
    _npc_location_id, structure_location_id, item_id = seed_locations_and_item(session)
    session.add(
        StructureDemandPeriod(
            structure_id=1022734985679,
            type_id=item_id,
            period_days=14,
            demand_min=8.0,
            demand_max=12.0,
            demand_chosen=10.0,
            coverage_pct=0.8,
            confidence_score=0.9,
        )
    )
    session.commit()

    result = MarketDemandResolutionService().upsert_for_location(
        session,
        location_id=structure_location_id,
        type_id=item_id,
        period_days=14,
    )

    assert result.row is not None
    assert result.points_used == 1
    assert result.row.demand_source == "local_structure"
    assert result.row.confidence_score == 0.9
    assert result.row.demand_day == 10.0


def test_upsert_market_demand_falls_back_for_structure_when_confidence_is_insufficient() -> None:
    session = build_session()
    _npc_location_id, structure_location_id, item_id = seed_locations_and_item(session)
    session.add(
        StructureDemandPeriod(
            structure_id=1022734985679,
            type_id=item_id,
            period_days=14,
            demand_min=8.0,
            demand_max=12.0,
            demand_chosen=10.0,
            coverage_pct=0.5,
            confidence_score=0.9,
        )
    )
    session.commit()

    result = MarketDemandResolutionService().upsert_for_location(
        session,
        location_id=structure_location_id,
        type_id=item_id,
        period_days=14,
    )

    assert result.row is not None
    assert result.points_used == 0
    assert result.row.demand_source == "regional_fallback"
    assert result.row.confidence_score == 0.0
    assert result.row.demand_day == 0.0
