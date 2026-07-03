from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "ugc_outreach",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.email_tasks",
        "app.workers.import_tasks",
        "app.workers.ai_tasks",
        "app.workers.woto_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.email_tasks.*": {"queue": "email"},
        "app.workers.import_tasks.*": {"queue": "default"},
        "app.workers.ai_tasks.*": {"queue": "ai"},
        "app.workers.woto_tasks.*": {"queue": "default"},
    },
    beat_schedule={
        "reset-daily-email-counts": {
            "task": "app.workers.email_tasks.reset_daily_counts",
            "schedule": crontab(hour=0, minute=0),  # Midnight UTC
        },
    },
)

celery_app.autodiscover_tasks(["app.workers"])
