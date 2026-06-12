"""B3 persistence: LLM-personalized checklist guidance, cached as
RemediationTask rows (the data model's home for per-finding remediation —
PRD §10.4; rows stay status=SUGGESTED, read-only in MVP).

Generation is lazy (first checklist view with the LLM enabled), built from
the NON-elevated checklist so credential details never reach the model, and
audited. The deterministic playbook steps are always served alongside —
guidance personalizes, never replaces (ADR-0003: the LLM is an assist).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ayin.config import Settings
from ayin.llm import get_llm_client
from ayin.llm.remediation import RemediationItemView, generate_remediation
from ayin.models import RemediationTask, Scan
from ayin.models.enums import FindingCategory, RemediationType
from ayin.remediation.checklist import build_checklist
from ayin.safety.audit import record_scan_event, system_actor

log = logging.getLogger("ayin.remediation.llm")

_TYPE_BY_CATEGORY = {
    FindingCategory.BROKER.value: RemediationType.OPT_OUT,
}


def _task_type(category: str) -> RemediationType:
    return _TYPE_BY_CATEGORY.get(category, RemediationType.HARDENING)


def ensure_llm_guidance(
    db: Session, scan: Scan, settings: Settings | None = None
) -> dict[str, list[str]]:
    """{finding_id: personalized steps} for this scan's checklist findings.

    Serves existing RemediationTask rows when present; otherwise, with the
    LLM enabled, generates once, persists, and audits. Returns {} when no
    guidance exists and none can be generated — callers fall back to the
    playbook steps. Never raises past the LLM boundary. Caller commits.
    """
    _, base_items = build_checklist(db, scan, elevated=False)
    if not base_items:
        return {}
    ids = [uuid.UUID(i.finding_id) for i in base_items]
    existing = db.execute(
        select(RemediationTask).where(
            RemediationTask.finding_id.in_(ids), RemediationTask.instructions.isnot(None)
        )
    ).scalars().all()
    guidance = {str(t.finding_id): t.instructions.splitlines() for t in existing}
    missing = [i for i in base_items if i.finding_id not in guidance]
    if not missing:
        return guidance

    client = get_llm_client(settings)
    if client is None:
        return guidance
    views = [
        RemediationItemView(
            finding_id=i.finding_id,
            category=i.category,
            sensitivity=i.sensitivity,
            title=i.title,
            baseline_steps=list(i.steps),
            expected_score_delta=i.expected_score_delta,
        )
        for i in missing
    ]
    result = generate_remediation(views, client)
    by_id = {i.finding_id: i for i in missing}
    for finding_id, steps in result.steps_by_finding.items():
        item = by_id[finding_id]  # guard guarantees membership
        db.add(
            RemediationTask(
                subject_id=scan.subject_id,
                finding_id=uuid.UUID(finding_id),
                type=_task_type(item.category),
                target=item.title,
                instructions="\n".join(steps),
                evidence={
                    "generated_by": result.model,
                    "scan_id": str(scan.id),
                    "guard_ok": True,
                },
                expected_score_impact=float(item.expected_score_delta),
            )
        )
        guidance[finding_id] = steps
    record_scan_event(
        db,
        actor=system_actor("remediation"),
        event_type="scan.remediation_generated",
        scan_id=scan.id,
        subject_id=scan.subject_id,
        detail={
            "used_llm": result.used_llm,
            "model": result.model,
            "guard_ok": result.guard.ok if result.guard else None,
            "invented_finding_ids": result.guard.invented_ids if result.guard else [],
            "items_generated": len(result.steps_by_finding),
            "items_requested": len(missing),
            "tokens": result.usage.total_tokens if result.usage else 0,
        },
    )
    db.flush()
    return guidance
