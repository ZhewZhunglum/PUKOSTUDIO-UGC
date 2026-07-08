import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EmailProviderType(str, enum.Enum):
    ses = "ses"
    sendgrid = "sendgrid"
    smtp = "smtp"


class EmailHealthStatus(str, enum.Enum):
    healthy = "healthy"
    degraded = "degraded"
    suspended = "suspended"


class SignatureMode(str, enum.Enum):
    structured = "structured"  # signature_content is plain text, server-composed into signature_html
    custom = "custom"  # signature_html is user-authored rich HTML (sanitized), stored as-is


class EmailAccount(BaseModel):
    __tablename__ = "email_accounts"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    email_address: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider_type: Mapped[EmailProviderType] = mapped_column(
        Enum(EmailProviderType), nullable=False
    )
    provider_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    daily_limit: Mapped[int] = mapped_column(Integer, default=50)
    sent_today: Mapped[int] = mapped_column(Integer, default=0)
    warmup_stage: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    health_status: Mapped[EmailHealthStatus] = mapped_column(
        Enum(EmailHealthStatus), default=EmailHealthStatus.healthy
    )

    # Branded signature (appended to outbound mail when enabled).
    # signature_content holds the user-authored text block (name/title/company/
    # tagline); signature_html is the server-rendered canonical block used at
    # send time (single source of truth), composed from content + logo + links.
    signature_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    signature_mode: Mapped[SignatureMode] = mapped_column(
        Enum(SignatureMode), default=SignatureMode.structured, nullable=False
    )
    signature_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_logo_attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_attachments.id", ondelete="SET NULL"),
        nullable=True,
    )
    brand_color: Mapped[str | None] = mapped_column(String(9), nullable=True)
    social_links: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
