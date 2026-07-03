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
        conversation_id = result.get("conversation_id")
        if conversation_id:
            from app.workers.ai_tasks import process_inbound_conversation

            process_inbound_conversation.delay(str(conversation_id))
        return {"status": "ok", **result}
    except Exception as exc:
        logger.exception("Failed to process inbound email")
        return {"status": "error", "detail": str(exc)}
