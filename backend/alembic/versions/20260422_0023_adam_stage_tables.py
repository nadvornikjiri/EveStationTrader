"""add adam_price_history_stage + adam_volume_history_stage, drop raw tables

Revision ID: 20260422_0023
Revises: 20260421_0022
Create Date: 2026-04-22 00:23:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260422_0023"
down_revision: str | None = "20260421_0022"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "adam_price_history_stage",
        sa.Column("id", sa.Integer(), nullable=False),
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
        sa.Column("export_key", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("location_id", "type_id", "date"),
    )
    op.create_index(
        "ix_adam_price_history_stage_export_key",
        "adam_price_history_stage",
        ["export_key"],
        unique=False,
    )

    op.create_table(
        "adam_volume_history_stage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sell_volume_avg", sa.BigInteger(), nullable=True),
        sa.Column("export_key", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("location_id", "type_id", "date"),
    )
    op.create_index(
        "ix_adam_volume_history_stage_export_key",
        "adam_volume_history_stage",
        ["export_key"],
        unique=False,
    )

    op.drop_index(
        "ix_adam_market_volume_history_raw_location_id_type_id",
        table_name="adam_market_volume_history_raw",
    )
    op.drop_table("adam_market_volume_history_raw")
    op.drop_table("adam_market_price_history_raw")


def downgrade() -> None:
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

    op.drop_index("ix_adam_volume_history_stage_export_key", table_name="adam_volume_history_stage")
    op.drop_table("adam_volume_history_stage")

    op.drop_index("ix_adam_price_history_stage_export_key", table_name="adam_price_history_stage")
    op.drop_table("adam_price_history_stage")
