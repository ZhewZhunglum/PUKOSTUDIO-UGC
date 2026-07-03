import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class WotoSyncJobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class WotoBillingOperation(str, enum.Enum):
    influencer_search = "influencer_search"
    influencer_detail = "influencer_detail"
    video_data = "video_data"
    contact_email = "contact_email"
    brand_monitoring = "brand_monitoring"


class WotoSyncJob(BaseModel):
    __tablename__ = "woto_sync_jobs"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    query: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[WotoSyncJobStatus] = mapped_column(
        Enum(WotoSyncJobStatus), default=WotoSyncJobStatus.queued, nullable=False, index=True
    )
    discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enrolled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_cny: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    actual_cost_cny: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    billable_search_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    billable_detail_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    billable_contact_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_messages: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WotoUsageRecord(BaseModel):
    __tablename__ = "woto_usage_records"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    sync_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("woto_sync_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    operation: Mapped[WotoBillingOperation] = mapped_column(
        Enum(WotoBillingOperation), nullable=False, index=True
    )
    platform: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    unit_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price_cny: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("1.00"), nullable=False)
    amount_cny: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    billable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
