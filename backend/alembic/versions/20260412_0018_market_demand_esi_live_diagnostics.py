"""add esi live diagnostics to market demand resolved

Revision ID: 20260412_0018
Revises: 20260412_0017
Create Date: 2026-04-12 20:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260412_0018"
down_revision: str | None = "20260412_0017"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("market_demand_resolved", sa.Column("esi_live_valid_days", sa.Integer(), nullable=True))
    op.add_column(
        "market_demand_resolved",
        sa.Column("esi_live_buy_from_sell_ratio_period", sa.Float(), nullable=True),
    )
    op.add_column(
        "market_demand_resolved",
        sa.Column("esi_live_buy_from_sell_ratio_yesterday", sa.Float(), nullable=True),
    )
    op.add_column(
        "market_demand_resolved",
        sa.Column("esi_live_fallback_reason", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("market_demand_resolved", "esi_live_fallback_reason")
    op.drop_column("market_demand_resolved", "esi_live_buy_from_sell_ratio_yesterday")
    op.drop_column("market_demand_resolved", "esi_live_buy_from_sell_ratio_period")
    op.drop_column("market_demand_resolved", "esi_live_valid_days")
