"""add signature mode to email accounts

Revision ID: 59d9217f6c8c
Revises: 5641dfa5cbe1
Create Date: 2026-07-08 18:21:21.249383

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '59d9217f6c8c'
down_revision: Union[str, None] = '5641dfa5cbe1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    signature_mode = postgresql.ENUM(
        "structured", "custom", name="signaturemode", create_type=True,
    )
    signature_mode.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "email_accounts",
        sa.Column(
            "signature_mode", signature_mode,
            server_default="structured", nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("email_accounts", "signature_mode")
    postgresql.ENUM(name="signaturemode").drop(op.get_bind(), checkfirst=True)
