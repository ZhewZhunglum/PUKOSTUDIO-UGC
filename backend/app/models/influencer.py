import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import BaseModel

influencer_tags = Table(
    "influencer_tags",
    Base.metadata,
    Column("influencer_id", UUID(as_uuid=True), ForeignKey("influencers.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class InfluencerStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    replied = "replied"
    negotiating = "negotiating"
    signed = "signed"
    rejected = "rejected"
    blacklisted = "blacklisted"


class Platform(str, enum.Enum):
    tiktok = "tiktok"
    instagram = "instagram"
    youtube = "youtube"


class Influencer(BaseModel):
    __tablename__ = "influencers"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Where a batch job sourced the contact from: "dig" (free public-profile
    # crawl) or "woto" (paid backfill). Null = imported/manual.
    email_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Outcome of the last batch email/phone dig ("found" | "no-email" |
    # "unreachable") — lets the UI mark creators already dug so nobody wastes
    # time re-digging them.
    email_dig_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email_dig_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    niche: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    status: Mapped[InfluencerStatus] = mapped_column(
        Enum(InfluencerStatus), default=InfluencerStatus.new, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)

    platforms: Mapped[list["InfluencerPlatform"]] = relationship(
        "InfluencerPlatform", back_populates="influencer", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", secondary=influencer_tags, back_populates="influencers"
    )


class InfluencerPlatform(BaseModel):
    __tablename__ = "influencer_platforms"
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "data_provider",
            "platform",
            "external_id",
            name="uq_influencer_platforms_team_provider_platform_external",
        ),
        Index(
            "ix_influencer_platforms_provider_external",
            "data_provider",
            "platform",
            "external_id",
        ),
    )

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )

    influencer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("influencers.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    data_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str] = mapped_column(String(200), nullable=False)
    profile_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    followers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engagement_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_topics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    influencer: Mapped[Influencer] = relationship("Influencer", back_populates="platforms")


class Tag(BaseModel):
    __tablename__ = "tags"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)

    influencers: Mapped[list[Influencer]] = relationship(
        "Influencer", secondary=influencer_tags, back_populates="tags"
    )
