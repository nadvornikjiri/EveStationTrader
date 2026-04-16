"""Make market_price_period current_price and period_avg_price nullable

Revision ID: 20260416_0021
Revises: 20260416_0020
Create Date: 2026-04-16 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260416_0021"
down_revision = "20260416_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("market_price_period", "current_price", existing_type=sa.Float(), nullable=True)
    op.alter_column("market_price_period", "period_avg_price", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    op.alter_column("market_price_period", "current_price", existing_type=sa.Float(), nullable=False)
    op.alter_column("market_price_period", "period_avg_price", existing_type=sa.Float(), nullable=False)
