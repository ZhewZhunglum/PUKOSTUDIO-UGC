import uuid
from datetime import datetime

from pydantic import BaseModel


class ClientCampaignStepCreate(BaseModel):
    step_order: int
    step_type: str = "initial"
    template_id: uuid.UUID
    delay_days: int = 0
    condition: dict | None = None


class ClientCampaignStepResponse(BaseModel):
    id: uuid.UUID
    step_order: int
    step_type: str
    template_id: uuid.UUID
    delay_days: int
    condition: dict | None

    model_config = {"from_attributes": True}


class ClientCampaignCreate(BaseModel):
    name: str
    description: str | None = None
    target_criteria: dict | None = None
    schedule_config: dict | None = None
    steps: list[ClientCampaignStepCreate] = []


class ClientCampaignUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    target_criteria: dict | None = None
    schedule_config: dict | None = None


class ClientCampaignResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    status: str
    target_criteria: dict | None
    schedule_config: dict | None
    steps: list[ClientCampaignStepResponse] = []
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class EnrollClientsRequest(BaseModel):
    client_ids: list[uuid.UUID]


class ClientCampaignEnrollmentResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    client_company_name: str
    client_email: str | None
    current_step: int
    status: str
    enrolled_at: datetime | None
    last_sent_at: datetime | None
    last_email_status: str | None = None
    failure_reason: str | None = None
