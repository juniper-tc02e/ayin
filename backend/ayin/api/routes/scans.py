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
from ayin.api.schemas import (
    ActivityEventOut,
    ActivityOut,
    AppealIn,
    CategorySummaryOut,
    ChecklistItemOut,
    ChecklistOut,
    FindingOut,
    FindingsPage,
    JobOut,
    MessageOut,
    NarrativeClaimOut,
    ReportNarrativeOut,
    ReportOut,
    ScanOut,
    ScanProgress,
    ScanStartIn,
    ScoreContributorOut,
    ScoreOut,
)
from ayin.auth.tokens import SCOPE_STEP_UP, decode_token
from ayin.connectors import ConnectorRegistry
from ayin.connectors import registry as global_registry
from ayin.models import AuditRecord, ConnectorJob, Finding, Scan, Score, Subject
from ayin.models.enums import ActorType, FindingCategory, JobStatus
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
    ("no_consent", status.HTTP_403_FORBIDDEN),
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
    body: ScanStartIn | None = None,
    user=Depends(require_tos),  # ToS/AUP gate (FR-AUTH-2) on the way in
    registry: ConnectorRegistry = Depends(get_registry),
    vault: VaultProtocol = Depends(get_vault),
):
    # Default: scan yourself (T0). A subject_id is the consented-third-party
    # path — we hand the target to the engine, whose consent gate REFUSES it
    # unless this requester holds a live grant. Loading the row authorizes
    # nothing on its own.
    target: Subject | None = None
    if body is not None and body.subject_id is not None:
        target = db.get(Subject, body.subject_id)
        if target is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Subject not found.")
    inline = settings.scan_execution == "inline"
    scan, result = engine.start_scan(
        db, requester=user, settings=settings, registry=registry, vault=vault,
        inline=inline, subject=target,
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
    fresh = db.get(Scan, scan.id)
    assert fresh is not None  # just created in this request
    return _scan_out(db, fresh)


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


@router.post("/{scan_id}/appeal", response_model=MessageOut)
def appeal_scan(
    scan_id: uuid.UUID,
    body: AppealIn,
    user: CurrentUser,
    db: DbDep,
    subject: Subject = Depends(get_my_subject),
):
    """False-positive appeal for a refused/held scan (FR-SCAN-5): opens a
    human-review case. Audited."""
    from ayin.models.enums import ScanStatus  # noqa: PLC0415
    from ayin.safety.abuse import file_appeal  # noqa: PLC0415
    from ayin.safety.audit import record_scan_event  # noqa: PLC0415

    scan = _owned_scan(db, subject, scan_id)
    if scan.status not in (ScanStatus.FAILED, ScanStatus.HELD):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Only refused or held scans can be appealed."
        )
    try:
        file_appeal(db, scan, body.message)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    record_scan_event(
        db, actor=user_actor(user.id), event_type="scan.appeal_submitted",
        scan_id=scan.id, subject_id=subject.id,
    )
    db.commit()
    return MessageOut(
        message="Appeal submitted — a human will review this scan decision."
    )


@router.get("/{scan_id}/score", response_model=ScoreOut)
def get_score(
    scan_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    subject: Subject = Depends(get_my_subject),
):
    """The Exposure Score: 0-100 + sub-scores + every contributing finding.
    Measures exposure of data only — never the person (CLAUDE.md #2)."""
    from ayin.scoring.engine import verdict as _verdict  # noqa: PLC0415

    scan = _owned_scan(db, subject, scan_id)
    score = db.execute(select(Score).where(Score.scan_id == scan.id)).scalar_one_or_none()
    if score is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No score yet — the scan may still be running."
        )
    record_data_access(
        db, actor=user_actor(user.id), subject_id=subject.id,
        resource="score", purpose="self-view", scan_id=scan.id,
    )
    db.commit()
    return ScoreOut(
        scan_id=scan.id,
        overall=score.overall,
        subscores=score.subscores,
        rubric_version=score.rubric_version,
        computed_at=score.computed_at,
        verdict=_verdict(score.overall),
        contributing=[ScoreContributorOut(**c) for c in score.contributing],
    )


@router.get("/{scan_id}/report", response_model=ReportOut)
def get_report(
    scan_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    settings: SettingsDep,
    subject: Subject = Depends(get_my_subject),
):
    """The grounded report narrative (B1): score + plain-language verdict,
    per-category summaries, and "top fixes" — every statement citing the
    finding id(s) it rests on. Written by Qwen when the LLM is enabled,
    deterministic templates otherwise; the citation guard rejects any draft
    referencing a finding that doesn't exist (CLAUDE.md #5)."""
    from ayin.report import get_or_generate_narrative  # noqa: PLC0415

    scan = _owned_scan(db, subject, scan_id)
    score = db.execute(select(Score).where(Score.scan_id == scan.id)).scalar_one_or_none()
    if score is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No report yet — the scan may still be running."
        )
    narrative, meta = get_or_generate_narrative(db, scan, score, settings)
    record_data_access(
        db, actor=user_actor(user.id), subject_id=subject.id,
        resource="report", purpose="self-view", scan_id=scan.id,
    )
    db.commit()
    return ReportOut(
        scan_id=scan.id,
        overall=score.overall,
        subscores=score.subscores,
        rubric_version=score.rubric_version,
        computed_at=score.computed_at,
        narrative=ReportNarrativeOut(
            verdict=narrative.get("verdict", ""),
            claims=[NarrativeClaimOut(**c) for c in narrative.get("claims", [])],
            category_summaries=[
                CategorySummaryOut(**c) for c in narrative.get("category_summaries", [])
            ],
            top_fixes=[NarrativeClaimOut(**c) for c in narrative.get("top_fixes", [])],
            generated_by="qwen" if meta.get("used_llm") else "template",
            model=meta.get("model"),
            generated_at=meta.get("generated_at"),
        ),
    )


@router.get("/{scan_id}/checklist", response_model=ChecklistOut)
def get_checklist(
    scan_id: uuid.UUID,
    request: Request,
    user: CurrentUser,
    db: DbDep,
    settings: SettingsDep,
    subject: Subject = Depends(get_my_subject),
):
    """Read-only hardening checklist with honest expected score deltas
    (FR-REM-3 lite). Credential items stay generic without step-up. When the
    LLM is enabled, items also carry citation-guarded personalized steps
    (B3) — generated once from the non-elevated checklist and cached as
    RemediationTask rows; the playbook steps remain the floor."""
    from ayin.remediation import build_checklist  # noqa: PLC0415
    from ayin.remediation.llm_guidance import ensure_llm_guidance  # noqa: PLC0415

    scan = _owned_scan(db, subject, scan_id)
    step_up_token = request.headers.get("X-Ayin-Step-Up")
    elevated = (
        decode_token(settings, step_up_token, required_scope=SCOPE_STEP_UP) == user.id
        if step_up_token
        else False
    )
    current_overall, items = build_checklist(db, scan, elevated=elevated)
    guidance = ensure_llm_guidance(db, scan, settings)
    record_data_access(
        db, actor=user_actor(user.id), subject_id=subject.id,
        resource="checklist", purpose="self-view", scan_id=scan.id,
    )
    db.commit()
    return ChecklistOut(
        scan_id=scan.id,
        current_overall=current_overall,
        items=[
            ChecklistItemOut(
                finding_id=uuid.UUID(i.finding_id),
                category=i.category,
                sensitivity=i.sensitivity,
                title=i.title,
                steps=i.steps,
                expected_score_delta=i.expected_score_delta,
                effort=i.effort,
                personalized_steps=guidance.get(i.finding_id),
            )
            for i in items
        ],
    )


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
                    match_status=f.match_status.value,
                    match_confidence=f.match_confidence,
                    corroboration_count=f.corroboration_count,
                    merged_sources=[],  # source list may leak breach names — locked too
                    conflicts=[],
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
                    match_status=f.match_status.value,
                    match_confidence=f.match_confidence,
                    corroboration_count=f.corroboration_count,
                    merged_sources=f.merged_sources or [],
                    conflicts=(f.resolution or {}).get("conflicts", []),
                    llm_opinion=(f.resolution or {}).get("llm_opinion"),
                )
            )

    resource = "findings.credential" if elevated else "findings"
    record_data_access(
        db, actor=user_actor(user.id), subject_id=subject.id, resource=resource,
        purpose="self-view", scan_id=scan.id, detail={"count": len(out)},
    )
    db.commit()
    return FindingsPage(scan_id=scan.id, findings=out, locked_credential_findings=locked)


# Activity-trail allowlist: event type → detail fields that may leave the
# audit table. Double allowlist by design — an event type not listed here is
# never served, and a detail field not listed here is dropped even on a
# listed event, so new audit detail stays private by default. Deliberately
# excluded: data.access (the user's own report reads would flood the feed),
# cost_usd (internal cost telemetry), raw error/exception text (can embed
# internal endpoints), invented_finding_ids (model-fabricated strings — the
# guard_ok/unsourced counts tell that story), and the hash-chain fields.
_ACTIVITY_EVENTS: dict[str, frozenset[str]] = {
    # lifecycle
    "scan.created": frozenset(),
    "scan.gated": frozenset(),
    "scan.refused": frozenset({"reason"}),
    "scan.held": frozenset({"reason"}),
    "scan.started": frozenset({"connectors", "seed_kinds"}),
    "scan.completed": frozenset({"findings", "failed_connectors"}),
    # connectors
    "scan.connector_finished": frozenset({"connector", "findings", "attempt"}),
    "scan.connector_retry": frozenset({"connector", "attempt"}),
    "scan.connector_failed": frozenset({"connector", "attempt"}),
    # agentic planner (B2) — reasoning is the model's own words: serve it as
    # text for the user's own scan, but render it as untrusted content
    "scan.planner_decision": frozenset(
        {"connector", "seed_ref", "reasoning", "model", "step"}
    ),
    "scan.planner_rejected": frozenset({"connector", "reason", "reasoning", "model"}),
    "scan.planner_fallback": frozenset(),
    "scan.planner_done": frozenset(
        {"reason", "steps_taken", "invalid_proposals", "connectors_remaining"}
    ),
    # resolution + scoring
    "scan.resolved": frozenset(
        {"groups", "duplicates_collapsed", "conflicts_flagged",
         "auto_matched", "possible", "user_decisions_kept"}
    ),
    "scan.scored": frozenset({"overall", "rubric_version", "findings_counted"}),
    # LLM generation steps (B1/B3/B4)
    "scan.narrative_generated": frozenset(
        {"used_llm", "model", "guard_ok", "tokens",
         "findings_in_context", "unsourced_claim_count"}
    ),
    "scan.remediation_generated": frozenset(
        {"used_llm", "model", "guard_ok", "tokens",
         "items_generated", "items_requested"}
    ),
    "scan.er_assist_generated": frozenset(
        {"used_llm", "model", "guard_ok", "tokens",
         "candidates", "judgments", "verdict_counts"}
    ),
    "scan.narrative_generation_failed": frozenset(),
    "scan.remediation_generation_failed": frozenset(),
    "scan.er_assist_generation_failed": frozenset(),
}


def _actor_label(rec: AuditRecord) -> str:
    """'user' for the requester's own actions, 'system:<component>' for
    pipeline steps. Never an internal actor id."""
    if rec.actor_type == ActorType.SYSTEM:
        return f"system:{rec.actor_id}" if rec.actor_id else "system"
    return rec.actor_type.value


@router.get("/{scan_id}/activity", response_model=ActivityOut)
def get_activity(
    scan_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    subject: Subject = Depends(get_my_subject),
):
    """The scan's activity trail (E1) — planner decisions with the model's
    audited reasoning, pipeline lifecycle, and LLM generation/guard events,
    served straight from the immutable audit log so the UI shows what
    actually happened, not a reconstruction. Reading it is itself a
    subject-data access and is audited like any other."""
    scan = _owned_scan(db, subject, scan_id)
    rows = db.execute(
        select(AuditRecord)
        .where(
            AuditRecord.scan_id == scan.id,
            # defense in depth on top of _owned_scan
            AuditRecord.subject_id == subject.id,
            AuditRecord.event_type.in_(list(_ACTIVITY_EVENTS)),
        )
        .order_by(AuditRecord.id.asc())
    ).scalars().all()
    record_data_access(
        db, actor=user_actor(user.id), subject_id=subject.id,
        resource="activity", purpose="self-view", scan_id=scan.id,
        detail={"count": len(rows)},
    )
    db.commit()
    return ActivityOut(
        scan_id=scan.id,
        events=[
            ActivityEventOut(
                id=r.id,
                occurred_at=r.occurred_at,
                event_type=r.event_type,
                actor=_actor_label(r),
                detail={
                    k: v
                    for k, v in (r.detail or {}).items()
                    if k in _ACTIVITY_EVENTS[r.event_type]
                },
            )
            for r in rows
        ],
    )
