"""Pure orchestration functions over Postgres-backed scan state (M1-1).

Safety properties:
- Gates run BEFORE any connector is dispatched and can refuse/hold the scan
  (safety in the critical path — CLAUDE.md, PRD §10.1).
- Only seeds the user is entitled to scan fan out: verified challengeable
  identifiers (email/phone) + auxiliary kinds (username/name/city) riding
  along a verified anchor. An unverified email/phone is NEVER scanned.
- Every transition writes an audit record; findings persist with provenance;
  sensitive payloads only ever travel through the vault interface.
- Resumable: jobs are idempotent (findings upsert on (scan_id, dedupe_key));
  ``resume_stalled`` re-drives anything a dead worker left behind.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ayin.config import Settings
from ayin.connectors import (
    Connector,
    ConnectorAuthError,
    ConnectorContractViolation,
    ConnectorPermanentError,
    ConnectorRegistry,
    NormalizedFinding,
    SeedQuery,
)
from ayin.models import ConnectorJob, Finding, Identifier, Scan, Subject, User
from ayin.models.enums import (
    IdentifierKind,
    JobStatus,
    ScanStatus,
    VerificationState,
)
from ayin.safety import limits
from ayin.safety.audit import Actor, record_scan_event, system_actor, user_actor
from ayin.services.normalize import CHALLENGEABLE_KINDS
from ayin.vault import VaultProtocol

log = logging.getLogger("ayin.orchestrator")

JOB_MAX_ATTEMPTS = 3


class GateDecision(str, Enum):
    PASS = "pass"  # noqa: S105 — gate decision, not a credential
    REFUSE = "refuse"
    HOLD = "hold"


@dataclass(frozen=True)
class GateResult:
    decision: GateDecision
    reason: str = ""

    @property
    def passed(self) -> bool:
        return self.decision == GateDecision.PASS


# ── Seed selection ───────────────────────────────────────────────────


def eligible_seed_identifiers(db: Session, subject_id: uuid.UUID) -> list[Identifier]:
    """Seeds allowed to fan out: verified challengeable identifiers, plus
    auxiliary kinds (which cannot be challenge-verified). An UNVERIFIED
    email/phone is excluded — control not yet proven (FR-AUTH-1).
    Identifiers on the public exclusion list NEVER fan out (FR-TS-3)."""
    from ayin.safety.exclusion import split_excluded  # noqa: PLC0415

    rows = db.execute(
        select(Identifier).where(Identifier.subject_id == subject_id)
    ).scalars()
    out = []
    for ident in rows:
        if ident.kind in CHALLENGEABLE_KINDS:
            if ident.verification_state == VerificationState.VERIFIED:
                out.append(ident)
        else:
            out.append(ident)
    allowed, excluded = split_excluded(db, out)
    if excluded:
        log.info("seed selection: %d identifier(s) suppressed by exclusion list", len(excluded))
    return allowed


def has_verified_anchor(identifiers: list[Identifier]) -> bool:
    return any(
        i.kind in CHALLENGEABLE_KINDS and i.verification_state == VerificationState.VERIFIED
        for i in identifiers
    )


def build_seed_queries(
    identifiers: list[Identifier], connector_cls: type[Connector]
) -> list[SeedQuery]:
    """Seeds a given connector can use, with minimal context (city alongside
    full_name for sources that need it)."""
    city = next(
        (i.value_normalized for i in identifiers if i.kind == IdentifierKind.CITY), None
    )
    seeds = []
    for ident in identifiers:
        if ident.kind not in connector_cls.supported_kinds:
            continue
        context: dict[str, str] = {}
        if ident.kind == IdentifierKind.FULL_NAME and city:
            context["city"] = city
        seeds.append(
            SeedQuery(
                kind=ident.kind,
                value=ident.value_normalized,
                identifier_id=ident.id,
                context=context,
            )
        )
    return seeds


# ── Gates (safety in the critical path) ──────────────────────────────


def run_gates(db: Session, scan: Scan, settings: Settings) -> GateResult:
    subject = db.get(Subject, scan.subject_id)
    if subject is None:
        return GateResult(GateDecision.REFUSE, "subject_missing")
    if subject.exclusion_state == "excluded":
        # FR-TS-3: an excluded identity is never scanned.
        return GateResult(GateDecision.REFUSE, "subject_excluded")

    identifiers = eligible_seed_identifiers(db, scan.subject_id)
    if not has_verified_anchor(identifiers):
        # Distinguish "never verified" from "this identity excluded itself".
        # Exclusion purges the seed rows, so check (a) any surviving seed
        # rows that are hash-excluded and (b) the account email itself.
        from ayin.safety.exclusion import excluded_hashes, split_excluded  # noqa: PLC0415
        from ayin.safety.hashing import identifier_hash  # noqa: PLC0415

        all_rows = list(db.execute(
            select(Identifier).where(Identifier.subject_id == scan.subject_id)
        ).scalars())
        _, excluded = split_excluded(db, all_rows)
        anchor_excluded = any(
            i.kind in CHALLENGEABLE_KINDS
            and i.verification_state == VerificationState.VERIFIED
            for i in excluded
        )
        if not anchor_excluded:
            requester = db.get(User, scan.requester_user_id)
            if requester is not None:
                account_hash = identifier_hash(IdentifierKind.EMAIL, requester.email)
                anchor_excluded = bool(excluded_hashes(db, [account_hash]))
        if anchor_excluded:
            return GateResult(
                GateDecision.REFUSE,
                "subject_excluded: this identity asked to be excluded from Ayin "
                "scans — that request is honored for everyone, including you.",
            )
        return GateResult(
            GateDecision.REFUSE,
            "no_verified_anchor: verify control of at least one email or phone "
            "before scanning",
        )

    # Abuse heuristics (FR-SCAN-5 / FR-TS-2) — can refuse or hold BEFORE
    # any connector touches a source. Runs before rate limiting so a held
    # scan doesn't also burn the user's quota messaging.
    from ayin.safety.abuse import evaluate_scan  # noqa: PLC0415

    abuse = evaluate_scan(db, scan, identifiers)
    if abuse.decision == "refuse":
        return GateResult(GateDecision.REFUSE, abuse.public_reason)
    if abuse.decision == "hold":
        return GateResult(GateDecision.HOLD, abuse.public_reason)

    limit = limits.check_scan_allowed(
        db, scan.requester_user_id, settings, exclude_scan_id=scan.id
    )
    if not limit.allowed:
        return GateResult(GateDecision.REFUSE, f"rate_limited: {limit.message}")

    return GateResult(GateDecision.PASS)


# ── Lifecycle ────────────────────────────────────────────────────────


def _transition(
    db: Session, scan: Scan, status: ScanStatus, *, actor: Actor, event: str,
    detail: dict | None = None,
) -> None:
    scan.status = status
    record_scan_event(
        db, actor=actor, event_type=event, scan_id=scan.id,
        subject_id=scan.subject_id, detail=detail or {},
    )


def create_scan(db: Session, *, requester: User, settings: Settings) -> Scan:
    """Create the scan row (queued) + audit. Gates run in ``gate_scan``."""
    subject = db.execute(
        select(Subject).where(Subject.owner_user_id == requester.id)
    ).scalar_one()
    scan = Scan(requester_user_id=requester.id, subject_id=subject.id)
    db.add(scan)
    db.flush()
    record_scan_event(
        db, actor=user_actor(requester.id), event_type="scan.created",
        scan_id=scan.id, subject_id=subject.id,
    )
    from ayin.analytics import track  # noqa: PLC0415

    track(db, "scan_started", user_id=requester.id, scan_id=scan.id)
    db.commit()
    return scan


def gate_scan(db: Session, scan: Scan, settings: Settings) -> GateResult:
    """queued → gated → (refused | held | dispatch-ready). Commits."""
    actor = system_actor("orchestrator")
    _transition(db, scan, ScanStatus.GATED, actor=actor, event="scan.gated")
    result = run_gates(db, scan, settings)
    from ayin.analytics import track  # noqa: PLC0415

    if result.decision == GateDecision.REFUSE:
        scan.error = result.reason
        _transition(
            db, scan, ScanStatus.FAILED, actor=actor, event="scan.refused",
            detail={"reason": result.reason},
        )
        track(
            db, "scan_refused", user_id=scan.requester_user_id, scan_id=scan.id,
            properties={"reason_code": result.reason.split(":")[0][:40]},
        )
    elif result.decision == GateDecision.HOLD:
        scan.error = result.reason
        _transition(
            db, scan, ScanStatus.HELD, actor=actor, event="scan.held",
            detail={"reason": result.reason},
        )
        track(
            db, "scan_held", user_id=scan.requester_user_id, scan_id=scan.id,
            properties={"reason_code": result.reason.split(":")[0][:40]},
        )
    db.commit()
    return result


def dispatch_scan(db: Session, scan: Scan, registry: ConnectorRegistry) -> list[ConnectorJob]:
    """Fan out: one ConnectorJob per enabled connector that supports ≥1 seed
    kind. gated → running. Commits."""
    identifiers = eligible_seed_identifiers(db, scan.subject_id)
    seed_kinds = {i.kind for i in identifiers}
    jobs: list[ConnectorJob] = []
    for cid in registry.enabled_ids():
        cls = registry.get_class(cid)
        if not (cls.supported_kinds & seed_kinds):
            continue
        job = ConnectorJob(scan_id=scan.id, connector_id=cid)
        db.add(job)
        jobs.append(job)
    scan.source_set = [j.connector_id for j in jobs]
    scan.started_at = datetime.now(timezone.utc)
    _transition(
        db, scan, ScanStatus.RUNNING, actor=system_actor("orchestrator"),
        event="scan.started",
        detail={"connectors": scan.source_set, "seed_kinds": sorted(k.value for k in seed_kinds)},
    )
    db.flush()
    db.commit()
    return jobs


def run_connector_job(
    db: Session, job_id: uuid.UUID, registry: ConnectorRegistry, vault: VaultProtocol,
) -> JobStatus:
    """Execute one connector job idempotently. Commits. Returns final status."""
    job = db.execute(
        select(ConnectorJob).where(ConnectorJob.id == job_id).with_for_update(skip_locked=True)
    ).scalar_one_or_none()
    if job is None or job.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.RUNNING):
        return job.status if job else JobStatus.FAILED

    scan = db.get(Scan, job.scan_id)
    if scan is None:  # FK guarantees this; satisfy the type system + fail loudly
        raise RuntimeError(f"connector job {job.id} has no scan {job.scan_id}")
    job.status = JobStatus.RUNNING
    job.attempts += 1
    job.started_at = datetime.now(timezone.utc)
    db.commit()  # claim is visible to other workers

    actor = system_actor(f"connector:{job.connector_id}")
    try:
        connector = registry.get_class(job.connector_id)()
        identifiers = eligible_seed_identifiers(db, scan.subject_id)
        seeds = build_seed_queries(identifiers, type(connector))
        findings: list[NormalizedFinding] = []
        cost = 0.0
        for seed in seeds:
            result = connector.run(seed)
            findings.extend(result.findings)
            cost += result.telemetry.cost_usd
        persisted = _persist_findings(db, scan, findings, vault)
        job.status = JobStatus.DONE
        job.findings_count = persisted
        job.cost_usd = cost
        job.error = None
        job.finished_at = datetime.now(timezone.utc)
        record_scan_event(
            db, actor=actor, event_type="scan.connector_finished", scan_id=scan.id,
            subject_id=scan.subject_id,
            detail={"connector": job.connector_id, "findings": persisted,
                    "cost_usd": round(cost, 6), "attempt": job.attempts},
        )
    except (ConnectorAuthError, ConnectorPermanentError, ConnectorContractViolation) as exc:
        _fail_job(db, scan, job, exc, retryable=False)
    except Exception as exc:  # transient/rate-limited/unexpected → bounded retry
        _fail_job(db, scan, job, exc, retryable=job.attempts < JOB_MAX_ATTEMPTS)
    db.commit()
    return job.status


def _fail_job(db: Session, scan: Scan, job: ConnectorJob, exc: Exception, *, retryable: bool):
    job.error = f"{type(exc).__name__}: {exc}"
    if retryable:
        job.status = JobStatus.QUEUED  # picked up again by worker/resume
        event = "scan.connector_retry"
    else:
        job.status = JobStatus.FAILED
        job.finished_at = datetime.now(timezone.utc)
        event = "scan.connector_failed"
    record_scan_event(
        db, actor=system_actor(f"connector:{job.connector_id}"), event_type=event,
        scan_id=scan.id, subject_id=scan.subject_id,
        detail={"connector": job.connector_id, "error": job.error, "attempt": job.attempts},
    )


def _persist_findings(
    db: Session, scan: Scan, findings: list[NormalizedFinding], vault: VaultProtocol
) -> int:
    """Upsert findings (idempotent on (scan_id, dedupe_key)); sensitive
    payloads go to the vault only."""
    count = 0
    for f in findings:
        vault_ref = None
        if f.sensitive_payload:
            vault_ref = vault.put(
                db, subject_id=scan.subject_id, kind=f"finding.{f.category.value}",
                payload=f.sensitive_payload,
            )
        stmt = (
            pg_insert(Finding)
            .values(
                id=uuid.uuid4(),
                scan_id=scan.id,
                subject_id=scan.subject_id,
                identifier_id=f.identifier_id,
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
                vault_ref=vault_ref,
                dedupe_key=f.dedupe_key,
            )
            .on_conflict_do_nothing(index_elements=["scan_id", "dedupe_key"])
            .returning(Finding.id)
        )
        inserted = db.execute(stmt).fetchall()
        count += len(inserted)
    db.flush()
    return count


def finalize_scan_if_complete(db: Session, scan_id: uuid.UUID) -> bool:
    """When all jobs are terminal: running → resolving → scoring → done.
    Resolution/scoring are M2 hooks (no-ops in M1). Partial results stand —
    a failed connector doesn't void the others. Commits. True if finalized."""
    scan = db.get(Scan, scan_id)
    if scan is None or scan.status != ScanStatus.RUNNING:
        return False
    jobs = db.execute(
        select(ConnectorJob).where(ConnectorJob.scan_id == scan_id)
    ).scalars().all()
    if any(j.status in (JobStatus.QUEUED, JobStatus.RUNNING) for j in jobs):
        return False

    actor = system_actor("orchestrator")
    _transition(db, scan, ScanStatus.RESOLVING, actor=actor, event="scan.resolving")
    from ayin.resolution import resolve_scan  # noqa: PLC0415 — avoid import cycle

    resolve_scan(db, scan)
    _transition(db, scan, ScanStatus.SCORING, actor=actor, event="scan.scoring")
    from ayin.scoring import compute_score  # noqa: PLC0415 — avoid import cycle

    score = compute_score(db, scan)
    # REPORT step (B1): pre-generate the grounded narrative so the report is
    # ready the moment the user opens it. Best-effort — the LLM is an assist,
    # never load-bearing (ADR-0003); any failure falls through to lazy
    # generation at the report route.
    try:
        from ayin.report import get_or_generate_narrative  # noqa: PLC0415

        get_or_generate_narrative(db, scan, score)
    except Exception:
        log.warning("narrative pre-generation failed — report will generate lazily",
                    exc_info=True)
    failed = [j.connector_id for j in jobs if j.status == JobStatus.FAILED]
    if failed:
        scan.error = f"partial: connectors failed: {', '.join(sorted(failed))}"
    scan.finished_at = datetime.now(timezone.utc)
    _transition(
        db, scan, ScanStatus.DONE, actor=actor, event="scan.completed",
        detail={
            "findings": sum(j.findings_count for j in jobs),
            "cost_usd": round(sum(j.cost_usd for j in jobs), 6),
            "failed_connectors": sorted(failed),
        },
    )
    from ayin.analytics import track  # noqa: PLC0415

    duration = (
        (scan.finished_at - scan.started_at).total_seconds() if scan.started_at else None
    )
    track(
        db, "scan_completed", user_id=scan.requester_user_id, scan_id=scan.id,
        properties={
            "findings_count": sum(j.findings_count for j in jobs),
            "connectors": len(jobs),
            "duration_seconds": round(duration, 1) if duration is not None else None,
        },
    )
    db.commit()
    return True


# ── Drivers ──────────────────────────────────────────────────────────


def start_scan(
    db: Session, *, requester: User, settings: Settings, registry: ConnectorRegistry,
    vault: VaultProtocol, inline: bool,
) -> tuple[Scan, GateResult]:
    """create → gate → (dispatch [+ inline-run]). The API calls this."""
    scan = create_scan(db, requester=requester, settings=settings)
    result = gate_scan(db, scan, settings)
    if result.passed:
        dispatch_scan(db, scan, registry)
        if inline:
            run_scan_inline(db, scan.id, registry, vault, settings)
    return scan, result


def run_scan_inline(
    db: Session, scan_id: uuid.UUID, registry: ConnectorRegistry, vault: VaultProtocol,
    settings: Settings | None = None,
) -> None:
    """Synchronous driver (dev default + tests). Celery is the async driver.

    When the LLM is enabled, a Qwen planner proposes the dispatch order and
    reacts to intermediate results (B2, ADR-0003). The deterministic sweep
    below is both the no-LLM path and the planner's safety net — full source
    coverage is a product guarantee, not a model decision. (The Celery driver
    keeps deterministic queue order; the planner applies to inline runs.)
    """
    from ayin.llm import get_llm_client  # noqa: PLC0415 — avoid import cycle

    client = get_llm_client(settings)
    if client is not None:
        try:
            _run_scan_planned(db, scan_id, registry, vault, client)
        except Exception as exc:  # the LLM is never load-bearing (ADR-0003)
            scan = db.get(Scan, scan_id)
            record_scan_event(
                db, actor=system_actor("planner"), event_type="scan.planner_fallback",
                scan_id=scan_id, subject_id=scan.subject_id if scan else None,
                detail={"reason": f"{type(exc).__name__}: {exc}"},
            )
            db.commit()
            log.warning("scan planner failed — deterministic dispatch takes over: %s", exc)
    for _ in range(JOB_MAX_ATTEMPTS + 1):
        job_ids = db.execute(
            select(ConnectorJob.id).where(
                ConnectorJob.scan_id == scan_id, ConnectorJob.status == JobStatus.QUEUED
            )
        ).scalars().all()
        if not job_ids:
            break
        for jid in job_ids:
            run_connector_job(db, jid, registry, vault)
    finalize_scan_if_complete(db, scan_id)


def _job_summary(db: Session, scan: Scan, connector_id: str, status: JobStatus) -> dict:
    """Non-sensitive dispatch outcome fed back to the planner: counts by
    category only — never finding payloads or identifier values."""
    from sqlalchemy import func  # noqa: PLC0415

    rows = db.execute(
        select(Finding.category, func.count())
        .where(Finding.scan_id == scan.id, Finding.source == connector_id)
        .group_by(Finding.category)
    ).all()
    return {
        "connector": connector_id,
        "status": status.value,
        "findings_by_category": {
            (cat.value if hasattr(cat, "value") else str(cat)): int(n) for cat, n in rows
        },
    }


def _run_scan_planned(
    db: Session, scan_id: uuid.UUID, registry: ConnectorRegistry, vault: VaultProtocol,
    client,
) -> None:
    """One planner episode over the scan's PRE-GATED job set (B2).

    The planner proposes; this function validates each proposal against the
    jobs that gating already approved and refuses anything else — the LLM
    cannot widen scope or bypass a gate (CLAUDE.md #7). Every accepted
    decision and every refusal is audited with the model's reasoning.
    """
    from ayin.llm.planner import ConnectorTool, ScanPlanner  # noqa: PLC0415

    scan = db.get(Scan, scan_id)
    if scan is None or scan.status != ScanStatus.RUNNING:
        return
    jobs = {
        j.connector_id: j
        for j in db.execute(
            select(ConnectorJob).where(ConnectorJob.scan_id == scan_id)
        ).scalars()
    }
    pending = {cid for cid, j in jobs.items() if j.status == JobStatus.QUEUED}
    if not pending:
        return
    identifiers = eligible_seed_identifiers(db, scan.subject_id)
    seed_kinds = sorted({i.kind.value for i in identifiers})
    tools = [ConnectorTool.from_connector(registry.get_class(cid)) for cid in sorted(pending)]
    planner = ScanPlanner(client, tools, seed_kinds=seed_kinds)
    actor = system_actor("planner")

    while pending:
        decision = planner.propose()  # raises LLMError → caller falls back
        if decision is None:
            break
        if decision.connector_id not in pending:
            # Outside the pre-gated set (already ran, or never approved) —
            # refused, audited, never executed.
            record_scan_event(
                db, actor=actor, event_type="scan.planner_rejected",
                scan_id=scan.id, subject_id=scan.subject_id,
                detail={"connector": decision.connector_id,
                        "reason": "not in the pre-gated pending job set",
                        "reasoning": decision.reasoning, "model": client.model},
            )
            db.commit()
            planner.reject(
                f"connector {decision.connector_id!r} is not available for this scan"
            )
            continue
        record_scan_event(
            db, actor=actor, event_type="scan.planner_decision",
            scan_id=scan.id, subject_id=scan.subject_id,
            detail={"connector": decision.connector_id, "seed_ref": decision.seed_ref,
                    "reasoning": decision.reasoning, "model": client.model,
                    "step": planner.steps_taken},
        )
        db.commit()
        status = run_connector_job(db, jobs[decision.connector_id].id, registry, vault)
        if status != JobStatus.QUEUED:  # QUEUED = retryable failure, stays pending
            pending.discard(decision.connector_id)
        planner.observe(_job_summary(db, scan, decision.connector_id, status))


def resume_stalled(
    db: Session, *, settings: Settings, registry: ConnectorRegistry, vault: VaultProtocol,
    stale_after_seconds: int | None = None,
) -> dict:
    """Recover work a dead worker left behind (M1-1 acceptance: a scan
    survives a worker restart mid-run).

    - RUNNING jobs older than the staleness window → back to QUEUED
    - QUEUED jobs of RUNNING scans → run
    - GATED scans (gating crashed) → re-gate + dispatch
    - then finalize anything now complete
    """
    stale_after = stale_after_seconds or settings.job_stale_after_seconds
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after)
    summary = {"requeued_jobs": 0, "ran_jobs": 0, "regated_scans": 0, "finalized_scans": 0}

    stale = db.execute(
        select(ConnectorJob).where(
            ConnectorJob.status == JobStatus.RUNNING, ConnectorJob.started_at < cutoff
        )
    ).scalars().all()
    for job in stale:
        job.status = JobStatus.QUEUED
        job.error = (job.error or "") + " [requeued: worker presumed dead]"
        summary["requeued_jobs"] += 1
    db.commit()

    gated = db.execute(select(Scan).where(Scan.status == ScanStatus.GATED)).scalars().all()
    for scan in gated:
        summary["regated_scans"] += 1
        result = gate_scan(db, scan, settings)
        if result.passed:
            dispatch_scan(db, scan, registry)

    running = db.execute(select(Scan).where(Scan.status == ScanStatus.RUNNING)).scalars().all()
    for scan in running:
        job_ids = db.execute(
            select(ConnectorJob.id).where(
                ConnectorJob.scan_id == scan.id, ConnectorJob.status == JobStatus.QUEUED
            )
        ).scalars().all()
        for jid in job_ids:
            run_connector_job(db, jid, registry, vault)
            summary["ran_jobs"] += 1
        if finalize_scan_if_complete(db, scan.id):
            summary["finalized_scans"] += 1
    return summary
