import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr


class PlatformCreate(BaseModel):
    platform: str  # tiktok, instagram, youtube
    username: str
    profile_url: str | None = None
    data_provider: str | None = None
    external_id: str | None = None
    followers: int | None = None
    engagement_rate: float | None = None
    avg_views: int | None = None


class PlatformResponse(BaseModel):
    id: uuid.UUID
    platform: str
    username: str
    profile_url: str | None
    data_provider: str | None
    external_id: str | None
    followers: int | None
    engagement_rate: float | None
    avg_views: int | None
    raw_data: dict | None = None
    last_synced_at: datetime | None

    model_config = {"from_attributes": True}


class TagCreate(BaseModel):
    name: str
    color: str | None = None


class TagResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None

    model_config = {"from_attributes": True}


class InfluencerCreate(BaseModel):
    name: str
    email: EmailStr | None = None
    niche: str | None = None
    country: str | None = "US"
    notes: str | None = None
    source: str | None = "manual"
    platforms: list[PlatformCreate] = []
    tag_ids: list[uuid.UUID] = []


class InfluencerUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    niche: str | None = None
    country: str | None = None
    status: str | None = None
    notes: str | None = None
    platforms: list[PlatformCreate] | None = None
    tag_ids: list[uuid.UUID] | None = None


class InfluencerResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str | None
    email_verified: bool
    avatar_url: str | None
    niche: str | None
    country: str | None
    status: str
    notes: str | None
    source: str | None
    platforms: list[PlatformResponse] = []
    tags: list[TagResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InfluencerListResponse(BaseModel):
    items: list[InfluencerResponse]
    total: int
    page: int
    per_page: int
    pages: int


class InfluencerImportResponse(BaseModel):
    total_rows: int
    imported: int
    skipped: int
    errors: list[str]


class BulkTagRequest(BaseModel):
    influencer_ids: list[uuid.UUID]
    tag_ids: list[uuid.UUID]


class InfluencerCRMActionRequest(BaseModel):
    action: Literal[
        "mark_contacted",
        "mark_replied",
        "mark_negotiating",
        "mark_signed",
        "mark_rejected",
        "special_attention",
        "favorite",
        "recommend",
        "blacklist",
        "restore",
        "append_note",
    ]
    note: str | None = None
