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
        # Dispatch due follow-up steps for multi-step campaigns.
        "process-campaign-followups": {
            "task": "app.workers.email_tasks.process_followups",
            "schedule": crontab(minute="*/15"),
        },
        # advance_warmup must run BEFORE reset_daily_counts zeroes sent_today,
        # since it only promotes accounts that actually sent mail today.
        "advance-email-warmup": {
            "task": "app.workers.email_tasks.advance_warmup",
            "schedule": crontab(hour=23, minute=50),
        },
        "reset-daily-email-counts": {
            "task": "app.workers.email_tasks.reset_daily_counts",
            "schedule": crontab(hour=0, minute=0),  # Midnight UTC
        },
    },
)

celery_app.autodiscover_tasks(["app.workers"])
