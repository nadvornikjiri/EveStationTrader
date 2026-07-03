"""Add job_schedule_config table with default schedules.

Revision ID: 0024
Revises: 0023
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa

revision = "20260427_0024"
down_revision = "20260422_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_schedule_config",
        sa.Column("job_type", sa.String(64), primary_key=True),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("trigger_type", sa.String(16), nullable=False, server_default="interval"),
        sa.Column("interval_minutes", sa.Integer, nullable=True),
        sa.Column("cron_hour", sa.Integer, nullable=True),
        sa.Column("cron_minute", sa.Integer, nullable=True, server_default="0"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Seed default schedules matching previous hardcoded values,
    # plus the new opportunity_rebuild at 60-minute interval.
    op.execute(
        """
        INSERT INTO job_schedule_config (job_type, label, trigger_type, interval_minutes, cron_hour, cron_minute, enabled)
        VALUES
            ('esi_market_orders_sync', 'NPC Orders + Split Estimation', 'interval', 10, NULL, NULL, true),
            ('everef_history_sync',    'EVE Ref History Sync',          'cron',     NULL, 8,    0,    true),
            ('adam4eve_sync',          'Adam4EVE Sync',                 'cron',     NULL, 9,    0,    true),
            ('character_sync',         'Character Sync',                'interval', 15,  NULL, NULL, true),
            ('opportunity_rebuild',    'Opportunity Rebuild',           'interval', 60,  NULL, NULL, true)
        """
    )


def downgrade() -> None:
    op.drop_table("job_schedule_config")
