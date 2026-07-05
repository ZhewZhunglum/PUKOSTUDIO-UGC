import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.services import ai_communication_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Each Celery task runs its coroutine via asyncio.run(), which creates a fresh
# event loop every time. asyncpg connections are bound to the loop that opened
# them, so a pooled connection reused on a later loop raises "attached to a
# different loop". NullPool opens and closes a connection per session, keeping
# nothing across loops, so this module-level engine is safe for the worker.
_worker_engine = create_async_engine(settings.database_url, poolclass=NullPool)
async_session = async_sessionmaker(
    _worker_engine, class_=AsyncSession, expire_on_commit=False
)


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
