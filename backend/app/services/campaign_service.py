import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.campaign import (
    Campaign,
    CampaignInfluencer,
    CampaignInfluencerStatus,
    CampaignStatus,
    CampaignStep,
    CampaignType,
)
from app.models.email_attachment import EmailAttachment
from app.models.email_message import EmailDirection, EmailMessage, EmailStatus
from app.models.influencer import Influencer
from app.schemas.campaign import CampaignCreate, CampaignUpdate

ALLOWED_UPDATE_FIELDS = {"name", "description", "target_criteria", "schedule_config"}


async def list_campaigns(db: AsyncSession, team_id: uuid.UUID) -> list[Campaign]:
    result = await db.execute(
        select(Campaign)
        .where(Campaign.team_id == team_id)
        .options(selectinload(Campaign.steps))
        .order_by(Campaign.created_at.desc())
    )
    return list(result.scalars().all())


async def get_campaign(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID
) -> Campaign:
    result = await db.execute(
        select(Campaign)
        .where(Campaign.id == campaign_id, Campaign.team_id == team_id)
        .options(selectinload(Campaign.steps), selectinload(Campaign.influencers))
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise NotFoundException("Campaign not found")
    return campaign


MAX_CAMPAIGN_STEPS = 5
# ESPs commonly reject (or silently drop) mail well before 25MB; keep enough
# headroom under that for the base64-inflated MIME size of the attachments
# themselves plus the HTML body.
MAX_STEP_ATTACHMENT_BYTES = 15 * 1024 * 1024


def _validate_steps(steps: list) -> None:
    """Multi-step sequence rules: 1..MAX steps, consecutive orders starting at
    1, the initial step sends immediately, follow-ups need a positive delay."""
    if not steps:
        raise BadRequestException("Campaign must have at least one step")
    if len(steps) > MAX_CAMPAIGN_STEPS:
        raise BadRequestException(f"最多支持 {MAX_CAMPAIGN_STEPS} 个步骤")
    orders = sorted(s.step_order for s in steps)
    if orders != list(range(1, len(steps) + 1)):
        raise BadRequestException("步骤顺序必须从 1 开始连续递增")
    by_order = {s.step_order: s for s in steps}
    if (by_order[1].delay_days or 0) != 0:
        raise BadRequestException("首发步骤的延迟必须为 0 天")
    for order in orders[1:]:
        if (by_order[order].delay_days or 0) < 1:
            raise BadRequestException("跟进步骤的延迟至少为 1 天")


async def _validate_step_attachments(
    db: AsyncSession, team_id: uuid.UUID, steps: list
) -> None:
    """Reject a step whose combined attachment size risks provider rejection.

    One query covers every attachment referenced across all steps instead of
    one query per step.
    """
    all_ids = {aid for step in steps for aid in (step.attachment_ids or [])}
    if not all_ids:
        return
    result = await db.execute(
        select(EmailAttachment.id, EmailAttachment.size_bytes).where(
            EmailAttachment.id.in_(all_ids), EmailAttachment.team_id == team_id
        )
    )
    size_by_id = dict(result.all())
    overflowing = _overflowing_step_orders(steps, size_by_id)
    if overflowing:
        raise BadRequestException(
            f"步骤 {overflowing[0]} 的附件总大小超过 "
            f"{MAX_STEP_ATTACHMENT_BYTES // (1024 * 1024)}MB 限制"
        )


def _overflowing_step_orders(steps: list, size_by_id: dict) -> list[int]:
    """Pure sizing check (no I/O) — step_orders whose combined attachments
    exceed the per-step cap, given a precomputed id->size_bytes map."""
    overflowing = []
    for step in steps:
        total = sum(size_by_id.get(aid, 0) for aid in (step.attachment_ids or []))
        if total > MAX_STEP_ATTACHMENT_BYTES:
            overflowing.append(step.step_order)
    return overflowing


async def create_campaign(
    db: AsyncSession, team_id: uuid.UUID, data: CampaignCreate
) -> Campaign:
    _validate_steps(data.steps)
    await _validate_step_attachments(db, team_id, data.steps)

    campaign = Campaign(
        team_id=team_id,
        name=data.name,
        description=data.description,
        campaign_type=CampaignType(data.campaign_type),
        target_criteria=data.target_criteria,
        schedule_config=data.schedule_config,
    )
    db.add(campaign)
    await db.flush()

    # Create steps
    for step_data in data.steps:
        step = CampaignStep(
            campaign_id=campaign.id,
            step_order=step_data.step_order,
            step_type=step_data.step_type,
            template_id=step_data.template_id,
            delay_days=step_data.delay_days,
            condition=step_data.condition,
            attachment_ids=[str(a) for a in step_data.attachment_ids] or None,
        )
        db.add(step)

    await db.flush()
    return await get_campaign(db, campaign.id, team_id)


async def update_campaign(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID, data: CampaignUpdate
) -> Campaign:
    campaign = await get_campaign(db, campaign_id, team_id)

    if campaign.status not in (CampaignStatus.draft, CampaignStatus.paused):
        raise BadRequestException("Can only edit draft or paused campaigns")

    for field, value in data.model_dump(exclude_unset=True).items():
        if field not in ALLOWED_UPDATE_FIELDS:
            raise BadRequestException(f"Field '{field}' cannot be updated")
        setattr(campaign, field, value)

    await db.flush()
    return await get_campaign(db, campaign_id, team_id)


async def start_campaign(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID
) -> Campaign:
    campaign = await get_campaign(db, campaign_id, team_id)

    if campaign.status not in (CampaignStatus.draft, CampaignStatus.paused):
        raise BadRequestException("Campaign cannot be started from current status")

    if not campaign.steps:
        raise BadRequestException("Campaign must have at least one step")

    # Count enrolled influencers
    count = await db.execute(
        select(func.count(CampaignInfluencer.id)).where(
            CampaignInfluencer.campaign_id == campaign_id
        )
    )
    if (count.scalar() or 0) == 0:
        raise BadRequestException("No influencers enrolled in this campaign")

    campaign.status = CampaignStatus.active
    campaign.started_at = datetime.now(timezone.utc)

    # Commit BEFORE dispatching the Celery task so the worker always sees
    # status=active when it queries the DB.  Without this explicit commit the
    # task can race the route-level commit in get_db() and exit early with
    # "Campaign is not active, skipping batch".
    await db.commit()

    # Dispatch Celery task (imported here to avoid circular imports)
    from app.workers.email_tasks import send_campaign_batch

    send_campaign_batch.delay(str(campaign_id), str(team_id))

    return await get_campaign(db, campaign_id, team_id)


async def pause_campaign(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID
) -> Campaign:
    campaign = await get_campaign(db, campaign_id, team_id)
    if campaign.status != CampaignStatus.active:
        raise BadRequestException("Only active campaigns can be paused")

    campaign.status = CampaignStatus.paused
    await db.flush()
    return await get_campaign(db, campaign_id, team_id)


async def stop_campaign(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID
) -> Campaign:
    campaign = await get_campaign(db, campaign_id, team_id)
    if campaign.status not in (CampaignStatus.active, CampaignStatus.paused):
        raise BadRequestException("Campaign is not active or paused")

    campaign.status = CampaignStatus.completed
    campaign.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_campaign(db, campaign_id, team_id)


async def enroll_influencers(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID, influencer_ids: list[uuid.UUID]
) -> int:
    campaign = await get_campaign(db, campaign_id, team_id)
    if campaign.status not in (CampaignStatus.draft, CampaignStatus.paused):
        raise BadRequestException("Can only enroll to draft or paused campaigns")

    # Get existing enrollments
    existing = await db.execute(
        select(CampaignInfluencer.influencer_id).where(
            CampaignInfluencer.campaign_id == campaign_id
        )
    )
    existing_ids = {row[0] for row in existing}

    valid_influencers = await db.execute(
        select(Influencer.id).where(
            Influencer.team_id == team_id,
            Influencer.id.in_(influencer_ids),
        )
    )
    valid_ids = {row[0] for row in valid_influencers}

    count = 0
    now = datetime.now(timezone.utc)
    for inf_id in influencer_ids:
        if inf_id in valid_ids and inf_id not in existing_ids:
            ci = CampaignInfluencer(
                campaign_id=campaign_id,
                influencer_id=inf_id,
                enrolled_at=now,
            )
            db.add(ci)
            count += 1

    await db.flush()
    return count


async def list_campaign_enrollments(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID
) -> list[dict]:
    await get_campaign(db, campaign_id, team_id)

    result = await db.execute(
        select(CampaignInfluencer, Influencer)
        .join(Influencer, Influencer.id == CampaignInfluencer.influencer_id)
        .where(CampaignInfluencer.campaign_id == campaign_id)
        .order_by(CampaignInfluencer.created_at.desc())
    )

    rows = result.all()

    # Fetch latest message per influencer in a single query (avoid N+1)
    influencer_ids = [influencer.id for _, influencer in rows]
    latest_msgs: dict[uuid.UUID, EmailMessage] = {}
    if influencer_ids:
        latest_msgs_result = await db.execute(
            select(EmailMessage)
            .where(
                EmailMessage.campaign_id == campaign_id,
                EmailMessage.influencer_id.in_(influencer_ids),
            )
            .distinct(EmailMessage.influencer_id)
            .order_by(EmailMessage.influencer_id, EmailMessage.created_at.desc())
        )
        latest_msgs = {msg.influencer_id: msg for msg in latest_msgs_result.scalars().all()}

    items: list[dict] = []
    for enrollment, influencer in rows:
        latest_message = latest_msgs.get(influencer.id)

        failure_reason = None
        if enrollment.status == CampaignInfluencerStatus.bounced:
            if not influencer.email:
                failure_reason = "Influencer is missing an email address"
            elif latest_message and latest_message.metadata_:
                failure_reason = latest_message.metadata_.get("failure_reason")
            else:
                failure_reason = "Email delivery failed"

        items.append(
            {
                "id": enrollment.id,
                "influencer_id": influencer.id,
                "influencer_name": influencer.name,
                "influencer_email": influencer.email,
                "current_step": enrollment.current_step,
                "status": enrollment.status.value,
                "enrolled_at": enrollment.enrolled_at,
                "last_sent_at": enrollment.last_sent_at,
                "last_email_status": latest_message.status.value if latest_message else None,
                "failure_reason": failure_reason,
            }
        )

    return items


async def remove_enrollment(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    team_id: uuid.UUID,
    enrollment_id: uuid.UUID,
) -> None:
    await get_campaign(db, campaign_id, team_id)
    result = await db.execute(
        select(CampaignInfluencer).where(
            CampaignInfluencer.id == enrollment_id,
            CampaignInfluencer.campaign_id == campaign_id,
        )
    )
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise NotFoundException("Campaign enrollment not found")
    await db.delete(enrollment)


async def get_send_progress(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID
) -> dict:
    """Live send progress for a campaign, derived from enrollment statuses.

    `pending` = still queued, `failed` = bounced, `sent` = everything that got
    past the sending stage (in_progress/replied/completed/unsubscribed).
    """
    campaign = await get_campaign(db, campaign_id, team_id)  # team-scoped existence check

    result = await db.execute(
        select(CampaignInfluencer.status, func.count(CampaignInfluencer.id))
        .where(CampaignInfluencer.campaign_id == campaign_id)
        .group_by(CampaignInfluencer.status)
    )
    by_status = {status.value: count for status, count in result.all()}
    total = sum(by_status.values())
    pending = by_status.get(CampaignInfluencerStatus.queued.value, 0)
    failed = by_status.get(CampaignInfluencerStatus.bounced.value, 0)
    sent = total - pending - failed
    processed = total - pending

    return {
        "campaign_status": campaign.status.value,
        "is_active": campaign.status == CampaignStatus.active,
        "total": total,
        "pending": pending,
        "sent": sent,
        "failed": failed,
        "by_status": by_status,
        "progress_pct": round(processed / total * 100, 1) if total else 0.0,
    }


async def get_campaign_stats(db: AsyncSession, campaign_id: uuid.UUID) -> dict:
    # Count messages by status
    result = await db.execute(
        select(EmailMessage.status, func.count(EmailMessage.id))
        .where(
            EmailMessage.campaign_id == campaign_id,
            EmailMessage.direction == EmailDirection.outbound,
        )
        .group_by(EmailMessage.status)
    )
    status_counts = dict(result.all())

    sent = sum(
        status_counts.get(s, 0)
        for s in [EmailStatus.sent, EmailStatus.delivered, EmailStatus.opened, EmailStatus.clicked]
    )
    delivered = status_counts.get(EmailStatus.delivered, 0) + status_counts.get(
        EmailStatus.opened, 0
    ) + status_counts.get(EmailStatus.clicked, 0)
    opened = status_counts.get(EmailStatus.opened, 0) + status_counts.get(EmailStatus.clicked, 0)
    bounced = status_counts.get(EmailStatus.bounced, 0)

    # Count enrollees and replies in a single query
    ci_result = await db.execute(
        select(
            func.count(CampaignInfluencer.id).label("total_enrolled"),
            func.count(CampaignInfluencer.id)
            .filter(CampaignInfluencer.status == CampaignInfluencerStatus.replied)
            .label("total_replied"),
        ).where(CampaignInfluencer.campaign_id == campaign_id)
    )
    ci_row = ci_result.one()
    total_enrolled = ci_row.total_enrolled or 0
    total_replied = ci_row.total_replied or 0

    # A/B subject breakdown (present only when messages carry an ab_variant).
    _SENT_STATUSES = [
        EmailStatus.sent, EmailStatus.delivered, EmailStatus.opened, EmailStatus.clicked,
    ]
    _OPENED_STATUSES = [EmailStatus.opened, EmailStatus.clicked]
    variant_col = EmailMessage.metadata_["ab_variant"].astext
    variant_rows = await db.execute(
        select(
            variant_col.label("variant"),
            func.count(EmailMessage.id)
            .filter(EmailMessage.status.in_(_SENT_STATUSES))
            .label("sent"),
            func.count(EmailMessage.id)
            .filter(EmailMessage.status.in_(_OPENED_STATUSES))
            .label("opened"),
        )
        .where(
            EmailMessage.campaign_id == campaign_id,
            EmailMessage.direction == EmailDirection.outbound,
            variant_col.is_not(None),
        )
        .group_by(variant_col)
    )
    ab_test = {
        row.variant: {
            "sent": row.sent or 0,
            "opened": row.opened or 0,
            "open_rate": round(row.opened / row.sent * 100, 1) if row.sent else 0,
        }
        for row in variant_rows.all()
    }
    # Only surface the block when a real experiment ran (both variants present).
    if set(ab_test.keys()) != {"A", "B"}:
        ab_test = None

    return {
        "ab_test": ab_test,
        "total_enrolled": total_enrolled,
        "emails_sent": sent,
        "emails_delivered": delivered,
        "emails_opened": opened,
        "emails_replied": total_replied,
        "emails_bounced": bounced,
        "open_rate": (opened / delivered * 100) if delivered > 0 else 0,
        "reply_rate": (total_replied / sent * 100) if sent > 0 else 0,
    }
