import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class ClientCampaignStepCreate(BaseModel):
    step_order: int
    step_type: str = "initial"
    template_id: uuid.UUID
    delay_days: int = 0
    condition: dict | None = None
    attachment_ids: list[uuid.UUID] = []


class ClientCampaignStepResponse(BaseModel):
    id: uuid.UUID
    step_order: int
    step_type: str
    template_id: uuid.UUID
    delay_days: int
    condition: dict | None
    attachment_ids: list[uuid.UUID] = []

    model_config = {"from_attributes": True}

    @field_validator("attachment_ids", mode="before")
    @classmethod
    def _default_attachment_ids(cls, v):
        # Steps created before the attachment_ids column existed have NULL
        # in the DB rather than an empty JSONB array.
        return v or []


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
