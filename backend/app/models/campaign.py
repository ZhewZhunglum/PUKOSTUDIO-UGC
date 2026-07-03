import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    completed = "completed"
    archived = "archived"


class CampaignType(str, enum.Enum):
    ugc = "ugc"
    brand_promo = "brand_promo"
    tiktok_shop = "tiktok_shop"


class CampaignInfluencerStatus(str, enum.Enum):
    queued = "queued"
    in_progress = "in_progress"
    replied = "replied"
    completed = "completed"
    unsubscribed = "unsubscribed"
    bounced = "bounced"


class Campaign(BaseModel):
    __tablename__ = "campaigns"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus), default=CampaignStatus.draft
    )
    campaign_type: Mapped[CampaignType] = mapped_column(Enum(CampaignType), nullable=False)
    target_criteria: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    schedule_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    steps: Mapped[list["CampaignStep"]] = relationship(
        "CampaignStep", back_populates="campaign", cascade="all, delete-orphan",
        order_by="CampaignStep.step_order"
    )
    influencers: Mapped[list["CampaignInfluencer"]] = relationship(
        "CampaignInfluencer", back_populates="campaign", cascade="all, delete-orphan"
    )


class CampaignStep(BaseModel):
    __tablename__ = "campaign_steps"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(20), default="initial")
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_templates.id"), nullable=False
    )
    delay_days: Mapped[int] = mapped_column(Integer, default=0)
    condition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="steps")


class CampaignInfluencer(BaseModel):
    __tablename__ = "campaign_influencers"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    influencer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("influencers.id"), nullable=False
    )
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[CampaignInfluencerStatus] = mapped_column(
        Enum(CampaignInfluencerStatus), default=CampaignInfluencerStatus.queued
    )
    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="influencers")
