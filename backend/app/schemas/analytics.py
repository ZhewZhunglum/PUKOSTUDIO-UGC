from datetime import date

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_influencers: int
    active_campaigns: int
    emails_sent: int
    emails_delivered: int
    emails_opened: int
    emails_replied: int
    emails_bounced: int
    open_rate: float
    reply_rate: float
    bounce_rate: float


class CampaignStats(BaseModel):
    campaign_id: str
    campaign_name: str
    total_enrolled: int
    emails_sent: int
    emails_delivered: int
    emails_opened: int
    emails_replied: int
    emails_bounced: int
    open_rate: float
    reply_rate: float


class DailyStatsItem(BaseModel):
    date: date
    emails_sent: int
    emails_delivered: int
    emails_opened: int
    emails_replied: int
    emails_bounced: int


class DashboardResponse(BaseModel):
    stats: DashboardStats
    daily: list[DailyStatsItem]
