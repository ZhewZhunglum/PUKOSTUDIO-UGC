import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ClientRelationshipType(str, enum.Enum):
    buyer = "buyer"  # wholesale/retail buyer we're pitching to stock the product
    agency_prospect = "agency_prospect"  # brand that might pay for our outreach service
    partner = "partner"  # co-marketing / sponsorship partnership target


class ClientStatus(str, enum.Enum):
    """Deliberately reuses InfluencerStatus's exact vocabulary (see
    app/models/influencer.py) so the deal pipeline reads consistently across
    the whole app: signed = deal closed, rejected = declined, blacklisted =
    do not contact again."""

    new = "new"
    contacted = "contacted"
    replied = "replied"
    negotiating = "negotiating"
    signed = "signed"
    rejected = "rejected"
    blacklisted = "blacklisted"


class Client(BaseModel):
    """A B2B contact: a wholesale/retail buyer, a prospective agency-service
    client, or a brand/sponsorship partnership target (see relationship_type).

    Deliberately separate from Influencer — no social platform/follower
    fields apply here, and keeping this a parallel entity (rather than a
    contact_type flag on Influencer) keeps the creator-focused
    influencer CRM's schema and UI free of unrelated business fields.
    """

    __tablename__ = "clients"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    relationship_type: Mapped[ClientRelationshipType] = mapped_column(
        Enum(ClientRelationshipType), nullable=False, index=True
    )
    status: Mapped[ClientStatus] = mapped_column(
        Enum(ClientStatus), default=ClientStatus.new, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "manual" | "csv_import" — no automated discovery source exists for B2B
    # contacts (Woto only covers individual creators).
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
