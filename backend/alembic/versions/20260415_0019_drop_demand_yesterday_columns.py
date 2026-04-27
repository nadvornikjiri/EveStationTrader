"""Drop stored demand-yesterday columns from demand tables.

Revision ID: 20260415_0019
Revises: 20260412_0018
Create Date: 2026-04-15 13:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260415_0019"
down_revision = "20260412_0018"
branch_labels = None
depends_on = None


def _drop_if_exists(table_name: str, column_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in columns:
        op.drop_column(table_name, column_name)


def _add_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {existing["name"] for existing in inspector.get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def upgrade() -> None:
    for table_name in ("structure_demand_period", "npc_station_demand_period", "market_demand_resolved"):
        _drop_if_exists(table_name, "buy_from_sell_yesterday")
        _drop_if_exists(table_name, "sell_to_buy_yesterday")


def downgrade() -> None:
    for table_name in ("structure_demand_period", "npc_station_demand_period", "market_demand_resolved"):
        _add_if_missing(table_name, sa.Column("buy_from_sell_yesterday", sa.Float(), nullable=False, server_default="0"))
        _add_if_missing(table_name, sa.Column("sell_to_buy_yesterday", sa.Float(), nullable=False, server_default="0"))
