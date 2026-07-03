import base64
import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.email_message import EmailEventType, EmailStatus
from app.services.email_sending_service import update_message_status

router = APIRouter()

TRANSPARENT_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WH0r1sAAAAASUVORK5CYII="
)


@router.get("/open/{message_id}.png")
async def track_open(message_id: str, db: AsyncSession = Depends(get_db)):
    try:
        email_message_id = uuid.UUID(message_id)
        await update_message_status(
            db,
            email_message_id=email_message_id,
            status=EmailStatus.opened,
            event_type=EmailEventType.opened,
            raw_data={"source": "tracking_pixel"},
        )
    except (ValueError, TypeError):
        # Always return the tracking pixel, even for malformed IDs.
        pass

    return Response(
        content=TRANSPARENT_PIXEL,
        media_type="image/png",
        headers={"Cache-Control": "no-store, no-cache, max-age=0"},
    )
