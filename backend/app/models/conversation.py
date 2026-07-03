import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AIIntent(str, enum.Enum):
    interested = "interested"
    not_interested = "not_interested"
    question = "question"
    negotiation = "negotiation"
    spam = "spam"
    unknown = "unknown"


class Conversation(BaseModel):
    __tablename__ = "conversations"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    influencer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("influencers.id"), nullable=False, unique=True
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    ai_intent: Mapped[AIIntent | None] = mapped_column(Enum(AIIntent), nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
