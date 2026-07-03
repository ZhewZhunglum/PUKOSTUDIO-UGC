"""add ai_settings to teams

Revision ID: b2e9f4c7d1a3
Revises: a3f7e2c1d8b5
Create Date: 2026-05-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "b2e9f4c7d1a3"
down_revision = "a3f7e2c1d8b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column("ai_settings", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("teams", "ai_settings")
