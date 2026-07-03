import uuid
from datetime import date, timedelta

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import (
    Campaign,
    CampaignStatus,
)
from app.models.email_message import EmailDirection, EmailMessage, EmailStatus
from app.models.influencer import Influencer


async def get_dashboard_stats(
    db: AsyncSession, team_id: uuid.UUID, start_date: date | None = None, end_date: date | None = None
) -> dict:
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Total influencers
    inf_count = await db.execute(
        select(func.count(Influencer.id)).where(Influencer.team_id == team_id)
    )
    total_influencers = inf_count.scalar() or 0

    # Active campaigns
    camp_count = await db.execute(
        select(func.count(Campaign.id)).where(
            Campaign.team_id == team_id, Campaign.status == CampaignStatus.active
        )
    )
    active_campaigns = camp_count.scalar() or 0

    # Email stats
    email_stats = await db.execute(
        select(
            func.count(EmailMessage.id).label("total"),
            func.count(case((and_(
                EmailMessage.direction == EmailDirection.outbound,
                EmailMessage.status.in_([
                    EmailStatus.sent, EmailStatus.delivered, EmailStatus.opened, EmailStatus.clicked
                ]),
            ), 1))).label("sent"),
            func.count(case((and_(
                EmailMessage.direction == EmailDirection.outbound,
                EmailMessage.status.in_([
                    EmailStatus.delivered, EmailStatus.opened, EmailStatus.clicked
                ]),
            ), 1))).label("delivered"),
            func.count(case((and_(
                EmailMessage.direction == EmailDirection.outbound,
                EmailMessage.status.in_([
                    EmailStatus.opened, EmailStatus.clicked
                ]),
            ), 1))).label("opened"),
            func.count(case((and_(
                EmailMessage.direction == EmailDirection.outbound,
                EmailMessage.status == EmailStatus.bounced,
            ), 1))).label("bounced"),
            func.count(case((EmailMessage.direction == EmailDirection.inbound, 1))).label("replied"),
        )
        .where(
            EmailMessage.team_id == team_id,
            func.date(EmailMessage.created_at) >= start_date,
            func.date(EmailMessage.created_at) <= end_date,
        )
    )
    stats = email_stats.one()

    sent = stats.sent or 0
    delivered = stats.delivered or 0
    opened = stats.opened or 0
    bounced = stats.bounced or 0
    emails_replied = stats.replied or 0

    return {
        "stats": {
            "total_influencers": total_influencers,
            "active_campaigns": active_campaigns,
            "emails_sent": sent,
            "emails_delivered": delivered,
            "emails_opened": opened,
            "emails_replied": emails_replied,
            "emails_bounced": bounced,
            "open_rate": round(opened / delivered * 100, 1) if delivered > 0 else 0,
            "reply_rate": round(emails_replied / sent * 100, 1) if sent > 0 else 0,
            "bounce_rate": round(bounced / sent * 100, 1) if sent > 0 else 0,
        }
    }


async def get_daily_stats(
    db: AsyncSession, team_id: uuid.UUID, start_date: date, end_date: date
) -> list[dict]:
    result = await db.execute(
        select(
            func.date(EmailMessage.created_at).label("day"),
            func.count(case((and_(
                EmailMessage.direction == EmailDirection.outbound,
                EmailMessage.status.in_([
                    EmailStatus.sent, EmailStatus.delivered, EmailStatus.opened, EmailStatus.clicked
                ]),
            ), 1))).label("sent"),
            func.count(case((and_(
                EmailMessage.direction == EmailDirection.outbound,
                EmailMessage.status.in_([
                    EmailStatus.delivered, EmailStatus.opened, EmailStatus.clicked
                ]),
            ), 1))).label("delivered"),
            func.count(case((and_(
                EmailMessage.direction == EmailDirection.outbound,
                EmailMessage.status.in_([
                    EmailStatus.opened, EmailStatus.clicked
                ]),
            ), 1))).label("opened"),
            func.count(case((and_(
                EmailMessage.direction == EmailDirection.outbound,
                EmailMessage.status == EmailStatus.bounced,
            ), 1))).label("bounced"),
            func.count(case((EmailMessage.direction == EmailDirection.inbound, 1))).label("replied"),
        )
        .where(
            EmailMessage.team_id == team_id,
            func.date(EmailMessage.created_at) >= start_date,
            func.date(EmailMessage.created_at) <= end_date,
        )
        .group_by(func.date(EmailMessage.created_at))
        .order_by(func.date(EmailMessage.created_at))
    )

    return [
        {
            "date": str(row.day),
            "emails_sent": row.sent or 0,
            "emails_delivered": row.delivered or 0,
            "emails_opened": row.opened or 0,
            "emails_replied": row.replied or 0,
            "emails_bounced": row.bounced or 0,
        }
        for row in result.all()
    ]
