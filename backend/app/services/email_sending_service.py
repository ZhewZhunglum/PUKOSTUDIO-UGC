import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import CampaignInfluencer, CampaignInfluencerStatus
from app.models.email_message import (
    EmailDirection,
    EmailEvent,
    EmailEventType,
    EmailMessage,
    EmailStatus,
)

# Forward progression of a healthy delivery lifecycle. Higher rank = later stage.
_STATUS_RANK = {
    EmailStatus.queued: 0,
    EmailStatus.sending: 1,
    EmailStatus.sent: 2,
    EmailStatus.delivered: 3,
    EmailStatus.opened: 4,
    EmailStatus.clicked: 5,
}
# Terminal negative outcomes; these always take precedence over progression.
_TERMINAL_NEGATIVE = {EmailStatus.bounced, EmailStatus.complained, EmailStatus.failed}


def _should_apply_status(current: EmailStatus, new: EmailStatus) -> bool:
    """Decide whether an incoming webhook event should overwrite the status.

    Provider events can arrive out of order (a late "delivered" after "opened",
    or a duplicate). Without this guard, ``msg.status = status`` would silently
    downgrade an already opened/clicked message. Rules:
    - A terminal negative (bounced/complained/failed) always applies, unless the
      message is already in a terminal negative state.
    - Once terminal negative, positive progression events are ignored.
    - Otherwise only move forward along the lifecycle.
    """
    if new in _TERMINAL_NEGATIVE:
        return current not in _TERMINAL_NEGATIVE
    if current in _TERMINAL_NEGATIVE:
        return False
    return _STATUS_RANK.get(new, -1) > _STATUS_RANK.get(current, -1)


async def create_outbound_message(
    db: AsyncSession,
    team_id: uuid.UUID,
    influencer_id: uuid.UUID,
    email_account_id: uuid.UUID,
    to_address: str,
    from_address: str,
    subject: str,
    body_html: str,
    body_text: str | None = None,
    campaign_id: uuid.UUID | None = None,
    campaign_step_id: uuid.UUID | None = None,
) -> EmailMessage:
    message = EmailMessage(
        team_id=team_id,
        campaign_id=campaign_id,
        campaign_step_id=campaign_step_id,
        influencer_id=influencer_id,
        email_account_id=email_account_id,
        direction=EmailDirection.outbound,
        from_address=from_address,
        to_address=to_address,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        status=EmailStatus.queued,
    )
    db.add(message)
    await db.flush()
    return message


async def update_message_status(
    db: AsyncSession,
    message_id: str | None = None,
    email_message_id: uuid.UUID | None = None,
    status: EmailStatus = EmailStatus.sent,
    event_type: EmailEventType | None = None,
    raw_data: dict | None = None,
) -> EmailMessage | None:
    if email_message_id:
        result = await db.execute(
            select(EmailMessage).where(EmailMessage.id == email_message_id)
        )
    elif message_id:
        result = await db.execute(
            select(EmailMessage).where(EmailMessage.message_id == message_id)
        )
    else:
        return None

    msg = result.scalar_one_or_none()
    if not msg:
        return None

    now = datetime.now(timezone.utc)

    # Record event timestamps regardless of arrival order (idempotent).
    if status == EmailStatus.sent:
        msg.sent_at = msg.sent_at or now
    elif status == EmailStatus.opened:
        msg.opened_at = msg.opened_at or now
    elif status == EmailStatus.clicked:
        msg.clicked_at = msg.clicked_at or now

    # Only advance status forward so an out-of-order event can't downgrade it.
    if _should_apply_status(msg.status, status):
        msg.status = status

    # Record event
    if event_type:
        existing_event = await db.execute(
            select(EmailEvent).where(
                EmailEvent.email_message_id == msg.id,
                EmailEvent.event_type == event_type,
            )
        )
        if existing_event.scalar_one_or_none() is None:
            event = EmailEvent(
                email_message_id=msg.id,
                event_type=event_type,
                occurred_at=now,
                raw_data=raw_data,
            )
            db.add(event)

    if status in {EmailStatus.bounced, EmailStatus.complained}:
        # Auto-suppress the address so we stop mailing it (protects reputation).
        from app.models.suppression import SuppressionReason
        from app.services import suppression_service

        reason = (
            SuppressionReason.complained
            if status == EmailStatus.complained
            else SuppressionReason.bounced
        )
        await suppression_service.add_suppression(db, msg.team_id, msg.to_address, reason)

        if msg.campaign_id:
            enrollment = await db.execute(
                select(CampaignInfluencer).where(
                    CampaignInfluencer.campaign_id == msg.campaign_id,
                    CampaignInfluencer.influencer_id == msg.influencer_id,
                )
            )
            campaign_influencer = enrollment.scalar_one_or_none()
            if campaign_influencer:
                campaign_influencer.status = CampaignInfluencerStatus.bounced

    await db.flush()
    return msg


async def get_influencer_emails(
    db: AsyncSession, influencer_id: uuid.UUID, team_id: uuid.UUID
) -> list[EmailMessage]:
    result = await db.execute(
        select(EmailMessage)
        .where(
            EmailMessage.influencer_id == influencer_id,
            EmailMessage.team_id == team_id,
        )
        .order_by(EmailMessage.created_at.desc())
    )
    return list(result.scalars().all())
