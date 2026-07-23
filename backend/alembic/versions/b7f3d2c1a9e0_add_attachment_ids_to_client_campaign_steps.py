"""add attachment_ids to client_campaign_steps

Revision ID: b7f3d2c1a9e0
Revises: a1c6e5d4b3f2
Create Date: 2026-07-23 00:00:01.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7f3d2c1a9e0"
down_revision: Union[str, None] = "a1c6e5d4b3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "client_campaign_steps",
        sa.Column("attachment_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("client_campaign_steps", "attachment_ids")
