"""drop esi history sync state

Revision ID: 20260411_0016
Revises: 20260411_0015
Create Date: 2026-04-11 12:05:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260411_0016"
down_revision: str | None = "20260411_0015"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("esi_history_sync_state")


def downgrade() -> None:
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
