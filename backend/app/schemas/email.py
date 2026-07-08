import uuid
from datetime import datetime

from pydantic import BaseModel


class EmailAccountCreate(BaseModel):
    email_address: str
    display_name: str | None = None
    provider_type: str  # ses, sendgrid, smtp
    provider_config: dict | None = None
    daily_limit: int = 50


class EmailAccountUpdate(BaseModel):
    display_name: str | None = None
    provider_config: dict | None = None
    daily_limit: int | None = None
    is_active: bool | None = None
    # Branded signature inputs.
    # signature_mode="structured" (default): signature_html is rendered
    # server-side from signature_content/logo/brand_color/social_links (as
    # today, unchanged). signature_mode="custom": the caller writes
    # signature_html directly (user-authored via the rich-text editor); it is
    # sanitized and stored as-is, bypassing server rendering.
    signature_mode: str | None = None
    signature_enabled: bool | None = None
    signature_content: str | None = None
    signature_html: str | None = None
    signature_logo_attachment_id: uuid.UUID | None = None
    brand_color: str | None = None
    social_links: dict | None = None


class EmailAccountResponse(BaseModel):
    id: uuid.UUID
    email_address: str
    display_name: str | None
    provider_type: str
    daily_limit: int
    sent_today: int
    warmup_stage: int
    is_active: bool
    health_status: str
    signature_enabled: bool
    signature_mode: str
    signature_content: str | None
    signature_html: str | None
    signature_logo_attachment_id: uuid.UUID | None
    brand_color: str | None
    social_links: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SignaturePreviewRequest(BaseModel):
    signature_content: str | None = None
    signature_logo_attachment_id: uuid.UUID | None = None
    brand_color: str | None = None
    social_links: dict | None = None


class SignaturePreviewResponse(BaseModel):
    signature_html: str


class EmailAccountVerifyResponse(BaseModel):
    success: bool
    health_status: str
    error: str | None = None


class EmailAccountListResponse(BaseModel):
    items: list[EmailAccountResponse]
    total: int


class EmailMessageResponse(BaseModel):
    id: uuid.UUID
    direction: str
    from_address: str
    to_address: str
    subject: str
    body_html: str | None
    body_text: str | None
    status: str
    message_id: str | None
    in_reply_to: str | None
    references: str | None
    sent_at: datetime | None
    opened_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SendTestEmailRequest(BaseModel):
    to_address: str
    subject: str = "Test Email from UGC Outreach"
    body: str = "This is a test email to verify your email account configuration."
