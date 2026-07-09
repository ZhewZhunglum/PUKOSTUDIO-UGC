import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ClientCampaignStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    completed = "completed"
    archived = "archived"


class ClientCampaignInfluencerStatus(str, enum.Enum):
    queued = "queued"
    in_progress = "in_progress"
    replied = "replied"
    completed = "completed"
    unsubscribed = "unsubscribed"
    bounced = "bounced"


class ClientCampaign(BaseModel):
    __tablename__ = "client_campaigns"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ClientCampaignStatus] = mapped_column(
        Enum(ClientCampaignStatus), default=ClientCampaignStatus.draft
    )
    target_criteria: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    schedule_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    steps: Mapped[list["ClientCampaignStep"]] = relationship(
        "ClientCampaignStep", back_populates="campaign", cascade="all, delete-orphan",
        order_by="ClientCampaignStep.step_order"
    )
    clients: Mapped[list["ClientCampaignEnrollment"]] = relationship(
        "ClientCampaignEnrollment", back_populates="campaign", cascade="all, delete-orphan"
    )


class ClientCampaignStep(BaseModel):
    __tablename__ = "client_campaign_steps"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_campaigns.id", ondelete="CASCADE"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(20), default="initial")
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_templates.id"), nullable=False
    )
    delay_days: Mapped[int] = mapped_column(Integer, default=0)
    condition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    campaign: Mapped[ClientCampaign] = relationship("ClientCampaign", back_populates="steps")


class ClientCampaignEnrollment(BaseModel):
    __tablename__ = "client_campaign_enrollments"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_campaigns.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[ClientCampaignInfluencerStatus] = mapped_column(
        Enum(ClientCampaignInfluencerStatus), default=ClientCampaignInfluencerStatus.queued
    )
    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    campaign: Mapped[ClientCampaign] = relationship("ClientCampaign", back_populates="clients")
