"""add app_log_entries table

Revision ID: 20260612_0026
Revises: 20260526_0025
Create Date: 2026-06-12 08:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "20260612_0026"
down_revision = "20260526_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_log_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("log_level", sa.String(16), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_app_log_entries_created_at", "app_log_entries", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_app_log_entries_created_at", table_name="app_log_entries")
    op.drop_table("app_log_entries")
