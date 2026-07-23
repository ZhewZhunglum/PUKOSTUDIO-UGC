"""add attachment_ids to campaign_steps

Revision ID: a1c6e5d4b3f2
Revises: 7e1c9a4b2d3f
Create Date: 2026-07-23 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1c6e5d4b3f2"
down_revision: Union[str, None] = "7e1c9a4b2d3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campaign_steps",
        sa.Column("attachment_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("campaign_steps", "attachment_ids")
