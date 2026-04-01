"""remove demand confidence columns

Revision ID: 20260328_0007
Revises: 20260326_0006
Create Date: 2026-03-28 12:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260328_0007"
down_revision: str | None = "20260326_0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    table_columns = {
        table_name: {column["name"] for column in inspector.get_columns(table_name)}
        for table_name in (
            "structure_demand_period",
            "market_demand_resolved",
            "opportunity_items",
            "opportunity_source_summaries",
        )
    }

    if "confidence_score" in table_columns["structure_demand_period"]:
        op.drop_column("structure_demand_period", "confidence_score")
    if "confidence_score" in table_columns["market_demand_resolved"]:
        op.drop_column("market_demand_resolved", "confidence_score")
    if "confidence_score" in table_columns["opportunity_items"]:
        op.drop_column("opportunity_items", "confidence_score")
    if "confidence_score_summary" in table_columns["opportunity_source_summaries"]:
        op.drop_column("opportunity_source_summaries", "confidence_score_summary")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    table_columns = {
        table_name: {column["name"] for column in inspector.get_columns(table_name)}
        for table_name in (
            "structure_demand_period",
            "market_demand_resolved",
            "opportunity_items",
            "opportunity_source_summaries",
        )
    }

    if "confidence_score" not in table_columns["structure_demand_period"]:
        op.add_column(
            "structure_demand_period",
            sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        )
        op.alter_column("structure_demand_period", "confidence_score", server_default=None)
    if "confidence_score" not in table_columns["market_demand_resolved"]:
        op.add_column(
            "market_demand_resolved",
            sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        )
        op.alter_column("market_demand_resolved", "confidence_score", server_default=None)
    if "confidence_score" not in table_columns["opportunity_items"]:
        op.add_column(
            "opportunity_items",
            sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        )
        op.alter_column("opportunity_items", "confidence_score", server_default=None)
    if "confidence_score_summary" not in table_columns["opportunity_source_summaries"]:
        op.add_column(
            "opportunity_source_summaries",
            sa.Column("confidence_score_summary", sa.Float(), nullable=False, server_default="0"),
        )
        op.alter_column("opportunity_source_summaries", "confidence_score_summary", server_default=None)
