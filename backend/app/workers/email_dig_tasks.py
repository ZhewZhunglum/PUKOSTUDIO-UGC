import asyncio
import uuid

from app.services.email_dig_service import run_job
from app.services.woto_backfill_service import run_backfill_job
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.email_dig_tasks.run_email_dig")
def run_email_dig(job_id: str) -> None:
    asyncio.run(run_job(uuid.UUID(job_id)))


@celery_app.task(name="app.workers.email_dig_tasks.run_woto_backfill")
def run_woto_backfill(job_id: str) -> None:
    asyncio.run(run_backfill_job(uuid.UUID(job_id)))
