"""add npc station order deltas and demand period tables

Revision ID: 20260409_0010
Revises: 20260328_0009
Create Date: 2026-04-09 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260409_0010"
down_revision: str | None = "20260328_0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "npc_station_order_deltas" not in existing_tables:
        op.create_table(
            "npc_station_order_deltas",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False),
            sa.Column("type_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
            sa.Column("order_id", sa.BigInteger(), nullable=False),
            sa.Column("from_snapshot_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("to_snapshot_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("old_volume", sa.Integer(), nullable=False),
            sa.Column("new_volume", sa.Integer(), nullable=False),
            sa.Column("delta_volume", sa.Integer(), nullable=False),
            sa.Column("disappeared", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("inferred_trade_side", sa.String(32), nullable=True),
            sa.Column("inferred_trade_units", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("price", sa.Float(), nullable=False),
        )

    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("npc_station_order_deltas")}
    if "ix_npc_delta_loc_type_time" not in existing_indexes:
        op.create_index(
            "ix_npc_delta_loc_type_time",
            "npc_station_order_deltas",
            ["location_id", "type_id", "to_snapshot_time"],
        )

    if "npc_station_demand_period" not in existing_tables:
        op.create_table(
            "npc_station_demand_period",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False),
            sa.Column("type_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
            sa.Column("period_days", sa.Integer(), nullable=False),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("buy_from_sell_period", sa.Float(), nullable=False),
            sa.Column("sell_to_buy_period", sa.Float(), nullable=False),
            sa.Column("buy_from_sell_yesterday", sa.Float(), nullable=False),
            sa.Column("sell_to_buy_yesterday", sa.Float(), nullable=False),
            sa.Column("coverage_pct", sa.Float(), nullable=False),
            sa.UniqueConstraint("location_id", "type_id", "period_days"),
        )


def downgrade() -> None:
    op.drop_table("npc_station_demand_period")
    op.drop_index("ix_npc_delta_loc_type_time", table_name="npc_station_order_deltas")
    op.drop_table("npc_station_order_deltas")
