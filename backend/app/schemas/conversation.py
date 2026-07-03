import uuid
from datetime import datetime

from pydantic import BaseModel


class ConversationMessageResponse(BaseModel):
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
    created_at: datetime


class ConversationListItemResponse(BaseModel):
    id: uuid.UUID
    influencer_id: uuid.UUID
    influencer_name: str
    influencer_email: str | None
    last_message_at: datetime | None
    unread_count: int
    ai_intent: str | None
    ai_confidence: float | None
    needs_review: bool
    assigned_to: uuid.UUID | None
    latest_subject: str | None
    last_message_preview: str | None
    latest_draft_id: uuid.UUID | None = None
    latest_draft_status: str | None = None
    risk_level: str | None = None
    automation_status: str | None = None


class ConversationDetailResponse(ConversationListItemResponse):
    messages: list[ConversationMessageResponse]


class ConversationUpdateRequest(BaseModel):
    ai_intent: str | None = None
    needs_review: bool | None = None
    assigned_to: uuid.UUID | None = None


class ReplyDraftRequest(BaseModel):
    guidelines: str = ""


class ReplyDraftResponse(BaseModel):
    subject: str
    body_html: str
    body_text: str
    provider_available: bool
    fallback_reason: str | None = None


class SendReplyRequest(BaseModel):
    subject: str | None = None
    body_html: str
    body_text: str | None = None
    email_account_id: uuid.UUID | None = None
    attachment_ids: list[uuid.UUID] = []
