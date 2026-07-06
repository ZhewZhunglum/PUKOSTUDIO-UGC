import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.email_message import EmailEventType, EmailStatus
from app.services.email_sending_service import update_message_status

logger = logging.getLogger(__name__)
router = APIRouter()

SENDGRID_EVENT_MAP = {
    "delivered": (EmailStatus.delivered, EmailEventType.delivered),
    "open": (EmailStatus.opened, EmailEventType.opened),
    "click": (EmailStatus.clicked, EmailEventType.clicked),
    "bounce": (EmailStatus.bounced, EmailEventType.bounced),
    "spamreport": (EmailStatus.complained, EmailEventType.complained),
    "unsubscribe": (EmailStatus.complained, EmailEventType.unsubscribed),
}


@router.post("")
async def sendgrid_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    events = await request.json()

    if not isinstance(events, list):
        events = [events]

    failed = False
    for event in events:
        try:
            event_type_str = event.get("event")
            if event_type_str not in SENDGRID_EVENT_MAP:
                continue

            status, event_type = SENDGRID_EVENT_MAP[event_type_str]
            sg_message_id = event.get("sg_message_id", "").split(".")[0]

            if sg_message_id:
                await update_message_status(
                    db,
                    message_id=sg_message_id,
                    status=status,
                    event_type=event_type,
                    raw_data=event,
                )
        except Exception:
            logger.exception("Error processing SendGrid event")
            failed = True

    if failed:
        # Surface a non-2xx so SendGrid redelivers the batch instead of dropping
        # events silently. update_message_status is idempotent, so reprocessing
        # already-applied events in the batch is safe.
        raise RuntimeError("One or more SendGrid events failed to process")

    return {"status": "ok"}
