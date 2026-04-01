"""split Adam4EVE raw staging from resolved demand

Revision ID: 20260328_0008
Revises: 20260328_0007
Create Date: 2026-03-28 18:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260328_0008"
down_revision: str | None = "20260328_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "adam_npc_demand_daily" in table_names:
        op.drop_table("adam_npc_demand_daily")

    if "adam_market_orders_trade_raw" not in table_names:
        op.create_table(
            "adam_market_orders_trade_raw",
            sa.Column("location_id", sa.BigInteger(), nullable=False),
            sa.Column("region_id", sa.Integer(), nullable=False),
            sa.Column("type_id", sa.Integer(), nullable=False),
            sa.Column("is_buy_order", sa.Integer(), nullable=False),
            sa.Column("has_gone", sa.Integer(), nullable=False),
            sa.Column("scanDate", sa.Date(), nullable=False),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("high", sa.Float(), nullable=False),
            sa.Column("low", sa.Float(), nullable=False),
            sa.Column("avg", sa.Float(), nullable=False),
            sa.Column("orderNum", sa.Integer(), nullable=False),
            sa.Column("iskValue", sa.Float(), nullable=False),
        )

    structure_columns = {column["name"] for column in inspector.get_columns("structure_demand_period")}
    for column_name in ("demand_min", "demand_max", "demand_chosen"):
        if column_name in structure_columns:
            op.drop_column("structure_demand_period", column_name)
    for column_name in (
        "buy_from_sell_period",
        "sell_to_buy_period",
        "buy_from_sell_yesterday",
        "sell_to_buy_yesterday",
    ):
        if column_name not in structure_columns:
            op.add_column(
                "structure_demand_period",
                sa.Column(column_name, sa.Float(), nullable=False, server_default="0"),
            )
            op.alter_column("structure_demand_period", column_name, server_default=None)

    demand_columns = {column["name"] for column in inspector.get_columns("market_demand_resolved")}
    if "demand_day" in demand_columns:
        op.drop_column("market_demand_resolved", "demand_day")
    for column_name in (
        "buy_from_sell_period",
        "sell_to_buy_period",
        "buy_from_sell_yesterday",
        "sell_to_buy_yesterday",
    ):
        if column_name not in demand_columns:
            op.add_column(
                "market_demand_resolved",
                sa.Column(column_name, sa.Float(), nullable=False, server_default="0"),
            )
            op.alter_column("market_demand_resolved", column_name, server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "adam_market_orders_trade_raw" in table_names:
        op.drop_table("adam_market_orders_trade_raw")

    if "adam_npc_demand_daily" not in table_names:
        op.create_table(
            "adam_npc_demand_daily",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("location_id", sa.Integer(), nullable=False),
            sa.Column("type_id", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("demand_day", sa.Float(), nullable=False),
            sa.Column("source_label", sa.String(length=64), nullable=False, server_default="adam4eve"),
            sa.Column("raw_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.UniqueConstraint("location_id", "type_id", "date"),
        )
        op.alter_column("adam_npc_demand_daily", "source_label", server_default=None)
        op.alter_column("adam_npc_demand_daily", "raw_payload", server_default=None)

    structure_columns = {column["name"] for column in inspector.get_columns("structure_demand_period")}
    for column_name in (
        "buy_from_sell_period",
        "sell_to_buy_period",
        "buy_from_sell_yesterday",
        "sell_to_buy_yesterday",
    ):
        if column_name in structure_columns:
            op.drop_column("structure_demand_period", column_name)
    for column_name in ("demand_min", "demand_max", "demand_chosen"):
        if column_name not in structure_columns:
            op.add_column(
                "structure_demand_period",
                sa.Column(column_name, sa.Float(), nullable=False, server_default="0"),
            )
            op.alter_column("structure_demand_period", column_name, server_default=None)

    demand_columns = {column["name"] for column in inspector.get_columns("market_demand_resolved")}
    for column_name in (
        "buy_from_sell_period",
        "sell_to_buy_period",
        "buy_from_sell_yesterday",
        "sell_to_buy_yesterday",
    ):
        if column_name in demand_columns:
            op.drop_column("market_demand_resolved", column_name)
    if "demand_day" not in demand_columns:
        op.add_column(
            "market_demand_resolved",
            sa.Column("demand_day", sa.Float(), nullable=False, server_default="0"),
        )
        op.alter_column("market_demand_resolved", "demand_day", server_default=None)
