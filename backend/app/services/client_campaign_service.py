import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.client import Client
from app.models.client_campaign import (
    ClientCampaign,
    ClientCampaignEnrollment,
    ClientCampaignInfluencerStatus,
    ClientCampaignStatus,
    ClientCampaignStep,
)
from app.models.client_email_message import (
    ClientEmailDirection,
    ClientEmailMessage,
    ClientEmailStatus,
)
from app.schemas.client_campaign import ClientCampaignCreate, ClientCampaignUpdate
from app.services.campaign_service import _validate_step_attachments, _validate_steps

ALLOWED_UPDATE_FIELDS = {"name", "description", "target_criteria", "schedule_config"}


async def list_campaigns(db: AsyncSession, team_id: uuid.UUID) -> list[ClientCampaign]:
    result = await db.execute(
        select(ClientCampaign)
        .where(ClientCampaign.team_id == team_id)
        .options(selectinload(ClientCampaign.steps))
        .order_by(ClientCampaign.created_at.desc())
    )
    return list(result.scalars().all())


async def get_campaign(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID
) -> ClientCampaign:
    result = await db.execute(
        select(ClientCampaign)
        .where(ClientCampaign.id == campaign_id, ClientCampaign.team_id == team_id)
        .options(selectinload(ClientCampaign.steps), selectinload(ClientCampaign.clients))
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise NotFoundException("Campaign not found")
    return campaign


async def create_campaign(
    db: AsyncSession, team_id: uuid.UUID, data: ClientCampaignCreate
) -> ClientCampaign:
    _validate_steps(data.steps)
    await _validate_step_attachments(db, team_id, data.steps)

    campaign = ClientCampaign(
        team_id=team_id,
        name=data.name,
        description=data.description,
        target_criteria=data.target_criteria,
        schedule_config=data.schedule_config,
    )
    db.add(campaign)
    await db.flush()

    for step_data in data.steps:
        step = ClientCampaignStep(
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
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID, data: ClientCampaignUpdate
) -> ClientCampaign:
    campaign = await get_campaign(db, campaign_id, team_id)

    if campaign.status not in (ClientCampaignStatus.draft, ClientCampaignStatus.paused):
        raise BadRequestException("Can only edit draft or paused campaigns")

    for field, value in data.model_dump(exclude_unset=True).items():
        if field not in ALLOWED_UPDATE_FIELDS:
            raise BadRequestException(f"Field '{field}' cannot be updated")
        setattr(campaign, field, value)

    await db.flush()
    return await get_campaign(db, campaign_id, team_id)


async def start_campaign(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID
) -> ClientCampaign:
    campaign = await get_campaign(db, campaign_id, team_id)

    if campaign.status not in (ClientCampaignStatus.draft, ClientCampaignStatus.paused):
        raise BadRequestException("Campaign cannot be started from current status")

    if not campaign.steps:
        raise BadRequestException("Campaign must have at least one step")

    count = await db.execute(
        select(func.count(ClientCampaignEnrollment.id)).where(
            ClientCampaignEnrollment.campaign_id == campaign_id
        )
    )
    if (count.scalar() or 0) == 0:
        raise BadRequestException("No clients enrolled in this campaign")

    campaign.status = ClientCampaignStatus.active
    campaign.started_at = datetime.now(timezone.utc)

    # Commit BEFORE dispatching the Celery task so the worker always sees
    # status=active when it queries the DB — same race the influencer
    # pipeline's start_campaign guards against (see campaign_service.py).
    await db.commit()

    from app.workers.client_email_tasks import send_client_campaign_batch

    send_client_campaign_batch.delay(str(campaign_id), str(team_id))

    return await get_campaign(db, campaign_id, team_id)


async def pause_campaign(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID
) -> ClientCampaign:
    campaign = await get_campaign(db, campaign_id, team_id)
    if campaign.status != ClientCampaignStatus.active:
        raise BadRequestException("Only active campaigns can be paused")

    campaign.status = ClientCampaignStatus.paused
    await db.flush()
    return await get_campaign(db, campaign_id, team_id)


async def stop_campaign(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID
) -> ClientCampaign:
    campaign = await get_campaign(db, campaign_id, team_id)
    if campaign.status not in (ClientCampaignStatus.active, ClientCampaignStatus.paused):
        raise BadRequestException("Campaign is not active or paused")

    campaign.status = ClientCampaignStatus.completed
    campaign.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_campaign(db, campaign_id, team_id)


async def enroll_clients(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID, client_ids: list[uuid.UUID]
) -> int:
    campaign = await get_campaign(db, campaign_id, team_id)
    if campaign.status not in (ClientCampaignStatus.draft, ClientCampaignStatus.paused):
        raise BadRequestException("Can only enroll to draft or paused campaigns")

    existing = await db.execute(
        select(ClientCampaignEnrollment.client_id).where(
            ClientCampaignEnrollment.campaign_id == campaign_id
        )
    )
    existing_ids = {row[0] for row in existing}

    valid_clients = await db.execute(
        select(Client.id).where(
            Client.team_id == team_id,
            Client.id.in_(client_ids),
        )
    )
    valid_ids = {row[0] for row in valid_clients}

    count = 0
    now = datetime.now(timezone.utc)
    for client_id in client_ids:
        if client_id in valid_ids and client_id not in existing_ids:
            enrollment = ClientCampaignEnrollment(
                campaign_id=campaign_id,
                client_id=client_id,
                enrolled_at=now,
            )
            db.add(enrollment)
            count += 1

    await db.flush()
    return count


async def list_campaign_enrollments(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID
) -> list[dict]:
    await get_campaign(db, campaign_id, team_id)

    result = await db.execute(
        select(ClientCampaignEnrollment, Client)
        .join(Client, Client.id == ClientCampaignEnrollment.client_id)
        .where(ClientCampaignEnrollment.campaign_id == campaign_id)
        .order_by(ClientCampaignEnrollment.created_at.desc())
    )

    rows = result.all()

    client_ids = [client.id for _, client in rows]
    latest_msgs: dict[uuid.UUID, ClientEmailMessage] = {}
    if client_ids:
        latest_msgs_result = await db.execute(
            select(ClientEmailMessage)
            .where(
                ClientEmailMessage.campaign_id == campaign_id,
                ClientEmailMessage.client_id.in_(client_ids),
            )
            .distinct(ClientEmailMessage.client_id)
            .order_by(ClientEmailMessage.client_id, ClientEmailMessage.created_at.desc())
        )
        latest_msgs = {msg.client_id: msg for msg in latest_msgs_result.scalars().all()}

    items: list[dict] = []
    for enrollment, client in rows:
        latest_message = latest_msgs.get(client.id)

        failure_reason = None
        if enrollment.status == ClientCampaignInfluencerStatus.bounced:
            if not client.email:
                failure_reason = "Client is missing an email address"
            elif latest_message and latest_message.metadata_:
                failure_reason = latest_message.metadata_.get("failure_reason")
            else:
                failure_reason = "Email delivery failed"

        items.append(
            {
                "id": enrollment.id,
                "client_id": client.id,
                "client_company_name": client.company_name,
                "client_email": client.email,
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
        select(ClientCampaignEnrollment).where(
            ClientCampaignEnrollment.id == enrollment_id,
            ClientCampaignEnrollment.campaign_id == campaign_id,
        )
    )
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise NotFoundException("Campaign enrollment not found")
    await db.delete(enrollment)


async def get_send_progress(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID
) -> dict:
    campaign = await get_campaign(db, campaign_id, team_id)

    result = await db.execute(
        select(ClientCampaignEnrollment.status, func.count(ClientCampaignEnrollment.id))
        .where(ClientCampaignEnrollment.campaign_id == campaign_id)
        .group_by(ClientCampaignEnrollment.status)
    )
    by_status = {status.value: count for status, count in result.all()}
    total = sum(by_status.values())
    pending = by_status.get(ClientCampaignInfluencerStatus.queued.value, 0)
    failed = by_status.get(ClientCampaignInfluencerStatus.bounced.value, 0)
    sent = total - pending - failed
    processed = total - pending

    return {
        "campaign_status": campaign.status.value,
        "is_active": campaign.status == ClientCampaignStatus.active,
        "total": total,
        "pending": pending,
        "sent": sent,
        "failed": failed,
        "by_status": by_status,
        "progress_pct": round(processed / total * 100, 1) if total else 0.0,
    }


async def get_campaign_stats(db: AsyncSession, campaign_id: uuid.UUID) -> dict:
    result = await db.execute(
        select(ClientEmailMessage.status, func.count(ClientEmailMessage.id))
        .where(
            ClientEmailMessage.campaign_id == campaign_id,
            ClientEmailMessage.direction == ClientEmailDirection.outbound,
        )
        .group_by(ClientEmailMessage.status)
    )
    status_counts = dict(result.all())

    sent = sum(
        status_counts.get(s, 0)
        for s in [
            ClientEmailStatus.sent, ClientEmailStatus.delivered,
            ClientEmailStatus.opened, ClientEmailStatus.clicked,
        ]
    )
    delivered = status_counts.get(ClientEmailStatus.delivered, 0) + status_counts.get(
        ClientEmailStatus.opened, 0
    ) + status_counts.get(ClientEmailStatus.clicked, 0)
    opened = status_counts.get(ClientEmailStatus.opened, 0) + status_counts.get(
        ClientEmailStatus.clicked, 0
    )
    bounced = status_counts.get(ClientEmailStatus.bounced, 0)

    ce_result = await db.execute(
        select(
            func.count(ClientCampaignEnrollment.id).label("total_enrolled"),
            func.count(ClientCampaignEnrollment.id)
            .filter(ClientCampaignEnrollment.status == ClientCampaignInfluencerStatus.replied)
            .label("total_replied"),
        ).where(ClientCampaignEnrollment.campaign_id == campaign_id)
    )
    ce_row = ce_result.one()
    total_enrolled = ce_row.total_enrolled or 0
    total_replied = ce_row.total_replied or 0

    _SENT_STATUSES = [
        ClientEmailStatus.sent, ClientEmailStatus.delivered,
        ClientEmailStatus.opened, ClientEmailStatus.clicked,
    ]
    _OPENED_STATUSES = [ClientEmailStatus.opened, ClientEmailStatus.clicked]
    variant_col = ClientEmailMessage.metadata_["ab_variant"].astext
    variant_rows = await db.execute(
        select(
            variant_col.label("variant"),
            func.count(ClientEmailMessage.id)
            .filter(ClientEmailMessage.status.in_(_SENT_STATUSES))
            .label("sent"),
            func.count(ClientEmailMessage.id)
            .filter(ClientEmailMessage.status.in_(_OPENED_STATUSES))
            .label("opened"),
        )
        .where(
            ClientEmailMessage.campaign_id == campaign_id,
            ClientEmailMessage.direction == ClientEmailDirection.outbound,
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
