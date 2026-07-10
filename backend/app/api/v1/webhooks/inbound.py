import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.services import client_conversation_service, conversation_service

logger = logging.getLogger(__name__)
router = APIRouter()

_UNKNOWN_INFLUENCER_DETAIL = "Inbound sender is not a known influencer"


@router.post("")
async def inbound_email(request: Request, db: AsyncSession = Depends(get_db)):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)

    logger.info("Inbound email received from %s", body.get("from", "unknown"))
    try:
        result = await conversation_service.ingest_inbound_email(db, body)
    except NotFoundException as exc:
        # Sender isn't a known influencer — try the B2B client pipeline before
        # giving up. Both lookups are keyed on from_email within the same team,
        # so this is a safe additive fallback with no risk to the influencer path.
        if exc.detail != _UNKNOWN_INFLUENCER_DETAIL:
            # Any other not-found (e.g. recipient account missing) used to be
            # logged by the catch-all below; keep it visible in production logs.
            logger.exception("Failed to process inbound email")
            raise
        try:
            result = await client_conversation_service.ingest_inbound_email(db, body)
        except Exception:
            logger.exception("Failed to process inbound email (client fallback)")
            raise
        conversation_id = result.get("conversation_id")
        if conversation_id:
            await db.commit()
        return {"status": "ok", **result}
    except Exception:
        # Re-raise so get_db rolls back and the provider gets a non-2xx and
        # retries. Previously this returned HTTP 200 on failure, which made the
        # provider treat the delivery as accepted and silently drop the email.
        logger.exception("Failed to process inbound email")
        raise

    conversation_id = result.get("conversation_id")
    if conversation_id:
        # Persist the conversation before dispatching the background task so the
        # worker (which uses its own session) can actually see it.
        await db.commit()

        from app.workers.ai_tasks import process_inbound_conversation

        process_inbound_conversation.delay(str(conversation_id))
    return {"status": "ok", **result}
