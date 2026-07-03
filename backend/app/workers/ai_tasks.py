import asyncio
import logging
import uuid

from app.core.database import async_session
from app.services import ai_communication_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_classification(conversation_id: str) -> dict:
    async with async_session() as db:
        try:
            conversation = await ai_communication_service.classify_conversation(
                db, uuid.UUID(conversation_id)
            )
            await db.commit()
            return {
                "status": "ok",
                "intent": conversation.ai_intent.value if conversation.ai_intent else None,
                "confidence": conversation.ai_confidence,
            }
        except Exception as exc:
            await db.rollback()
            logger.exception("Failed to classify reply for conversation %s", conversation_id)
            return {"status": "error", "detail": str(exc)}


async def _run_draft(conversation_id: str, guidelines: str = "") -> dict:
    async with async_session() as db:
        try:
            draft = await ai_communication_service.create_ai_draft(
                db,
                uuid.UUID(conversation_id),
                team_id=(await ai_communication_service._get_conversation(
                    db, uuid.UUID(conversation_id)
                ))[0].team_id,
                guidelines=guidelines,
            )
            await db.commit()
            return {"status": draft.status.value, "draft_id": str(draft.id)}
        except Exception as exc:
            await db.rollback()
            logger.exception("Failed to draft reply for conversation %s", conversation_id)
            return {"status": "error", "detail": str(exc)}


async def _run_process(conversation_id: str) -> dict:
    async with async_session() as db:
        try:
            draft = await ai_communication_service.process_inbound_conversation(
                db, uuid.UUID(conversation_id)
            )
            await db.commit()
            return {
                "status": "ok",
                "draft_id": str(draft.id) if draft else None,
                "draft_status": draft.status.value if draft else None,
            }
        except Exception as exc:
            await db.rollback()
            logger.exception("Failed to process inbound conversation %s", conversation_id)
            return {"status": "error", "detail": str(exc)}


@celery_app.task(name="app.workers.ai_tasks.classify_inbound_reply")
def classify_inbound_reply(conversation_id: str):
    return asyncio.run(_run_classification(conversation_id))


@celery_app.task(name="app.workers.ai_tasks.draft_reply")
def draft_reply(conversation_id: str, guidelines: str = ""):
    return asyncio.run(_run_draft(conversation_id, guidelines))


@celery_app.task(name="app.workers.ai_tasks.process_inbound_conversation")
def process_inbound_conversation(conversation_id: str):
    return asyncio.run(_run_process(conversation_id))
