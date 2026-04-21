from typing import cast

from sqlalchemy import BigInteger, Float, Index, Table, UniqueConstraint

from app.models.all_models import (
    AdamMarketVolumeHistoryDaily,
    AdamMarketVolumeHistoryRaw,
    MarketVolumePeriod,
)


def test_adam_market_volume_history_raw_metadata_matches_expected_schema() -> None:
    assert AdamMarketVolumeHistoryRaw.name == "adam_market_volume_history_raw"
    assert isinstance(AdamMarketVolumeHistoryRaw.c.location_id.type, BigInteger)
    assert isinstance(AdamMarketVolumeHistoryRaw.c.region_id.type, BigInteger)
    assert isinstance(AdamMarketVolumeHistoryRaw.c.sell_volume_avg.type, BigInteger)

    unique_constraints = [
        constraint
        for constraint in AdamMarketVolumeHistoryRaw.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    assert any(
        tuple(column.name for column in constraint.columns) == ("location_id", "type_id", "date")
        for constraint in unique_constraints
    )
    assert any(
        isinstance(index, Index) and tuple(index.columns.keys()) == ("location_id", "type_id")
        for index in AdamMarketVolumeHistoryRaw.indexes
    )


def test_adam_market_volume_history_daily_metadata_matches_expected_schema() -> None:
    table = cast(Table, AdamMarketVolumeHistoryDaily.__table__)

    assert table.name == "adam_market_volume_history_daily"
    assert isinstance(table.c.sell_volume_avg.type, BigInteger)
    assert {fk.target_fullname for fk in table.c.location_id.foreign_keys} == {"locations.id"}
    assert {fk.target_fullname for fk in table.c.type_id.foreign_keys} == {"items.id"}
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(column.name for column in constraint.columns) == ("location_id", "type_id", "date")
        for constraint in table.constraints
    )
    assert any(
        isinstance(index, Index) and tuple(index.columns.keys()) == ("location_id", "type_id")
        for index in table.indexes
    )


def test_market_volume_period_metadata_matches_expected_schema() -> None:
    table = cast(Table, MarketVolumePeriod.__table__)

    assert table.name == "market_volume_period"
    assert isinstance(table.c.current_sell_volume.type, BigInteger)
    assert isinstance(table.c.period_avg_sell_volume.type, Float)
    assert table.c.current_sell_volume.nullable is True
    assert table.c.period_avg_sell_volume.nullable is True
    assert {fk.target_fullname for fk in table.c.location_id.foreign_keys} == {"locations.id"}
    assert {fk.target_fullname for fk in table.c.type_id.foreign_keys} == {"items.id"}
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(column.name for column in constraint.columns) == ("location_id", "type_id", "period_days")
        for constraint in table.constraints
    )
    assert any(
        isinstance(index, Index) and tuple(index.columns.keys()) == ("location_id", "type_id")
        for index in table.indexes
    )
