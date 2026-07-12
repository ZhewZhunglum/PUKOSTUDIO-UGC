import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EmailDigPlatform = Literal["tiktok", "instagram", "youtube"]


class EmailDigJobCreate(BaseModel):
    # Free-form entries: @usernames, bare usernames, profile URLs, UC... channel ids.
    entries: list[str] = Field(default=[], max_length=1000)
    # Bare usernames are assumed to live on this platform.
    default_platform: EmailDigPlatform = "tiktok"
    # Existing influencers to backfill emails for (their platform accounts are dug).
    influencer_ids: list[uuid.UUID] = Field(default=[], max_length=1000)


class EmailDigJobResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    status: str
    mode: str = "dig"
    default_platform: str
    input_count: int
    processed_count: int
    resolved_count: int
    found_count: int
    phone_found_count: int
    updated_count: int
    created_count: int
    results: list[dict] | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
