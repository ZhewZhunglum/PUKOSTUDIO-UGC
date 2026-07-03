import uuid

from pydantic import BaseModel


class SOPModule(BaseModel):
    id: str
    title: str
    output: str
    system_area: str


class SOPPricingBenchmark(BaseModel):
    tier: str
    follower_range: str
    tiktok: str
    instagram_reels: str
    youtube: str
    collaboration_model: str


class SOPPlatformGuide(BaseModel):
    platform: str
    content_formats: str
    strength: str
    ideal_creators: str
    best_posting_window_utc: str
    amplification_note: str


class SOPRule(BaseModel):
    title: str
    description: str
    severity: str | None = None


class SOPPlaybookResponse(BaseModel):
    source_title: str
    source_updated_at: str
    operating_principle: str
    modules: list[SOPModule]
    pricing_benchmarks: list[SOPPricingBenchmark]
    platform_guides: list[SOPPlatformGuide]
    screening_rules: list[SOPRule]
    compliance_rules: list[SOPRule]
    negotiation_scripts: list[SOPRule]
    review_checklist: list[str]
    performance_metrics: list[SOPRule]


class SOPInfluencerScore(BaseModel):
    influencer_id: uuid.UUID | None = None
    tier: str
    tier_label: str
    readiness_score: int
    recommendation: str
    flags: list[str]
    strengths: list[str]
    next_steps: list[str]
