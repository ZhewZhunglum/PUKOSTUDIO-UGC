import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AttachmentPurpose(str, enum.Enum):
    email = "email"
    signature_logo = "signature_logo"
    snippet_asset = "snippet_asset"


class EmailAttachment(BaseModel):
    __tablename__ = "email_attachments"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    # Sanitized original filename — display + Content-Disposition only, never used as a path.
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # On-disk name: uuid + whitelisted extension. Never client-controlled.
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[AttachmentPurpose] = mapped_column(
        Enum(AttachmentPurpose), default=AttachmentPurpose.email, nullable=False, index=True
    )
    email_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
