"""add bulk import tracking tables

Revision ID: 20260326_0006
Revises: 20260325_0005
Create Date: 2026-03-26 18:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260326_0006"
down_revision: str | None = "20260325_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "bulk_import_cursors" not in existing_tables:
        op.create_table(
            "bulk_import_cursors",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("import_kind", sa.String(length=64), nullable=False),
            sa.Column("scope_key", sa.String(length=128), nullable=False),
            sa.Column("synced_through_date", sa.Date(), nullable=True),
            sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_completed_key", sa.String(length=256), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("import_kind", "scope_key"),
        )

    existing_cursor_indexes = {
        index["name"] for index in inspector.get_indexes("bulk_import_cursors")
    } if "bulk_import_cursors" in inspector.get_table_names() else set()
    target_cursor_index = op.f("ix_bulk_import_cursors_import_kind")
    if target_cursor_index not in existing_cursor_indexes:
        op.create_index(target_cursor_index, "bulk_import_cursors", ["import_kind"], unique=False)

    if "bulk_import_files" not in existing_tables:
        op.create_table(
            "bulk_import_files",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("import_kind", sa.String(length=64), nullable=False),
            sa.Column("file_key", sa.String(length=256), nullable=False),
            sa.Column("remote_path", sa.Text(), nullable=False),
            sa.Column("local_path", sa.Text(), nullable=False),
            sa.Column("covered_date", sa.Date(), nullable=True),
            sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("import_kind", "file_key"),
        )

    existing_file_indexes = {
        index["name"] for index in inspector.get_indexes("bulk_import_files")
    } if "bulk_import_files" in inspector.get_table_names() else set()
    target_file_index = op.f("ix_bulk_import_files_import_kind")
    if target_file_index not in existing_file_indexes:
        op.create_index(target_file_index, "bulk_import_files", ["import_kind"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bulk_import_files_import_kind"), table_name="bulk_import_files")
    op.drop_table("bulk_import_files")
    op.drop_index(op.f("ix_bulk_import_cursors_import_kind"), table_name="bulk_import_cursors")
    op.drop_table("bulk_import_cursors")
