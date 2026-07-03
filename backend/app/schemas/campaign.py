import uuid
from datetime import datetime

from pydantic import BaseModel


class CampaignStepCreate(BaseModel):
    step_order: int
    step_type: str = "initial"
    template_id: uuid.UUID
    delay_days: int = 0
    condition: dict | None = None


class CampaignStepResponse(BaseModel):
    id: uuid.UUID
    step_order: int
    step_type: str
    template_id: uuid.UUID
    delay_days: int
    condition: dict | None

    model_config = {"from_attributes": True}


class CampaignCreate(BaseModel):
    name: str
    description: str | None = None
    campaign_type: str  # ugc, brand_promo, tiktok_shop
    target_criteria: dict | None = None
    schedule_config: dict | None = None
    steps: list[CampaignStepCreate] = []


class CampaignUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    target_criteria: dict | None = None
    schedule_config: dict | None = None


class CampaignResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    status: str
    campaign_type: str
    target_criteria: dict | None
    schedule_config: dict | None
    steps: list[CampaignStepResponse] = []
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class CampaignListResponse(BaseModel):
    items: list[CampaignResponse]
    total: int
    page: int
    per_page: int
    pages: int


class EnrollInfluencersRequest(BaseModel):
    influencer_ids: list[uuid.UUID]


class CampaignInfluencerResponse(BaseModel):
    id: uuid.UUID
    influencer_id: uuid.UUID
    current_step: int
    status: str
    enrolled_at: datetime | None
    last_sent_at: datetime | None

    model_config = {"from_attributes": True}


class CampaignEnrollmentResponse(BaseModel):
    id: uuid.UUID
    influencer_id: uuid.UUID
    influencer_name: str
    influencer_email: str | None
    current_step: int
    status: str
    enrolled_at: datetime | None
    last_sent_at: datetime | None
    last_email_status: str | None = None
    failure_reason: str | None = None
