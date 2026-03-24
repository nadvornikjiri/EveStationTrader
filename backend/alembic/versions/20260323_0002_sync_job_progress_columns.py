"""add sync job progress columns

Revision ID: 20260323_0002
Revises: 20260320_0001
Create Date: 2026-03-23 18:40:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260323_0002"
down_revision = "20260320_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("sync_job_runs")}

    if "progress_phase" not in existing_columns:
        op.add_column("sync_job_runs", sa.Column("progress_phase", sa.String(length=128), nullable=True))
    if "progress_current" not in existing_columns:
        op.add_column("sync_job_runs", sa.Column("progress_current", sa.Integer(), nullable=True))
    if "progress_total" not in existing_columns:
        op.add_column("sync_job_runs", sa.Column("progress_total", sa.Integer(), nullable=True))
    if "progress_unit" not in existing_columns:
        op.add_column("sync_job_runs", sa.Column("progress_unit", sa.String(length=32), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("sync_job_runs")}

    if "progress_unit" in existing_columns:
        op.drop_column("sync_job_runs", "progress_unit")
    if "progress_total" in existing_columns:
        op.drop_column("sync_job_runs", "progress_total")
    if "progress_current" in existing_columns:
        op.drop_column("sync_job_runs", "progress_current")
    if "progress_phase" in existing_columns:
        op.drop_column("sync_job_runs", "progress_phase")
