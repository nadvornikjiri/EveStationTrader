from datetime import UTC, date, datetime

from sqlalchemy import (
    Column,
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    Table,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    primary_character_id: Mapped[int | None] = mapped_column(ForeignKey("esi_characters.id"), nullable=True)


class EsiCharacter(Base):
    __tablename__ = "esi_characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    character_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    character_name: Mapped[str] = mapped_column(String(255))
    corporation_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    granted_scopes: Mapped[str] = mapped_column(Text, default="")
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EsiCharacterToken(Base):
    __tablename__ = "esi_character_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("esi_characters.id"), unique=True)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class EsiCharacterSyncState(Base):
    __tablename__ = "esi_character_sync_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("esi_characters.id"), unique=True)
    last_token_refresh: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assets_sync_status: Mapped[str] = mapped_column(String(50), default="pending")
    orders_sync_status: Mapped[str] = mapped_column(String(50), default="pending")
    skills_sync_status: Mapped[str] = mapped_column(String(50), default="pending")
    structures_sync_status: Mapped[str] = mapped_column(String(50), default="pending")


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))


class System(Base):
    __tablename__ = "systems"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[int] = mapped_column(unique=True, index=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    name: Mapped[str] = mapped_column(String(255))
    security_status: Mapped[float] = mapped_column(Float, default=0.0)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    type_id: Mapped[int] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    volume_m3: Mapped[float] = mapped_column(Float, default=0.0)
    group_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("systems.id"))
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    name: Mapped[str] = mapped_column(String(255))


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    location_type: Mapped[str] = mapped_column(String(32))
    system_id: Mapped[int] = mapped_column(ForeignKey("systems.id"))
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    name: Mapped[str] = mapped_column(String(255))


class TrackedStructure(Base):
    __tablename__ = "tracked_structures"

    id: Mapped[int] = mapped_column(primary_key=True)
    structure_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    system_id: Mapped[int] = mapped_column(ForeignKey("systems.id"))
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    tracking_tier: Mapped[str] = mapped_column(String(32), default="secondary")
    poll_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_by_character_id: Mapped[int | None] = mapped_column(ForeignKey("esi_characters.id"), nullable=True)


class CharacterAccessibleStructure(Base):
    __tablename__ = "character_accessible_structures"
    __table_args__ = (UniqueConstraint("character_id", "structure_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("esi_characters.id"))
    structure_id: Mapped[int] = mapped_column(BigInteger, index=True)
    structure_name: Mapped[str] = mapped_column(String(255))
    system_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    tracking_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    polling_tier: Mapped[str] = mapped_column(String(32), default="user")
    last_snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)


class CharacterAsset(Base):
    __tablename__ = "character_assets"
    __table_args__ = (UniqueConstraint("character_id", "type_id", "external_location_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("esi_characters.id"), index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    quantity: Mapped[int] = mapped_column(BigInteger, default=0)
    external_location_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    resolved_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CharacterOrder(Base):
    __tablename__ = "character_orders"
    __table_args__ = (UniqueConstraint("order_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("esi_characters.id"), index=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    volume_remain: Mapped[int] = mapped_column(Integer, default=0)
    is_buy_order: Mapped[bool] = mapped_column(Boolean, default=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    external_location_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    resolved_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    issued: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class InTransitAsset(Base):
    __tablename__ = "in_transit_assets"
    __table_args__ = (UniqueConstraint("source_location_id", "target_location_id", "type_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    target_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AdamMarketPriceHistoryDaily(Base):
    __tablename__ = "adam_market_price_history_daily"
    __table_args__ = (UniqueConstraint("location_id", "type_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    date: Mapped[date] = mapped_column(Date)
    average: Mapped[float] = mapped_column(Float)
    highest: Mapped[float] = mapped_column(Float)
    lowest: Mapped[float] = mapped_column(Float)
    order_count: Mapped[int] = mapped_column(Integer)
    volume: Mapped[int] = mapped_column(Integer)


class AdamMarketPriceSyncState(Base):
    __tablename__ = "adam_market_price_sync_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), unique=True, index=True)
    synced_through_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EsiHistoryDaily(Base):
    __tablename__ = "esi_history_daily"
    __table_args__ = (UniqueConstraint("region_id", "type_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    date: Mapped[date] = mapped_column(Date)
    average: Mapped[float] = mapped_column(Float)
    highest: Mapped[float] = mapped_column(Float)
    lowest: Mapped[float] = mapped_column(Float)
    order_count: Mapped[int] = mapped_column(Integer)
    volume: Mapped[int] = mapped_column(BigInteger)


class EveRefHistorySyncState(Base):
    __tablename__ = "everef_history_sync_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    history_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EsiMarketOrder(Base):
    __tablename__ = "esi_market_orders"
    __table_args__ = (UniqueConstraint("order_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("systems.id"))
    is_buy_order: Mapped[bool] = mapped_column(Boolean)
    price: Mapped[float] = mapped_column(Float)
    volume_total: Mapped[int] = mapped_column(Integer)
    volume_remain: Mapped[int] = mapped_column(Integer)
    min_volume: Mapped[int] = mapped_column(Integer, default=1)
    order_range: Mapped[str] = mapped_column(String(32), default="region")
    issued: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


AdamMarketOrdersTradeRaw = Table(
    "adam_market_orders_trade_raw",
    Base.metadata,
    Column("location_id", BigInteger, nullable=False),
    Column("region_id", Integer, nullable=False),
    Column("type_id", Integer, nullable=False),
    Column("is_buy_order", Integer, nullable=False),
    Column("has_gone", Integer, nullable=False),
    Column("scanDate", Date, nullable=False),
    Column("amount", Float, nullable=False),
    Column("high", Float, nullable=False),
    Column("low", Float, nullable=False),
    Column("avg", Float, nullable=False),
    Column("orderNum", Integer, nullable=False),
    Column("iskValue", Float, nullable=False),
)


AdamPriceHistoryStage = Table(
    "adam_price_history_stage",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("location_id", BigInteger, nullable=False),
    Column("region_id", Integer, nullable=False),
    Column("type_id", Integer, nullable=False),
    Column("date", Date, nullable=False),
    Column("buy_price_low", Float, nullable=True),
    Column("buy_price_avg", Float, nullable=True),
    Column("buy_price_high", Float, nullable=True),
    Column("sell_price_low", Float, nullable=True),
    Column("sell_price_avg", Float, nullable=True),
    Column("sell_price_high", Float, nullable=True),
    Column("export_key", Text, nullable=False),
    UniqueConstraint("location_id", "type_id", "date"),
    Index("ix_adam_price_history_stage_export_key", "export_key"),
)


AdamVolumeHistoryStage = Table(
    "adam_volume_history_stage",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("location_id", BigInteger, nullable=False),
    Column("region_id", Integer, nullable=False),
    Column("type_id", Integer, nullable=False),
    Column("date", Date, nullable=False),
    Column("sell_volume_avg", BigInteger, nullable=True),
    Column("export_key", Text, nullable=False),
    UniqueConstraint("location_id", "type_id", "date"),
    Index("ix_adam_volume_history_stage_export_key", "export_key"),
)



class AdamMarketVolumeHistoryDaily(Base):
    __tablename__ = "adam_market_volume_history_daily"
    __table_args__ = (
        UniqueConstraint("location_id", "type_id", "date"),
        Index("ix_adam_market_volume_history_daily_location_id_type_id", "location_id", "type_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    date: Mapped[date] = mapped_column(Date)
    sell_volume_avg: Mapped[int] = mapped_column(BigInteger)


class AdamNpcDemandSyncState(Base):
    __tablename__ = "adam_npc_demand_sync_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), unique=True, index=True)
    export_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    synced_through_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BulkImportCursor(Base):
    __tablename__ = "bulk_import_cursors"
    __table_args__ = (UniqueConstraint("import_kind", "scope_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    import_kind: Mapped[str] = mapped_column(String(64), index=True)
    scope_key: Mapped[str] = mapped_column(String(128))
    synced_through_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_completed_key: Mapped[str | None] = mapped_column(String(256), nullable=True)


class BulkImportFile(Base):
    __tablename__ = "bulk_import_files"
    __table_args__ = (UniqueConstraint("import_kind", "file_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    import_kind: Mapped[str] = mapped_column(String(64), index=True)
    file_key: Mapped[str] = mapped_column(String(256))
    remote_path: Mapped[str] = mapped_column(Text)
    local_path: Mapped[str] = mapped_column(Text)
    covered_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class StructureSnapshot(Base):
    __tablename__ = "structure_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    structure_id: Mapped[int] = mapped_column(BigInteger, index=True)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class StructureSnapshotOrder(Base):
    __tablename__ = "structure_snapshot_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("structure_snapshots.id"))
    structure_id: Mapped[int] = mapped_column(BigInteger, index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    order_id: Mapped[int] = mapped_column(BigInteger, index=True)
    is_buy_order: Mapped[bool] = mapped_column(Boolean)
    price: Mapped[float] = mapped_column(Float)
    volume_remain: Mapped[int] = mapped_column(Integer)
    issued: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)


class StructureOrderDelta(Base):
    __tablename__ = "structure_order_deltas"

    id: Mapped[int] = mapped_column(primary_key=True)
    structure_id: Mapped[int] = mapped_column(BigInteger, index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    order_id: Mapped[int] = mapped_column(BigInteger, index=True)
    from_snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    to_snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    old_volume: Mapped[int] = mapped_column(Integer)
    new_volume: Mapped[int] = mapped_column(Integer)
    delta_volume: Mapped[int] = mapped_column(Integer)
    disappeared: Mapped[bool] = mapped_column(Boolean, default=False)
    inferred_trade_side: Mapped[str | None] = mapped_column(String(32), nullable=True)
    inferred_trade_units: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[float] = mapped_column(Float)


class StructureDemandPeriod(Base):
    __tablename__ = "structure_demand_period"
    __table_args__ = (UniqueConstraint("structure_id", "type_id", "period_days"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    structure_id: Mapped[int] = mapped_column(BigInteger, index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    period_days: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    buy_from_sell_period: Mapped[float] = mapped_column(Float)
    sell_to_buy_period: Mapped[float] = mapped_column(Float)
    coverage_pct: Mapped[float] = mapped_column(Float)


class NpcStationOrderDelta(Base):
    __tablename__ = "npc_station_order_deltas"
    __table_args__ = (
        Index("ix_npc_delta_loc_type_time", "location_id", "type_id", "to_snapshot_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    order_id: Mapped[int] = mapped_column(BigInteger)
    from_snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    to_snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    old_volume: Mapped[int] = mapped_column(Integer)
    new_volume: Mapped[int] = mapped_column(Integer)
    delta_volume: Mapped[int] = mapped_column(Integer)
    disappeared: Mapped[bool] = mapped_column(Boolean, default=False)
    inferred_trade_side: Mapped[str | None] = mapped_column(String(32), nullable=True)
    inferred_trade_units: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[float] = mapped_column(Float)


class NpcStationDemandPeriod(Base):
    __tablename__ = "npc_station_demand_period"
    __table_args__ = (UniqueConstraint("location_id", "type_id", "period_days"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    period_days: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    buy_from_sell_period: Mapped[float] = mapped_column(Float)
    sell_to_buy_period: Mapped[float] = mapped_column(Float)
    coverage_pct: Mapped[float] = mapped_column(Float)


class MarketPricePeriod(Base):
    __tablename__ = "market_price_period"
    __table_args__ = (UniqueConstraint("location_id", "type_id", "period_days"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    period_days: Mapped[int] = mapped_column(Integer)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    period_avg_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MarketVolumePeriod(Base):
    __tablename__ = "market_volume_period"
    __table_args__ = (
        UniqueConstraint("location_id", "type_id", "period_days"),
        Index("ix_market_volume_period_location_id_type_id", "location_id", "type_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    period_days: Mapped[int] = mapped_column(Integer)
    current_sell_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    period_avg_sell_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MarketDemandResolved(Base):
    __tablename__ = "market_demand_resolved"
    __table_args__ = (UniqueConstraint("location_id", "type_id", "period_days"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    period_days: Mapped[int] = mapped_column(Integer)
    demand_source: Mapped[str] = mapped_column(String(32))
    buy_from_sell_period: Mapped[float] = mapped_column(Float)
    sell_to_buy_period: Mapped[float] = mapped_column(Float)
    esi_live_valid_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    esi_live_buy_from_sell_ratio_period: Mapped[float | None] = mapped_column(Float, nullable=True)
    esi_live_buy_from_sell_ratio_yesterday: Mapped[float | None] = mapped_column(Float, nullable=True)
    esi_live_fallback_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OpportunityItem(Base):
    __tablename__ = "opportunity_items"
    __table_args__ = (UniqueConstraint("target_location_id", "source_location_id", "type_id", "period_days"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    target_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    source_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    type_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    period_days: Mapped[int] = mapped_column(Integer)
    purchase_units: Mapped[float] = mapped_column(Float)
    source_units_available: Mapped[float] = mapped_column(Float)
    target_demand_day: Mapped[float] = mapped_column(Float)
    target_supply_units: Mapped[float] = mapped_column(Float)
    target_dos: Mapped[float] = mapped_column(Float)
    in_transit_units: Mapped[float] = mapped_column(Float, default=0.0)
    assets_units: Mapped[float] = mapped_column(Float, default=0.0)
    active_sell_orders_units: Mapped[float] = mapped_column(Float, default=0.0)
    source_station_sell_price: Mapped[float] = mapped_column(Float)
    target_station_sell_price: Mapped[float] = mapped_column(Float)
    target_period_avg_price: Mapped[float] = mapped_column(Float)
    target_now_profit: Mapped[float] = mapped_column(Float)
    target_period_profit: Mapped[float] = mapped_column(Float)
    capital_required: Mapped[float] = mapped_column(Float)
    roi_now: Mapped[float] = mapped_column(Float)
    roi_period: Mapped[float] = mapped_column(Float)
    source_security_status: Mapped[float] = mapped_column(Float, default=0.0)
    item_volume_m3: Mapped[float] = mapped_column(Float)
    shipping_cost: Mapped[float] = mapped_column(Float, default=0.0)
    demand_source: Mapped[str] = mapped_column(String(32))
    esi_demand_day: Mapped[float] = mapped_column(Float, default=0.0)
    target_price_source: Mapped[str] = mapped_column(String(16), default="live", server_default="live")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OpportunitySourceSummary(Base):
    __tablename__ = "opportunity_source_summaries"
    __table_args__ = (UniqueConstraint("target_location_id", "source_location_id", "period_days"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    target_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    source_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    source_security_status: Mapped[float] = mapped_column(Float, default=0.0)
    period_days: Mapped[int] = mapped_column(Integer)
    purchase_units_total: Mapped[float] = mapped_column(Float)
    source_units_available_total: Mapped[float] = mapped_column(Float)
    target_demand_day_total: Mapped[float] = mapped_column(Float)
    target_supply_units_total: Mapped[float] = mapped_column(Float)
    target_dos_weighted: Mapped[float] = mapped_column(Float)
    in_transit_units: Mapped[float] = mapped_column(Float, default=0.0)
    assets_units: Mapped[float] = mapped_column(Float, default=0.0)
    active_sell_orders_units: Mapped[float] = mapped_column(Float, default=0.0)
    source_avg_price_weighted: Mapped[float] = mapped_column(Float)
    target_now_price_weighted: Mapped[float] = mapped_column(Float)
    target_period_avg_price_weighted: Mapped[float] = mapped_column(Float)
    target_now_profit_weighted: Mapped[float] = mapped_column(Float)
    target_period_profit_weighted: Mapped[float] = mapped_column(Float)
    capital_required_total: Mapped[float] = mapped_column(Float)
    roi_now_weighted: Mapped[float] = mapped_column(Float)
    roi_period_weighted: Mapped[float] = mapped_column(Float)
    total_item_volume_m3: Mapped[float] = mapped_column(Float)
    shipping_cost_total: Mapped[float] = mapped_column(Float)
    demand_source_summary: Mapped[str] = mapped_column(String(32))
    esi_demand_day_total: Mapped[float] = mapped_column(Float, default=0.0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SyncJobRun(Base):
    __tablename__ = "sync_job_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    triggered_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    progress_phase: Mapped[str | None] = mapped_column(String(128), nullable=True)
    progress_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)


class SyncJobStageRun(Base):
    __tablename__ = "sync_job_stage_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_run_id: Mapped[int] = mapped_column(ForeignKey("sync_job_runs.id"), index=True)
    stage_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(64), default="worker", index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    status: Mapped[str] = mapped_column(String(32), default="healthy")


class UserSetting(Base):
    __tablename__ = "user_settings"
    __table_args__ = (UniqueConstraint("user_id", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    key: Mapped[str] = mapped_column(String(128))
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
