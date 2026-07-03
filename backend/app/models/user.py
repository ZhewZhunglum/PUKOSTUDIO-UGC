import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    admin = "admin"
    member = "member"


class Team(BaseModel):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    woto_settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    members: Mapped[list["User"]] = relationship("User", back_populates="team")


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.admin)
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False
    )

    team: Mapped[Team] = relationship("Team", back_populates="members")
