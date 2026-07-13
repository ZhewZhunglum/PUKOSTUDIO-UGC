import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.services.woto_service import run_sync_job
from app.workers.celery_app import celery_app

# Each Celery task runs its coroutine via asyncio.run(), which creates a fresh
# event loop every time. asyncpg connections are bound to the loop that opened
# them, so a pooled connection reused on a later loop raises "attached to a
# different loop". NullPool opens and closes a connection per session, keeping
# nothing across loops, so this module-level engine is safe for the worker.
_worker_engine = create_async_engine(settings.database_url, poolclass=NullPool)
async_session = async_sessionmaker(
    _worker_engine, class_=AsyncSession, expire_on_commit=False
)


@celery_app.task(name="app.workers.woto_tasks.sync_woto_influencers")
def sync_woto_influencers(job_id: str) -> None:
    asyncio.run(run_sync_job(uuid.UUID(job_id), session_factory=async_session))
