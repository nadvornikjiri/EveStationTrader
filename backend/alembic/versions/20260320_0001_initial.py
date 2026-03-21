"""initial schema

Revision ID: 20260320_0001
Revises:
Create Date: 2026-03-20 10:00:00
"""

from alembic import op

revision = "20260320_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db.base import Base
    from app.models import all_models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from app.db.base import Base
    from app.models import all_models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
