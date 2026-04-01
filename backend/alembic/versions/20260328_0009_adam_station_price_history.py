"""rename market history tables to adam station history

Revision ID: 20260328_0009
Revises: 20260328_0008
Create Date: 2026-03-28 20:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260328_0009"
down_revision: str | None = "20260328_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "esi_history_daily" in table_names:
        op.drop_table("esi_history_daily")

    if "adam_market_price_history_raw" not in table_names:
        op.create_table(
            "adam_market_price_history_raw",
            sa.Column("location_id", sa.BigInteger(), nullable=False),
            sa.Column("region_id", sa.Integer(), nullable=False),
            sa.Column("type_id", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("buy_price_low", sa.Float(), nullable=True),
            sa.Column("buy_price_avg", sa.Float(), nullable=True),
            sa.Column("buy_price_high", sa.Float(), nullable=True),
            sa.Column("sell_price_low", sa.Float(), nullable=True),
            sa.Column("sell_price_avg", sa.Float(), nullable=True),
            sa.Column("sell_price_high", sa.Float(), nullable=True),
        )

    if "adam_market_price_history_daily" not in table_names:
        op.create_table(
            "adam_market_price_history_daily",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("location_id", sa.Integer(), nullable=False),
            sa.Column("type_id", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("average", sa.Float(), nullable=False),
            sa.Column("highest", sa.Float(), nullable=False),
            sa.Column("lowest", sa.Float(), nullable=False),
            sa.Column("order_count", sa.Integer(), nullable=False),
            sa.Column("volume", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
            sa.ForeignKeyConstraint(["type_id"], ["items.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("location_id", "type_id", "date"),
        )

    if "esi_history_sync_state" in table_names and "adam_market_price_sync_state" not in table_names:
        op.rename_table("esi_history_sync_state", "adam_market_price_sync_state")
        op.execute(
            sa.text(
                "ALTER INDEX IF EXISTS esi_history_sync_state_pkey "
                "RENAME TO adam_market_price_sync_state_pkey"
            )
        )
        op.execute(
            sa.text(
                "ALTER INDEX IF EXISTS ix_esi_history_sync_state_region_id "
                "RENAME TO ix_adam_market_price_sync_state_region_id"
            )
        )

    if "adam_market_price_sync_state" not in table_names and "esi_history_sync_state" not in table_names:
        op.create_table(
            "adam_market_price_sync_state",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("region_id", sa.Integer(), nullable=False),
            sa.Column("synced_through_date", sa.Date(), nullable=True),
            sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("region_id"),
        )
        op.create_index(
            op.f("ix_adam_market_price_sync_state_region_id"),
            "adam_market_price_sync_state",
            ["region_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "adam_market_price_history_daily" in table_names:
        op.drop_table("adam_market_price_history_daily")

    if "adam_market_price_history_raw" in table_names:
        op.drop_table("adam_market_price_history_raw")

    if "adam_market_price_sync_state" in table_names and "esi_history_sync_state" not in table_names:
        op.rename_table("adam_market_price_sync_state", "esi_history_sync_state")
        op.execute(
            sa.text(
                "ALTER INDEX IF EXISTS adam_market_price_sync_state_pkey "
                "RENAME TO esi_history_sync_state_pkey"
            )
        )
        op.execute(
            sa.text(
                "ALTER INDEX IF EXISTS ix_adam_market_price_sync_state_region_id "
                "RENAME TO ix_esi_history_sync_state_region_id"
            )
        )

    if "esi_history_daily" not in table_names:
        op.create_table(
            "esi_history_daily",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("region_id", sa.Integer(), nullable=False),
            sa.Column("type_id", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("average", sa.Float(), nullable=False),
            sa.Column("highest", sa.Float(), nullable=False),
            sa.Column("lowest", sa.Float(), nullable=False),
            sa.Column("order_count", sa.Integer(), nullable=False),
            sa.Column("volume", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
            sa.ForeignKeyConstraint(["type_id"], ["items.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("region_id", "type_id", "date"),
        )
