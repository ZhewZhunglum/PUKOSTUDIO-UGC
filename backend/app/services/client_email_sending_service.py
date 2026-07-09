import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_campaign import ClientCampaignEnrollment, ClientCampaignInfluencerStatus
from app.models.client_email_message import (
    ClientEmailEvent,
    ClientEmailEventType,
    ClientEmailMessage,
    ClientEmailStatus,
)

# Mirrors email_sending_service._STATUS_RANK/_TERMINAL_NEGATIVE — see that
# module for the out-of-order-webhook-event rationale.
_STATUS_RANK = {
    ClientEmailStatus.queued: 0,
    ClientEmailStatus.sending: 1,
    ClientEmailStatus.sent: 2,
    ClientEmailStatus.delivered: 3,
    ClientEmailStatus.opened: 4,
    ClientEmailStatus.clicked: 5,
}
_TERMINAL_NEGATIVE = {
    ClientEmailStatus.bounced, ClientEmailStatus.complained, ClientEmailStatus.failed,
}


def _should_apply_status(current: ClientEmailStatus, new: ClientEmailStatus) -> bool:
    if new in _TERMINAL_NEGATIVE:
        return current not in _TERMINAL_NEGATIVE
    if current in _TERMINAL_NEGATIVE:
        return False
    return _STATUS_RANK.get(new, -1) > _STATUS_RANK.get(current, -1)


async def update_client_message_status(
    db: AsyncSession,
    message_id: str | None = None,
    client_email_message_id: uuid.UUID | None = None,
    status: ClientEmailStatus = ClientEmailStatus.sent,
    event_type: ClientEmailEventType | None = None,
    raw_data: dict | None = None,
) -> ClientEmailMessage | None:
    """Mirrors email_sending_service.update_message_status for the B2B pipeline.

    Webhook handlers call this as a fallback when the influencer-side lookup
    finds no matching message — provider message IDs never collide across
    the two tables, so trying both is safe.
    """
    if client_email_message_id:
        result = await db.execute(
            select(ClientEmailMessage).where(ClientEmailMessage.id == client_email_message_id)
        )
    elif message_id:
        result = await db.execute(
            select(ClientEmailMessage).where(ClientEmailMessage.message_id == message_id)
        )
    else:
        return None

    msg = result.scalar_one_or_none()
    if not msg:
        return None

    now = datetime.now(timezone.utc)

    if status == ClientEmailStatus.sent:
        msg.sent_at = msg.sent_at or now
    elif status == ClientEmailStatus.opened:
        msg.opened_at = msg.opened_at or now
    elif status == ClientEmailStatus.clicked:
        msg.clicked_at = msg.clicked_at or now

    if _should_apply_status(msg.status, status):
        msg.status = status

    if event_type:
        existing_event = await db.execute(
            select(ClientEmailEvent).where(
                ClientEmailEvent.client_email_message_id == msg.id,
                ClientEmailEvent.event_type == event_type,
            )
        )
        if existing_event.scalar_one_or_none() is None:
            event = ClientEmailEvent(
                client_email_message_id=msg.id,
                event_type=event_type,
                occurred_at=now,
                raw_data=raw_data,
            )
            db.add(event)

    if status in {ClientEmailStatus.bounced, ClientEmailStatus.complained}:
        from app.models.suppression import SuppressionReason
        from app.services import suppression_service

        reason = (
            SuppressionReason.complained
            if status == ClientEmailStatus.complained
            else SuppressionReason.bounced
        )
        await suppression_service.add_suppression(db, msg.team_id, msg.to_address, reason)

        if msg.campaign_id:
            enrollment = await db.execute(
                select(ClientCampaignEnrollment).where(
                    ClientCampaignEnrollment.campaign_id == msg.campaign_id,
                    ClientCampaignEnrollment.client_id == msg.client_id,
                )
            )
            client_enrollment = enrollment.scalar_one_or_none()
            if client_enrollment:
                client_enrollment.status = ClientCampaignInfluencerStatus.bounced

    await db.flush()
    return msg
