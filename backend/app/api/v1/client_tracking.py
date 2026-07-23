import base64
import uuid

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.client_campaign import ClientCampaignEnrollment, ClientCampaignInfluencerStatus
from app.models.client_email_message import (
    ClientEmailEventType,
    ClientEmailMessage,
    ClientEmailStatus,
)
from app.models.suppression import SuppressionReason
from app.services import suppression_service
from app.services.client_email_sending_service import update_client_message_status

router = APIRouter()

_UNSUB_OK_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>退订成功</title></head>
<body style="font-family:Arial,Helvetica,sans-serif;display:flex;align-items:center;
justify-content:center;height:100vh;margin:0;background:#faf9f7;color:#374151">
<div style="text-align:center"><h2>退订成功</h2>
<p>你将不会再收到我们的邮件。</p></div></body></html>"""


async def _process_unsubscribe(db: AsyncSession, message_id: str) -> bool:
    """Suppress the recipient of the given B2B client message. Returns True if applied."""
    try:
        msg_id = uuid.UUID(message_id)
    except (ValueError, TypeError):
        return False

    result = await db.execute(select(ClientEmailMessage).where(ClientEmailMessage.id == msg_id))
    msg = result.scalar_one_or_none()
    if not msg:
        return False

    await suppression_service.add_suppression(
        db, msg.team_id, msg.to_address, SuppressionReason.unsubscribed
    )
    enrollments = await db.execute(
        select(ClientCampaignEnrollment).where(
            ClientCampaignEnrollment.client_id == msg.client_id
        )
    )
    for enrollment in enrollments.scalars().all():
        enrollment.status = ClientCampaignInfluencerStatus.unsubscribed
    await db.flush()
    return True


@router.get("/unsubscribe/{message_id}", response_class=HTMLResponse)
async def unsubscribe_click(message_id: str, db: AsyncSession = Depends(get_db)):
    """Human click on the footer link. Always shows the confirmation page."""
    await _process_unsubscribe(db, message_id)
    return HTMLResponse(content=_UNSUB_OK_HTML)


@router.post("/unsubscribe/{message_id}")
async def unsubscribe_one_click(message_id: str, db: AsyncSession = Depends(get_db)):
    """RFC 8058 one-click unsubscribe — mailbox providers POST here directly."""
    await _process_unsubscribe(db, message_id)
    return {"status": "ok"}

TRANSPARENT_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WH0r1sAAAAASUVORK5CYII="
)


@router.get("/open/{message_id}.png")
async def track_open(message_id: str, db: AsyncSession = Depends(get_db)):
    try:
        client_email_message_id = uuid.UUID(message_id)
        await update_client_message_status(
            db,
            client_email_message_id=client_email_message_id,
            status=ClientEmailStatus.opened,
            event_type=ClientEmailEventType.opened,
            raw_data={"source": "tracking_pixel"},
        )
    except (ValueError, TypeError):
        pass

    return Response(
        content=TRANSPARENT_PIXEL,
        media_type="image/png",
        headers={"Cache-Control": "no-store, no-cache, max-age=0"},
    )


@router.get("/click/{message_id}")
async def track_click(
    message_id: str, url: str = Query(...), db: AsyncSession = Depends(get_db)
):
    """Redirect through a click record — see tracking.py's track_click for why
    a click is a stronger engagement signal than the open pixel."""
    if not url.startswith(("http://", "https://")):
        return Response(status_code=400, content="Invalid redirect target")

    try:
        client_email_message_id = uuid.UUID(message_id)
        await update_client_message_status(
            db,
            client_email_message_id=client_email_message_id,
            status=ClientEmailStatus.clicked,
            event_type=ClientEmailEventType.clicked,
            raw_data={"source": "click_redirect", "url": url},
        )
    except (ValueError, TypeError):
        pass

    return RedirectResponse(url, status_code=302)
