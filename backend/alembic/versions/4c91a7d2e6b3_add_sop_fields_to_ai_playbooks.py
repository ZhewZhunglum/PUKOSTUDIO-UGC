"""add sop fields to ai playbooks

Revision ID: 4c91a7d2e6b3
Revises: 2f5c3e0b9a21
Create Date: 2026-05-09 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "4c91a7d2e6b3"
down_revision: Union[str, None] = "2f5c3e0b9a21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("campaign_ai_playbooks", sa.Column("campaign_objectives", sa.Text(), nullable=True))
    op.add_column("campaign_ai_playbooks", sa.Column("target_audience", sa.Text(), nullable=True))
    op.add_column("campaign_ai_playbooks", sa.Column("key_messages", sa.Text(), nullable=True))
    op.add_column("campaign_ai_playbooks", sa.Column("content_dos", sa.Text(), nullable=True))
    op.add_column("campaign_ai_playbooks", sa.Column("content_donts", sa.Text(), nullable=True))
    op.add_column("campaign_ai_playbooks", sa.Column("required_hashtags", sa.Text(), nullable=True))
    op.add_column("campaign_ai_playbooks", sa.Column("disclosure_requirements", sa.Text(), nullable=True))
    op.add_column("campaign_ai_playbooks", sa.Column("payment_terms", sa.Text(), nullable=True))
    op.add_column("campaign_ai_playbooks", sa.Column("usage_rights", sa.Text(), nullable=True))
    op.add_column("campaign_ai_playbooks", sa.Column("approval_process", sa.Text(), nullable=True))
    op.add_column(
        "campaign_ai_playbooks",
        sa.Column(
            "contract_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column("campaign_ai_playbooks", sa.Column("content_review_checklist", sa.Text(), nullable=True))
    op.add_column("campaign_ai_playbooks", sa.Column("posting_guidance", sa.Text(), nullable=True))
    op.add_column("campaign_ai_playbooks", sa.Column("performance_kpis", sa.Text(), nullable=True))
    op.add_column("campaign_ai_playbooks", sa.Column("competitor_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("campaign_ai_playbooks", "competitor_notes")
    op.drop_column("campaign_ai_playbooks", "performance_kpis")
    op.drop_column("campaign_ai_playbooks", "posting_guidance")
    op.drop_column("campaign_ai_playbooks", "content_review_checklist")
    op.drop_column("campaign_ai_playbooks", "contract_required")
    op.drop_column("campaign_ai_playbooks", "approval_process")
    op.drop_column("campaign_ai_playbooks", "usage_rights")
    op.drop_column("campaign_ai_playbooks", "payment_terms")
    op.drop_column("campaign_ai_playbooks", "disclosure_requirements")
    op.drop_column("campaign_ai_playbooks", "required_hashtags")
    op.drop_column("campaign_ai_playbooks", "content_donts")
    op.drop_column("campaign_ai_playbooks", "content_dos")
    op.drop_column("campaign_ai_playbooks", "key_messages")
    op.drop_column("campaign_ai_playbooks", "target_audience")
    op.drop_column("campaign_ai_playbooks", "campaign_objectives")
