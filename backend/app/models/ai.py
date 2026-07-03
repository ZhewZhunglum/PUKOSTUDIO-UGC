import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AIRiskLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class AIDraftStatus(str, enum.Enum):
    pending_review = "pending_review"
    approved = "approved"
    sent = "sent"
    discarded = "discarded"
    failed = "failed"


class AIActionType(str, enum.Enum):
    classified = "classified"
    classification_skipped = "classification_skipped"
    draft_generated = "draft_generated"
    draft_failed = "draft_failed"
    draft_updated = "draft_updated"
    draft_approved = "draft_approved"
    draft_sent = "draft_sent"
    draft_discarded = "draft_discarded"


class CampaignAIPlaybook(BaseModel):
    __tablename__ = "campaign_ai_playbooks"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), unique=True,
        nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    product_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    product_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    offer_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    deliverables: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    pricing_rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    negotiation_limits: Mapped[str | None] = mapped_column(Text, nullable=True)
    prohibited_claims: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_guidelines: Mapped[str | None] = mapped_column(Text, nullable=True)
    campaign_objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_messages: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_dos: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_donts: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_hashtags: Mapped[str | None] = mapped_column(Text, nullable=True)
    disclosure_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage_rights: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_process: Mapped[str | None] = mapped_column(Text, nullable=True)
    contract_required: Mapped[bool] = mapped_column(Boolean, default=False)
    content_review_checklist: Mapped[str | None] = mapped_column(Text, nullable=True)
    posting_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    performance_kpis: Mapped[str | None] = mapped_column(Text, nullable=True)
    competitor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AIMessageDraft(BaseModel):
    __tablename__ = "ai_message_drafts"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True,
        index=True
    )
    influencer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("influencers.id"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[AIRiskLevel] = mapped_column(
        Enum(AIRiskLevel), default=AIRiskLevel.medium, index=True
    )
    status: Mapped[AIDraftStatus] = mapped_column(
        Enum(AIDraftStatus), default=AIDraftStatus.pending_review, index=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id"), nullable=True
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)


class AIActionLog(BaseModel):
    __tablename__ = "ai_action_logs"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True, index=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True,
        index=True
    )
    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_message_drafts.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    action_type: Mapped[AIActionType] = mapped_column(Enum(AIActionType), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
