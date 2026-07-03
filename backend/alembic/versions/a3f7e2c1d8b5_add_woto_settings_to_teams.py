"""add woto_settings to teams

Revision ID: a3f7e2c1d8b5
Revises: 9d2a4e1f7b6c
Create Date: 2026-05-20 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "a3f7e2c1d8b5"
down_revision: Union[str, None] = "f18b3c4d5e6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column("woto_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("teams", "woto_settings")
