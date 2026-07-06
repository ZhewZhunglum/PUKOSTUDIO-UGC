import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import conversation_service

logger = logging.getLogger(__name__)
router = APIRouter()


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
