"""add email attachments

Revision ID: c4d8a1f9e2b7
Revises: b2e9f4c7d1a3
Create Date: 2026-06-01 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "c4d8a1f9e2b7"
down_revision: Union[str, None] = "b2e9f4c7d1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    attachment_purpose = postgresql.ENUM(
        "email", "signature_logo", "snippet_asset", name="attachmentpurpose",
        create_type=False,
    )
    attachment_purpose.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "email_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column(
            "purpose",
            attachment_purpose,
            server_default="email",
            nullable=False,
        ),
        sa.Column(
            "email_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_email_attachments_team_id", "email_attachments", ["team_id"])
    op.create_index("ix_email_attachments_purpose", "email_attachments", ["purpose"])
    op.create_index(
        "ix_email_attachments_email_message_id", "email_attachments", ["email_message_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_email_attachments_email_message_id", table_name="email_attachments")
    op.drop_index("ix_email_attachments_purpose", table_name="email_attachments")
    op.drop_index("ix_email_attachments_team_id", table_name="email_attachments")
    op.drop_table("email_attachments")
    postgresql.ENUM(name="attachmentpurpose").drop(op.get_bind(), checkfirst=True)
