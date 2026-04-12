"""add sync job stage runs

Revision ID: 20260410_0014
Revises: 20260409_0013
Create Date: 2026-04-10 08:45:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260410_0014"
down_revision = "20260409_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "sync_job_stage_runs" in existing_tables:
        return

    op.create_table(
        "sync_job_stage_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_run_id", sa.Integer(), nullable=False),
        sa.Column("stage_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["job_run_id"], ["sync_job_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sync_job_stage_runs_job_run_id",
        "sync_job_stage_runs",
        ["job_run_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "sync_job_stage_runs" not in existing_tables:
        return

    op.drop_index("ix_sync_job_stage_runs_job_run_id", table_name="sync_job_stage_runs")
    op.drop_table("sync_job_stage_runs")
