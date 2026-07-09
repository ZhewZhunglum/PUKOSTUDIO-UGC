import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ClientEmailDirection(str, enum.Enum):
    outbound = "outbound"
    inbound = "inbound"


class ClientEmailStatus(str, enum.Enum):
    queued = "queued"
    sending = "sending"
    sent = "sent"
    delivered = "delivered"
    opened = "opened"
    clicked = "clicked"
    bounced = "bounced"
    complained = "complained"
    failed = "failed"


class ClientEmailEventType(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    opened = "opened"
    clicked = "clicked"
    bounced = "bounced"
    complained = "complained"
    unsubscribed = "unsubscribed"


class ClientEmailMessage(BaseModel):
    """Outbound/inbound email log for the B2B client-outreach pipeline.

    Deliberately a separate table from EmailMessage rather than making
    EmailMessage.influencer_id nullable — keeps the hardened influencer send
    path untouched at the cost of some structural duplication.
    """

    __tablename__ = "client_email_messages"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_campaigns.id"), nullable=True
    )
    campaign_step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_campaign_steps.id"), nullable=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True
    )
    email_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_accounts.id"), nullable=True
    )
    direction: Mapped[ClientEmailDirection] = mapped_column(
        Enum(ClientEmailDirection), nullable=False
    )
    from_address: Mapped[str] = mapped_column(String(255), nullable=False)
    to_address: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    in_reply_to: Mapped[str | None] = mapped_column(String(500), nullable=True)
    references: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ClientEmailStatus] = mapped_column(
        Enum(ClientEmailStatus), default=ClientEmailStatus.queued, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    events: Mapped[list["ClientEmailEvent"]] = relationship(
        "ClientEmailEvent", back_populates="client_email_message", cascade="all, delete-orphan"
    )


class ClientEmailEvent(BaseModel):
    __tablename__ = "client_email_events"

    client_email_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_email_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[ClientEmailEventType] = mapped_column(
        Enum(ClientEmailEventType), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    client_email_message: Mapped[ClientEmailMessage] = relationship(
        "ClientEmailMessage", back_populates="events"
    )
