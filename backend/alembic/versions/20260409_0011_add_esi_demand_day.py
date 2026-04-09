"""Add esi_demand_day to opportunity_items and opportunity_source_summaries.

Revision ID: 20260409_0011
Revises: 20260409_0010
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260409_0011"
down_revision = "20260409_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "opportunity_items",
        sa.Column("esi_demand_day", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "opportunity_source_summaries",
        sa.Column("esi_demand_day_total", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("opportunity_source_summaries", "esi_demand_day_total")
    op.drop_column("opportunity_items", "esi_demand_day")
