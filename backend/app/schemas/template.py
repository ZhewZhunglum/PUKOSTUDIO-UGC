import uuid
from datetime import datetime

from pydantic import BaseModel


class TemplateCreate(BaseModel):
    name: str
    subject: str
    body_html: str
    body_text: str | None = None
    category: str = "initial_outreach"
    language: str = "en"
    is_library: bool = False
    variables: dict | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    category: str | None = None
    language: str | None = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    subject: str
    body_html: str
    body_text: str | None
    category: str
    language: str
    is_library: bool
    variables: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    items: list[TemplateResponse]
    total: int


class TemplatePreviewRequest(BaseModel):
    subject: str
    body_html: str
    variables: dict = {}


class TemplatePreviewResponse(BaseModel):
    subject: str
    body_html: str


class AIGenerateTemplateRequest(BaseModel):
    brief: str
    campaign_type: str
    tone: str = "professional"
    language: str = "en"
