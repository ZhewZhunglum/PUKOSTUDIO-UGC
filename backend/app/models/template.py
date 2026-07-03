import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class TemplateCategory(str, enum.Enum):
    initial_outreach = "initial_outreach"
    followup_1 = "followup_1"
    followup_2 = "followup_2"
    reply = "reply"
    custom = "custom"


class EmailTemplate(BaseModel):
    __tablename__ = "email_templates"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[TemplateCategory] = mapped_column(
        Enum(TemplateCategory), default=TemplateCategory.initial_outreach
    )
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False, index=True)
    is_library: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    variables: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
