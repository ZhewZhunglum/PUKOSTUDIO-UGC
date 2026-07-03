import asyncio
import uuid

from app.services.woto_service import run_sync_job
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.woto_tasks.sync_woto_influencers")
def sync_woto_influencers(job_id: str) -> None:
    asyncio.run(run_sync_job(uuid.UUID(job_id)))
