"""add ai communication tables

Revision ID: 2f5c3e0b9a21
Revises: 8fb4dd2e5a99
Create Date: 2026-04-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "2f5c3e0b9a21"
down_revision: Union[str, None] = "8fb4dd2e5a99"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    risk_level = sa.Enum("low", "medium", "high", name="airisklevel")
    draft_status = sa.Enum(
        "pending_review", "approved", "sent", "discarded", "failed",
        name="aidraftstatus"
    )
    action_type = sa.Enum(
        "classified",
        "classification_skipped",
        "draft_generated",
        "draft_failed",
        "draft_updated",
        "draft_approved",
        "draft_sent",
        "draft_discarded",
        name="aiactiontype",
    )

    op.create_table(
        "campaign_ai_playbooks",
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=True),
        sa.Column("product_description", sa.Text(), nullable=True),
        sa.Column("offer_summary", sa.Text(), nullable=True),
        sa.Column("deliverables", sa.Text(), nullable=True),
        sa.Column("sample_policy", sa.Text(), nullable=True),
        sa.Column("pricing_rules", sa.Text(), nullable=True),
        sa.Column("negotiation_limits", sa.Text(), nullable=True),
        sa.Column("prohibited_claims", sa.Text(), nullable=True),
        sa.Column("tone", sa.String(length=100), nullable=True),
        sa.Column("language", sa.String(length=50), nullable=True),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("reply_guidelines", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id"),
    )
    op.create_index(
        op.f("ix_campaign_ai_playbooks_campaign_id"),
        "campaign_ai_playbooks",
        ["campaign_id"],
        unique=False,
    )

    op.create_table(
        "ai_message_drafts",
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=True),
        sa.Column("influencer_id", sa.UUID(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("intent", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("status", draft_status, nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("missing_context", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_message_id", sa.UUID(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["influencer_id"], ["influencers.id"]),
        sa.ForeignKeyConstraint(["sent_message_id"], ["email_messages.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_message_drafts_campaign_id"), "ai_message_drafts", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_ai_message_drafts_conversation_id"), "ai_message_drafts", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_ai_message_drafts_influencer_id"), "ai_message_drafts", ["influencer_id"], unique=False)
    op.create_index(op.f("ix_ai_message_drafts_risk_level"), "ai_message_drafts", ["risk_level"], unique=False)
    op.create_index(op.f("ix_ai_message_drafts_status"), "ai_message_drafts", ["status"], unique=False)
    op.create_index(op.f("ix_ai_message_drafts_team_id"), "ai_message_drafts", ["team_id"], unique=False)

    op.create_table(
        "ai_action_logs",
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("campaign_id", sa.UUID(), nullable=True),
        sa.Column("draft_id", sa.UUID(), nullable=True),
        sa.Column("action_type", action_type, nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["draft_id"], ["ai_message_drafts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_action_logs_campaign_id"), "ai_action_logs", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_ai_action_logs_conversation_id"), "ai_action_logs", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_ai_action_logs_draft_id"), "ai_action_logs", ["draft_id"], unique=False)
    op.create_index(op.f("ix_ai_action_logs_team_id"), "ai_action_logs", ["team_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_action_logs_team_id"), table_name="ai_action_logs")
    op.drop_index(op.f("ix_ai_action_logs_draft_id"), table_name="ai_action_logs")
    op.drop_index(op.f("ix_ai_action_logs_conversation_id"), table_name="ai_action_logs")
    op.drop_index(op.f("ix_ai_action_logs_campaign_id"), table_name="ai_action_logs")
    op.drop_table("ai_action_logs")
    op.drop_index(op.f("ix_ai_message_drafts_team_id"), table_name="ai_message_drafts")
    op.drop_index(op.f("ix_ai_message_drafts_status"), table_name="ai_message_drafts")
    op.drop_index(op.f("ix_ai_message_drafts_risk_level"), table_name="ai_message_drafts")
    op.drop_index(op.f("ix_ai_message_drafts_influencer_id"), table_name="ai_message_drafts")
    op.drop_index(op.f("ix_ai_message_drafts_conversation_id"), table_name="ai_message_drafts")
    op.drop_index(op.f("ix_ai_message_drafts_campaign_id"), table_name="ai_message_drafts")
    op.drop_table("ai_message_drafts")
    op.drop_index(op.f("ix_campaign_ai_playbooks_campaign_id"), table_name="campaign_ai_playbooks")
    op.drop_table("campaign_ai_playbooks")
    op.execute("DROP TYPE IF EXISTS aiactiontype")
    op.execute("DROP TYPE IF EXISTS aidraftstatus")
    op.execute("DROP TYPE IF EXISTS airisklevel")
