"""Thin Celery wrappers around the engine (all logic lives in engine.py)."""

import uuid

from ayin.config import get_settings
from ayin.connectors import registry as global_registry
from ayin.db import get_sessionmaker
from ayin.orchestrator import engine
from ayin.orchestrator.celery_app import celery_app
from ayin.vault import NullVault


def _vault():
    """Real encrypted vault once configured (M1-5); refusing NullVault otherwise."""
    try:
        from ayin.vault.store import DbVault  # noqa: PLC0415

        return DbVault(get_settings())
    except Exception:  # not yet shipped/configured
        return NullVault()


@celery_app.task(name="ayin.scan.gate_and_dispatch")
def gate_and_dispatch(scan_id: str) -> str:
    from ayin.models import Scan  # noqa: PLC0415

    settings = get_settings()
    with get_sessionmaker()() as db:
        scan = db.get(Scan, uuid.UUID(scan_id))
        if scan is None:
            return "missing"
        result = engine.gate_scan(db, scan, settings)
        if not result.passed:
            return result.decision.value
        jobs = engine.dispatch_scan(db, scan, global_registry)
        for job in jobs:
            run_job.delay(str(job.id))
        return f"dispatched:{len(jobs)}"


@celery_app.task(name="ayin.scan.run_job")
def run_job(job_id: str) -> str:
    from ayin.models import ConnectorJob  # noqa: PLC0415

    with get_sessionmaker()() as db:
        status = engine.run_connector_job(db, uuid.UUID(job_id), global_registry, _vault())
        job = db.get(ConnectorJob, uuid.UUID(job_id))
        if job is not None:
            if status.value == "queued":  # transient failure → bounded retry
                run_job.apply_async(args=[job_id], countdown=30)
            engine.finalize_scan_if_complete(db, job.scan_id)
        return status.value


@celery_app.task(name="ayin.scan.resume_stalled")
def resume_stalled() -> dict:
    settings = get_settings()
    with get_sessionmaker()() as db:
        return engine.resume_stalled(
            db, settings=settings, registry=global_registry, vault=_vault()
        )


@celery_app.task(name="ayin.vault.purge_expired")
def vault_purge_expired() -> int:
    try:
        from ayin.vault.store import purge_expired  # noqa: PLC0415
    except ImportError:
        return 0
    with get_sessionmaker()() as db:
        return purge_expired(db)
