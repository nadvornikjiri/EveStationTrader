"""Add target_price_source column to opportunity_items.

Revision ID: 20260416_0020
Revises: 20260415_0019
Create Date: 2026-04-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260416_0020"
down_revision = "20260415_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("opportunity_items")}
    if "target_price_source" not in columns:
        op.add_column(
            "opportunity_items",
            sa.Column("target_price_source", sa.String(16), nullable=False, server_default="live"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("opportunity_items")}
    if "target_price_source" in columns:
        op.drop_column("opportunity_items", "target_price_source")
