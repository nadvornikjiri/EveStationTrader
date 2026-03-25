"""add adam npc demand sync state

Revision ID: 20260325_0005
Revises: 20260325_0004
Create Date: 2026-03-25 23:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260325_0005"
down_revision: str | None = "20260325_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "adam_npc_demand_sync_state" not in inspector.get_table_names():
        op.create_table(
            "adam_npc_demand_sync_state",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("region_id", sa.Integer(), nullable=False),
            sa.Column("export_key", sa.String(length=128), nullable=True),
            sa.Column("synced_through_date", sa.Date(), nullable=True),
            sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("region_id"),
        )

    existing_indexes = {index["name"] for index in inspector.get_indexes("adam_npc_demand_sync_state")}
    target_index = op.f("ix_adam_npc_demand_sync_state_region_id")
    if target_index not in existing_indexes:
        op.create_index(
            target_index,
            "adam_npc_demand_sync_state",
            ["region_id"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_adam_npc_demand_sync_state_region_id"), table_name="adam_npc_demand_sync_state")
    op.drop_table("adam_npc_demand_sync_state")
