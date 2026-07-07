import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SuppressionReason(str, enum.Enum):
    bounced = "bounced"
    complained = "complained"
    unsubscribed = "unsubscribed"
    manual = "manual"


class EmailSuppression(BaseModel):
    """A recipient address the team must not email again.

    Populated automatically on hard bounce / spam complaint / unsubscribe, and
    manually. Sends check this list first so we stop mailing bad or opted-out
    addresses — the single biggest protector of sender reputation.
    """

    __tablename__ = "email_suppressions"
    __table_args__ = (
        UniqueConstraint("team_id", "email", name="uq_email_suppressions_team_email"),
    )

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    reason: Mapped[SuppressionReason] = mapped_column(
        Enum(SuppressionReason), nullable=False
    )
