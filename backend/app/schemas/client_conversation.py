import uuid
from datetime import datetime

from pydantic import BaseModel


class ClientConversationMessageResponse(BaseModel):
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


class ClientConversationListItemResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    client_company_name: str
    client_email: str | None
    last_message_at: datetime | None
    unread_count: int
    needs_review: bool
    assigned_to: uuid.UUID | None
    latest_subject: str | None
    last_message_preview: str | None


class ClientConversationDetailResponse(ClientConversationListItemResponse):
    messages: list[ClientConversationMessageResponse]


class ClientConversationUpdateRequest(BaseModel):
    needs_review: bool | None = None
    assigned_to: uuid.UUID | None = None


class SendClientReplyRequest(BaseModel):
    subject: str | None = None
    body_html: str
    body_text: str | None = None
    email_account_id: uuid.UUID | None = None
