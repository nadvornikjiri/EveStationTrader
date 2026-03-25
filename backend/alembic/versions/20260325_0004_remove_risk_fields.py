"""remove calculated risk fields

Revision ID: 20260325_0004
Revises: 20260325_0003
Create Date: 2026-03-25 23:20:00.000000
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect


revision: str = "20260325_0004"
down_revision: str | None = "20260325_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _drop_column_if_present(table_name: str, column_name: str) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name not in existing_columns:
        return
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_column(column_name)


def upgrade() -> None:
    _drop_column_if_present("market_price_period", "risk_pct")
    _drop_column_if_present("market_price_period", "warning_flag")
    _drop_column_if_present("opportunity_items", "risk_pct")
    _drop_column_if_present("opportunity_items", "warning_flag")
    _drop_column_if_present("opportunity_source_summaries", "risk_pct_weighted")
    _drop_column_if_present("opportunity_source_summaries", "warning_count")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for removed calculated risk fields.")
