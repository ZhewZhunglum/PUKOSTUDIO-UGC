import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EmailDigJobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class EmailDigJob(BaseModel):
    """A batch public-profile email extraction run (creator-finder port)."""

    __tablename__ = "email_dig_jobs"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    status: Mapped[EmailDigJobStatus] = mapped_column(
        Enum(EmailDigJobStatus), default=EmailDigJobStatus.queued, nullable=False, index=True
    )
    # "dig" = free public-profile crawl; "woto" = paid Woto contact backfill.
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="dig")
    default_platform: Mapped[str] = mapped_column(String(20), nullable=False, default="tiktok")
    input_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolved_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    found_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    phone_found_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # One row per input entry: {entry, influencer_id?, platform, handle, status,
    # emails, display_name, follower_count, applied}
    results: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
