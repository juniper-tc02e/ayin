"""Scan endpoints (FR-SCAN-1, M1-1).

Gate order at scan start: session auth → ToS/AUP (require_tos) → pipeline
gates (verified anchor, exclusion, rate limits) inside the engine. Findings
are served through the visibility filter; credential-category findings are
REDACTED until a valid step-up token is presented (FR-AUTH-1).
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from ayin.api.deps import CurrentUser, DbDep, SettingsDep
from ayin.api.routes.identifiers import get_my_subject
from ayin.api.schemas import FindingOut, FindingsPage, JobOut, ScanOut, ScanProgress
from ayin.auth.tokens import SCOPE_STEP_UP, decode_token
from ayin.connectors import ConnectorRegistry
from ayin.connectors import registry as global_registry
from ayin.models import ConnectorJob, Finding, Scan, Subject
from ayin.models.enums import FindingCategory, JobStatus
from ayin.orchestrator import engine
from ayin.safety.audit import record_data_access, user_actor
from ayin.safety.tos import require_tos
from ayin.safety.visibility import visible_findings_query
from ayin.vault import NullVault, VaultProtocol

log = logging.getLogger("ayin.scans")
router = APIRouter(prefix="/scans", tags=["scans"])

_REFUSAL_HTTP: list[tuple[str, int]] = [
    ("rate_limited", status.HTTP_429_TOO_MANY_REQUESTS),
    ("no_verified_anchor", status.HTTP_422_UNPROCESSABLE_ENTITY),
    ("subject_excluded", status.HTTP_403_FORBIDDEN),
]


def get_registry() -> ConnectorRegistry:
    return global_registry


def get_vault(settings: SettingsDep) -> VaultProtocol:
    try:
        from ayin.vault.store import DbVault  # noqa: PLC0415

        return DbVault(settings)
    except Exception:
        return NullVault()


def _scan_out(db, scan: Scan) -> ScanOut:
    jobs = db.execute(
        select(ConnectorJob).where(ConnectorJob.scan_id == scan.id).order_by(
            ConnectorJob.connector_id
        )
    ).scalars().all()
    return ScanOut(
        id=scan.id,
        status=scan.status.value,
        tier=scan.tier.value,
        purpose=scan.purpose,
        error=scan.error,
        source_set=scan.source_set or [],
        created_at=scan.created_at,
        started_at=scan.started_at,
        finished_at=scan.finished_at,
        progress=ScanProgress(
            jobs_total=len(jobs),
            jobs_done=sum(1 for j in jobs if j.status == JobStatus.DONE),
            jobs_failed=sum(1 for j in jobs if j.status == JobStatus.FAILED),
        ),
        jobs=[
            JobOut(
                connector_id=j.connector_id,
                status=j.status.value,
                findings_count=j.findings_count,
                attempts=j.attempts,
                error=j.error,
            )
            for j in jobs
        ],
    )


def _owned_scan(db, subject: Subject, scan_id: uuid.UUID) -> Scan:
    scan = db.execute(
        select(Scan).where(Scan.id == scan_id, Scan.subject_id == subject.id)
    ).scalar_one_or_none()
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan not found.")
    return scan


@router.post("", response_model=ScanOut, status_code=status.HTTP_202_ACCEPTED)
def start_scan(
    db: DbDep,
    settings: SettingsDep,
    user=Depends(require_tos),  # ToS/AUP gate (FR-AUTH-2) on the way in
    registry: ConnectorRegistry = Depends(get_registry),
    vault: VaultProtocol = Depends(get_vault),
):
    inline = settings.scan_execution == "inline"
    scan, result = engine.start_scan(
        db, requester=user, settings=settings, registry=registry, vault=vault, inline=inline
    )
    if not result.passed and result.decision.value == "refuse":
        code = next(
            (http for prefix, http in _REFUSAL_HTTP if result.reason.startswith(prefix)),
            status.HTTP_409_CONFLICT,
        )
        raise HTTPException(
            code, detail={"scan_id": str(scan.id), "reason": result.reason}
        )
    if not inline and result.passed:
        from ayin.orchestrator.tasks import run_job  # noqa: PLC0415

        jobs = db.execute(
            select(ConnectorJob).where(ConnectorJob.scan_id == scan.id)
        ).scalars().all()
        for job in jobs:
            run_job.delay(str(job.id))
    db.expire_all()
    return _scan_out(db, db.get(Scan, scan.id))


@router.get("", response_model=list[ScanOut])
def list_scans(
    user: CurrentUser, db: DbDep, subject: Subject = Depends(get_my_subject)
):
    record_data_access(
        db, actor=user_actor(user.id), subject_id=subject.id,
        resource="scans", purpose="self-view",
    )
    db.commit()
    scans = db.execute(
        select(Scan).where(Scan.subject_id == subject.id).order_by(Scan.created_at.desc())
    ).scalars().all()
    return [_scan_out(db, s) for s in scans]


@router.get("/{scan_id}", response_model=ScanOut)
def get_scan(
    scan_id: uuid.UUID, user: CurrentUser, db: DbDep,
    subject: Subject = Depends(get_my_subject),
):
    scan = _owned_scan(db, subject, scan_id)
    record_data_access(
        db, actor=user_actor(user.id), subject_id=subject.id,
        resource="scans", purpose="self-view", scan_id=scan.id,
    )
    db.commit()
    return _scan_out(db, scan)


@router.get("/{scan_id}/findings", response_model=FindingsPage)
def get_findings(
    scan_id: uuid.UUID,
    request: Request,
    user: CurrentUser,
    db: DbDep,
    settings: SettingsDep,
    subject: Subject = Depends(get_my_subject),
):
    """Findings for one scan — visibility-filtered (unverified seeds never
    surface results), credential details locked behind step-up."""
    scan = _owned_scan(db, subject, scan_id)

    step_up_token = request.headers.get("X-Ayin-Step-Up")
    elevated = (
        decode_token(settings, step_up_token, required_scope=SCOPE_STEP_UP) == user.id
        if step_up_token
        else False
    )

    rows = db.execute(
        visible_findings_query(subject.id).where(Finding.scan_id == scan.id)
    ).scalars().all()

    locked = 0
    out: list[FindingOut] = []
    for f in rows:
        is_credential = f.category == FindingCategory.CREDENTIAL
        if is_credential and not elevated:
            locked += 1
            out.append(
                FindingOut(
                    id=f.id,
                    category=f.category.value,
                    sensitivity=f.sensitivity.value,
                    source=f.source,
                    source_name=f.source_name,
                    source_url=None,
                    captured_at=f.captured_at,
                    confidence=f.confidence,
                    exploitability=f.exploitability,
                    summary="Credential exposure found — re-enter your password to view "
                    "the details.",
                    payload={},
                    identifier_id=f.identifier_id,
                    state=f.state.value,
                    step_up_required=True,
                )
            )
        else:
            out.append(
                FindingOut(
                    id=f.id,
                    category=f.category.value,
                    sensitivity=f.sensitivity.value,
                    source=f.source,
                    source_name=f.source_name,
                    source_url=f.source_url,
                    captured_at=f.captured_at,
                    confidence=f.confidence,
                    exploitability=f.exploitability,
                    summary=f.summary,
                    payload=f.payload,
                    identifier_id=f.identifier_id,
                    state=f.state.value,
                    step_up_required=False,
                )
            )

    resource = "findings.credential" if elevated else "findings"
    record_data_access(
        db, actor=user_actor(user.id), subject_id=subject.id, resource=resource,
        purpose="self-view", scan_id=scan.id, detail={"count": len(out)},
    )
    db.commit()
    return FindingsPage(scan_id=scan.id, findings=out, locked_credential_findings=locked)
