import uuid
from datetime import datetime

from pydantic import BaseModel


class CampaignAIPlaybookBase(BaseModel):
    enabled: bool = False
    product_name: str | None = None
    product_description: str | None = None
    offer_summary: str | None = None
    deliverables: str | None = None
    sample_policy: str | None = None
    pricing_rules: str | None = None
    negotiation_limits: str | None = None
    prohibited_claims: str | None = None
    tone: str | None = None
    language: str | None = None
    signature: str | None = None
    reply_guidelines: str | None = None
    campaign_objectives: str | None = None
    target_audience: str | None = None
    key_messages: str | None = None
    content_dos: str | None = None
    content_donts: str | None = None
    required_hashtags: str | None = None
    disclosure_requirements: str | None = None
    payment_terms: str | None = None
    usage_rights: str | None = None
    approval_process: str | None = None
    contract_required: bool = False
    content_review_checklist: str | None = None
    posting_guidance: str | None = None
    performance_kpis: str | None = None
    competitor_notes: str | None = None


class CampaignAIPlaybookUpsert(CampaignAIPlaybookBase):
    pass


class CampaignAIPlaybookResponse(CampaignAIPlaybookBase):
    id: uuid.UUID | None = None
    campaign_id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AIMessageDraftCreate(BaseModel):
    guidelines: str = ""


class AIMessageDraftUpdate(BaseModel):
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None


class AIMessageDraftResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    conversation_id: uuid.UUID
    campaign_id: uuid.UUID | None
    influencer_id: uuid.UUID
    subject: str
    body_html: str
    body_text: str | None
    intent: str | None
    confidence: float | None
    risk_level: str
    status: str
    failure_reason: str | None
    rationale: str | None
    missing_context: str | None
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    sent_message_id: uuid.UUID | None
    metadata_: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AIActionLogResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    conversation_id: uuid.UUID | None
    campaign_id: uuid.UUID | None
    draft_id: uuid.UUID | None
    action_type: str
    actor_user_id: uuid.UUID | None
    detail: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
