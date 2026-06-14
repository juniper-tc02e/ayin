"""Celery application (async driver for the scan pipeline)."""

from celery import Celery
from celery.signals import worker_process_init

from ayin.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ayin",
    broker=settings.redis_url,
    backend=None,  # job state lives in Postgres, not a result backend
    # The worker boots from this module (-A ayin.orchestrator.celery_app),
    # so the task module must be imported here or the tasks are never
    # registered and the worker silently runs nothing.
    include=["ayin.orchestrator.tasks"],
)


@worker_process_init.connect
def _enable_connectors_in_worker(**_: object) -> None:
    """The worker dispatches/runs connector jobs, so its registry must be
    enabled too — the API's create_app() bootstrap doesn't run in this
    process. Lazy import to avoid an import cycle at module load."""
    from ayin.connectors.bootstrap import configure_default_connectors

    configure_default_connectors(get_settings())


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
