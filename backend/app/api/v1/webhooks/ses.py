import json
import logging
import re
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestException
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


# SNS-owned URLs (SubscribeURL / SigningCertURL) must live on the regional SNS
# host over https; anything else is a forged payload trying to make us GET an
# attacker-controlled URL.
_SNS_HOST_RE = re.compile(r"sns\.[a-z0-9-]+\.amazonaws\.com")
_SNS_CONFIRM_TIMEOUT_SECONDS = 10.0


def _is_trusted_sns_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    return _SNS_HOST_RE.fullmatch(parsed.hostname) is not None


async def _confirm_sns_subscription(body: dict) -> None:
    """Visit SubscribeURL so the SNS topic subscription leaves PendingConfirmation.

    Without this, SES delivery/bounce/open events are never delivered. A failed
    confirmation raises so SNS gets a non-2xx and retries the confirmation.
    """
    signing_cert_url = body.get("SigningCertURL")
    subscribe_url = body.get("SubscribeURL")
    if not _is_trusted_sns_url(signing_cert_url) or not _is_trusted_sns_url(subscribe_url):
        logger.warning(
            "Rejected SNS SubscriptionConfirmation with untrusted URLs: "
            "SigningCertURL=%r SubscribeURL=%r",
            signing_cert_url,
            subscribe_url,
        )
        raise BadRequestException("Untrusted SNS confirmation URLs")

    try:
        async with httpx.AsyncClient(timeout=_SNS_CONFIRM_TIMEOUT_SECONDS) as client:
            response = await client.get(subscribe_url)
    except httpx.HTTPError as exc:
        logger.error("SNS subscription confirmation request failed: %s", exc)
        raise BadRequestException("SNS subscription confirmation request failed") from exc

    if response.status_code >= 400:
        logger.error(
            "SNS subscription confirmation rejected: HTTP %s for topic %r",
            response.status_code,
            body.get("TopicArn"),
        )
        raise BadRequestException("SNS subscription confirmation rejected")

    logger.info("Confirmed SNS subscription for topic %r", body.get("TopicArn"))


@router.post("")
async def ses_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()

    # Handle SNS subscription confirmation
    if body.get("Type") == "SubscriptionConfirmation":
        await _confirm_sns_subscription(body)
        return {"status": "ok"}

    if body.get("Type") == "UnsubscribeConfirmation":
        # Deliberately no auto-resubscribe: an unexpected unsubscribe should be
        # investigated in the AWS console, not silently undone.
        logger.warning(
            "SNS UnsubscribeConfirmation received for topic %r; SES events will "
            "stop until the subscription is restored.",
            body.get("TopicArn"),
        )
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
