"""widen esi history volume to bigint

Revision ID: 20260409_0013
Revises: 20260409_0012
Create Date: 2026-04-09 18:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260409_0013"
down_revision: str | None = "20260409_0012"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())
    if "esi_history_daily" not in table_names:
        return

    columns = {column["name"]: column for column in inspector.get_columns("esi_history_daily")}
    volume_type = columns.get("volume", {}).get("type")
    if volume_type is None:
        return
    if str(volume_type).lower() == "integer":
        op.alter_column(
            "esi_history_daily",
            "volume",
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())
    if "esi_history_daily" not in table_names:
        return

    columns = {column["name"]: column for column in inspector.get_columns("esi_history_daily")}
    volume_type = columns.get("volume", {}).get("type")
    if volume_type is None:
        return
    if str(volume_type).lower() == "bigint":
        op.alter_column(
            "esi_history_daily",
            "volume",
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=False,
        )
