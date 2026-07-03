"""add language and library to templates

Revision ID: e7b4a2c9d6f1
Revises: d5e9b3a2c1f8
Create Date: 2026-06-01 17:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e7b4a2c9d6f1"
down_revision: Union[str, None] = "d5e9b3a2c1f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "email_templates",
        sa.Column("language", sa.String(length=10), server_default="en", nullable=False),
    )
    op.add_column(
        "email_templates",
        sa.Column("is_library", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(op.f("ix_email_templates_language"), "email_templates", ["language"])
    op.create_index(op.f("ix_email_templates_is_library"), "email_templates", ["is_library"])


def downgrade() -> None:
    op.drop_index(op.f("ix_email_templates_is_library"), table_name="email_templates")
    op.drop_index(op.f("ix_email_templates_language"), table_name="email_templates")
    op.drop_column("email_templates", "is_library")
    op.drop_column("email_templates", "language")
