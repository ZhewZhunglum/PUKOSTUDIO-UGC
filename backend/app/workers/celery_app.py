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
    # NOTE: no task_routes. Previously email_tasks/ai_tasks were routed to
    # dedicated "email"/"ai" queues, but the worker (docker-compose and the
    # documented `celery ... worker` command) runs without `-Q`, so it only
    # consumes the default queue. That left campaign sends and AI drafts piling
    # up in queues nothing consumed — they silently never ran. All tasks now use
    # the default queue the single worker actually consumes.
    beat_schedule={
        "reset-daily-email-counts": {
            "task": "app.workers.email_tasks.reset_daily_counts",
            "schedule": crontab(hour=0, minute=0),  # Midnight UTC
        },
    },
)

celery_app.autodiscover_tasks(["app.workers"])
