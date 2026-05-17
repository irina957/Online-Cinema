from celery import Celery
from celery.schedules import crontab
from src.config.settings import settings

celery_app = Celery(
    "cinema",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["src.tasks.accounts"],
)

celery_app.conf.beat_schedule = {
    "delete-expired-tokens-every-hour": {
        "task": "delete_expired_tokens_task",
        "schedule": crontab(minute=0),
    },
}

celery_app.conf.timezone = "UTC"
