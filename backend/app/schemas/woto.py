import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

WotoPlatform = Literal["tiktok", "instagram", "youtube"]
WotoSearchType = Literal["KEYWORD", "NAME"]


class WotoSyncJobCreate(BaseModel):
    platform: WotoPlatform
    search_type: WotoSearchType = "KEYWORD"
    keyword: str | None = Field(default=None, max_length=200)
    blogger_name: str | None = Field(default=None, max_length=200)
    exclude_keywords: list[str] = []
    region_ids: list[str] = []
    category_ids: list[str] = []
    min_followers: int | None = Field(default=None, ge=0)
    max_followers: int | None = Field(default=None, ge=0)
    min_engagement_rate: float | None = Field(default=None, ge=0, le=100)
    max_engagement_rate: float | None = Field(default=None, ge=0, le=100)
    has_email: bool | None = None
    min_avg_views: int | None = Field(default=None, ge=0)
    max_avg_views: int | None = Field(default=None, ge=0)
    sort: Literal["FANS_NUM", "VIEW_AVG", "INTERACTIVE_RATE", "TOTAL_STAR"] = "FANS_NUM"
    sort_order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=50, ge=1, le=500)
    fetch_detail: bool = True
    enrich_contacts: bool = True
    campaign_id: uuid.UUID | None = None


class WotoSyncJobResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    campaign_id: uuid.UUID | None
    platform: str
    query: dict | None
    status: str
    discovered: int
    created_count: int
    updated_count: int
    enrolled_count: int
    skipped_count: int
    estimated_cost_cny: Decimal
    actual_cost_cny: Decimal
    billable_search_calls: int
    billable_detail_calls: int
    billable_contact_calls: int
    warning_messages: list[str] | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WotoQuotaResponse(BaseModel):
    remain_quota: int | None
    raw: dict


class WotoDictionaryItem(BaseModel):
    id: str | int | None = None
    dict_code: str | None = None
    dict_value: str | None = None
    dict_type_code: str | None = None
    raw: dict


class WotoPricingItem(BaseModel):
    operation: str
    label: str
    platform: str
    unit_price_cny: Decimal
    unit: str
    return_count: str | None = None
    description: str


class WotoDiscountTier(BaseModel):
    min_calls: int
    max_calls: int | None
    discount_rate: Decimal
    label: str


class WotoPricingTableResponse(BaseModel):
    currency: str = "CNY"
    valid_from: str
    valid_to: str
    rate_limit_per_minute: int
    duplicate_policy: str
    items: list[WotoPricingItem]
    discount_tiers: list[WotoDiscountTier]
    current_month_billable_calls: int
    current_discount_rate: Decimal
    current_month_spend_cny: Decimal


class WotoCostEstimateLine(BaseModel):
    operation: str
    label: str
    platform: str
    unit_price_cny: Decimal
    units: int
    subtotal_cny: Decimal
    discounted_subtotal_cny: Decimal
    note: str | None = None


class WotoCostEstimateResponse(BaseModel):
    currency: str = "CNY"
    discount_rate: Decimal
    monthly_billable_calls_before: int
    estimated_billable_calls: int
    estimated_subtotal_cny: Decimal
    estimated_total_cny: Decimal
    lines: list[WotoCostEstimateLine]
    notes: list[str]
