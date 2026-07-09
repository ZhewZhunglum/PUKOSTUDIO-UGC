import json
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.client_email_message import ClientEmailEventType, ClientEmailStatus
from app.models.email_message import EmailEventType, EmailStatus
from app.services.client_email_sending_service import update_client_message_status
from app.services.email_sending_service import update_message_status

logger = logging.getLogger(__name__)
router = APIRouter()

SES_EVENT_MAP = {
    "Delivery": (EmailStatus.delivered, EmailEventType.delivered),
    "Bounce": (EmailStatus.bounced, EmailEventType.bounced),
    "Complaint": (EmailStatus.complained, EmailEventType.complained),
    "Open": (EmailStatus.opened, EmailEventType.opened),
    "Click": (EmailStatus.clicked, EmailEventType.clicked),
}

# Same provider notificationType keys, mapped onto the B2B client pipeline's
# own status/event enums for the additive client-message fallback lookup.
SES_CLIENT_EVENT_MAP = {
    "Delivery": (ClientEmailStatus.delivered, ClientEmailEventType.delivered),
    "Bounce": (ClientEmailStatus.bounced, ClientEmailEventType.bounced),
    "Complaint": (ClientEmailStatus.complained, ClientEmailEventType.complained),
    "Open": (ClientEmailStatus.opened, ClientEmailEventType.opened),
    "Click": (ClientEmailStatus.clicked, ClientEmailEventType.clicked),
}


@router.post("")
async def ses_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()

    # Handle SNS subscription confirmation
    if body.get("Type") == "SubscriptionConfirmation":
        logger.info("SES SNS subscription confirmation received")
        # In production, verify and confirm the subscription
        return {"status": "ok"}

    # Handle notification
    if body.get("Type") == "Notification":
        try:
            message = json.loads(body.get("Message", "{}"))
            notification_type = message.get("notificationType") or message.get("eventType")

            if notification_type in SES_EVENT_MAP:
                status, event_type = SES_EVENT_MAP[notification_type]

                # Extract message ID from mail headers
                mail = message.get("mail", {})
                ses_message_id = mail.get("messageId")

                if ses_message_id:
                    matched = await update_message_status(
                        db,
                        message_id=ses_message_id,
                        status=status,
                        event_type=event_type,
                        raw_data=message,
                    )
                    if not matched and notification_type in SES_CLIENT_EVENT_MAP:
                        client_status, client_event_type = SES_CLIENT_EVENT_MAP[notification_type]
                        await update_client_message_status(
                            db,
                            message_id=ses_message_id,
                            status=client_status,
                            event_type=client_event_type,
                            raw_data=message,
                        )
        except Exception:
            # Re-raise so get_db rolls back and SNS gets a non-2xx and redelivers.
            # Swallowing here (returning 200) permanently drops the event and
            # silently corrupts delivery/open/bounce metrics. update_message_status
            # is idempotent, so redelivery is safe.
            logger.exception("Error processing SES webhook")
            raise

    return {"status": "ok"}
