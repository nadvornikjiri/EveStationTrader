"""add everef history sync state

Revision ID: 20260411_0015
Revises: 20260410_0014
Create Date: 2026-04-11 12:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260411_0015"
down_revision = "20260410_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "everef_history_sync_state" in existing_tables:
        return

    op.create_table(
        "everef_history_sync_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("history_date", sa.Date(), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("history_date"),
    )
    op.create_index(
        "ix_everef_history_sync_state_history_date",
        "everef_history_sync_state",
        ["history_date"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "everef_history_sync_state" not in existing_tables:
        return

    op.drop_index("ix_everef_history_sync_state_history_date", table_name="everef_history_sync_state")
    op.drop_table("everef_history_sync_state")

