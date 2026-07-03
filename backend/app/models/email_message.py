import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class EmailDirection(str, enum.Enum):
    outbound = "outbound"
    inbound = "inbound"


class EmailStatus(str, enum.Enum):
    queued = "queued"
    sending = "sending"
    sent = "sent"
    delivered = "delivered"
    opened = "opened"
    clicked = "clicked"
    bounced = "bounced"
    complained = "complained"
    failed = "failed"


class EmailEventType(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    opened = "opened"
    clicked = "clicked"
    bounced = "bounced"
    complained = "complained"
    unsubscribed = "unsubscribed"


class EmailMessage(BaseModel):
    __tablename__ = "email_messages"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True
    )
    campaign_step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_steps.id"), nullable=True
    )
    influencer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("influencers.id"), nullable=False, index=True
    )
    email_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_accounts.id"), nullable=True
    )
    direction: Mapped[EmailDirection] = mapped_column(Enum(EmailDirection), nullable=False)
    from_address: Mapped[str] = mapped_column(String(255), nullable=False)
    to_address: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    in_reply_to: Mapped[str | None] = mapped_column(String(500), nullable=True)
    references: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus), default=EmailStatus.queued, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    events: Mapped[list["EmailEvent"]] = relationship(
        "EmailEvent", back_populates="email_message", cascade="all, delete-orphan"
    )


class EmailEvent(BaseModel):
    __tablename__ = "email_events"

    email_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[EmailEventType] = mapped_column(Enum(EmailEventType), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    email_message: Mapped[EmailMessage] = relationship("EmailMessage", back_populates="events")
