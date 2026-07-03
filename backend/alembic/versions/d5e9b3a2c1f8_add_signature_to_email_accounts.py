"""add signature to email accounts

Revision ID: d5e9b3a2c1f8
Revises: c4d8a1f9e2b7
Create Date: 2026-06-01 16:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "d5e9b3a2c1f8"
down_revision: Union[str, None] = "c4d8a1f9e2b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "email_accounts",
        sa.Column(
            "signature_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column("email_accounts", sa.Column("signature_content", sa.Text(), nullable=True))
    op.add_column("email_accounts", sa.Column("signature_html", sa.Text(), nullable=True))
    op.add_column(
        "email_accounts",
        sa.Column(
            "signature_logo_attachment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_attachments.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("email_accounts", sa.Column("brand_color", sa.String(length=9), nullable=True))
    op.add_column("email_accounts", sa.Column("social_links", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("email_accounts", "social_links")
    op.drop_column("email_accounts", "brand_color")
    op.drop_column("email_accounts", "signature_logo_attachment_id")
    op.drop_column("email_accounts", "signature_html")
    op.drop_column("email_accounts", "signature_content")
    op.drop_column("email_accounts", "signature_enabled")
