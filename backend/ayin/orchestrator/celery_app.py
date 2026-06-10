"""Celery application (async driver for the scan pipeline)."""

from celery import Celery

from ayin.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ayin",
    broker=settings.redis_url,
    backend=None,  # job state lives in Postgres, not a result backend
)
celery_app.conf.update(
    task_acks_late=True,  # a killed worker's task gets redelivered
    worker_prefetch_multiplier=1,
    task_default_queue="ayin.scans",
    beat_schedule={
        "resume-stalled-scans": {
            "task": "ayin.scan.resume_stalled",
            "schedule": 60.0,
        },
        "vault-retention-purge": {
            "task": "ayin.vault.purge_expired",
            "schedule": 3600.0,
        },
    },
)
