"""make adam_market_orders_trade_raw.region_id nullable

Revision ID: 20260526_0025
Revises: 20260427_0024
Create Date: 2026-05-26 09:30:00.000000

"""

from alembic import op

revision = "20260526_0025"
down_revision = "20260427_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "adam_market_orders_trade_raw",
        "region_id",
        nullable=True,
    )


def downgrade() -> None:
    op.execute("DELETE FROM adam_market_orders_trade_raw WHERE region_id IS NULL")
    op.alter_column(
        "adam_market_orders_trade_raw",
        "region_id",
        nullable=False,
    )
