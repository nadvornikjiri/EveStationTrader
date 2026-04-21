"""add adam4eve volume history tables

Revision ID: 20260421_0022
Revises: 20260416_0021
Create Date: 2026-04-21 00:22:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260421_0022"
down_revision: str | None = "20260416_0021"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "adam_market_volume_history_raw",
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("region_id", sa.BigInteger(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sell_volume_avg", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("location_id", "type_id", "date"),
    )
    op.create_index(
        "ix_adam_market_volume_history_raw_location_id_type_id",
        "adam_market_volume_history_raw",
        ["location_id", "type_id"],
        unique=False,
    )

    op.create_table(
        "adam_market_volume_history_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sell_volume_avg", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["type_id"], ["items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("location_id", "type_id", "date"),
    )
    op.create_index(
        "ix_adam_market_volume_history_daily_location_id_type_id",
        "adam_market_volume_history_daily",
        ["location_id", "type_id"],
        unique=False,
    )

    op.create_table(
        "market_volume_period",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("period_days", sa.Integer(), nullable=False),
        sa.Column("current_sell_volume", sa.BigInteger(), nullable=True),
        sa.Column("period_avg_sell_volume", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["type_id"], ["items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("location_id", "type_id", "period_days"),
    )
    op.create_index(
        "ix_market_volume_period_location_id_type_id",
        "market_volume_period",
        ["location_id", "type_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_market_volume_period_location_id_type_id", table_name="market_volume_period")
    op.drop_table("market_volume_period")

    op.drop_index(
        "ix_adam_market_volume_history_daily_location_id_type_id",
        table_name="adam_market_volume_history_daily",
    )
    op.drop_table("adam_market_volume_history_daily")

    op.drop_index(
        "ix_adam_market_volume_history_raw_location_id_type_id",
        table_name="adam_market_volume_history_raw",
    )
    op.drop_table("adam_market_volume_history_raw")
