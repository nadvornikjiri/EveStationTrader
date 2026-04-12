"""restore esi history daily tables

Revision ID: 20260409_0012
Revises: 20260409_0011
Create Date: 2026-04-09 15:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260409_0012"
down_revision: str | None = "20260409_0011"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

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
            sa.Column("volume", sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
            sa.ForeignKeyConstraint(["type_id"], ["items.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("region_id", "type_id", "date"),
        )
    else:
        columns = {column["name"]: column for column in inspector.get_columns("esi_history_daily")}
        volume_type = columns.get("volume", {}).get("type")
        if isinstance(volume_type, sa.Integer) and not isinstance(volume_type, sa.BigInteger):
            op.alter_column(
                "esi_history_daily",
                "volume",
                existing_type=sa.Integer(),
                type_=sa.BigInteger(),
                existing_nullable=False,
            )

    if "esi_history_sync_state" not in table_names:
        op.create_table(
            "esi_history_sync_state",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("region_id", sa.Integer(), nullable=False),
            sa.Column("synced_through_date", sa.Date(), nullable=True),
            sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("region_id"),
        )
        op.create_index(
            op.f("ix_esi_history_sync_state_region_id"),
            "esi_history_sync_state",
            ["region_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "esi_history_sync_state" in table_names:
        op.drop_index(op.f("ix_esi_history_sync_state_region_id"), table_name="esi_history_sync_state")
        op.drop_table("esi_history_sync_state")

    if "esi_history_daily" in table_names:
        op.drop_table("esi_history_daily")
