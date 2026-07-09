import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class ClientCreate(BaseModel):
    company_name: str
    contact_name: str | None = None
    title: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    industry: str | None = None
    website: str | None = None
    relationship_type: str  # buyer | agency_prospect | partner
    notes: str | None = None
    source: str | None = "manual"


class ClientUpdate(BaseModel):
    company_name: str | None = None
    contact_name: str | None = None
    title: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    industry: str | None = None
    website: str | None = None
    relationship_type: str | None = None
    status: str | None = None
    notes: str | None = None


class ClientResponse(BaseModel):
    id: uuid.UUID
    company_name: str
    contact_name: str | None
    title: str | None
    email: str | None
    phone: str | None
    industry: str | None
    website: str | None
    relationship_type: str
    status: str
    notes: str | None
    source: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClientListResponse(BaseModel):
    items: list[ClientResponse]
    total: int
    page: int
    per_page: int
    pages: int


class ClientImportResponse(BaseModel):
    total_rows: int
    imported: int
    skipped: int
    errors: list[str]
