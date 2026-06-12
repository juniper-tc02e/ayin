"""B4 persistence: attach Qwen's gray-zone opinion to POSSIBLE findings.

The opinion lands in ``finding.resolution["llm_opinion"]`` — display-only
material for the user's confirm/reject review (FR-ER-1). It NEVER moves
match_status or match_confidence; the assertion of that invariant is in the
tests, the enforcement is simply that this module never writes those fields.
Every generation is audited. Fail-soft: any LLM problem leaves findings
exactly as the rules left them.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ayin.config import Settings
from ayin.llm import get_llm_client
from ayin.llm.er_assist import ERCandidateView, judge_gray_zone
from ayin.models import Finding, Scan
from ayin.models.enums import FindingCategory, FindingState, MatchStatus
from ayin.safety.audit import record_scan_event, system_actor

log = logging.getLogger("ayin.resolution.llm_assist")

# Below this the rules are confident enough that it's a stranger/noise;
# asking the model would only invite overreach.
ER_ASSIST_MIN_CONFIDENCE = 0.40

# The same masking rule as the report narrative: credential summaries are
# step-up data and never reach the model.
_LOCKED_CREDENTIAL_SUMMARY = "A credential exposure (details withheld)."


def annotate_gray_zone(
    db: Session, scan: Scan, settings: Settings | None = None
) -> dict[str, str]:
    """{finding_id: verdict} for the gray-zone findings annotated this call.

    Picks active POSSIBLE primaries without a stored opinion, asks Qwen once,
    stores guarded opinions on ``resolution["llm_opinion"]``, audits. Returns
    {} when the LLM is disabled or nothing qualifies. Caller commits.
    """
    client = get_llm_client(settings)
    if client is None:
        return {}
    rows = list(
        db.execute(
            select(Finding).where(
                Finding.scan_id == scan.id,
                Finding.state == FindingState.ACTIVE,
                Finding.match_status == MatchStatus.POSSIBLE,
            )
        ).scalars()
    )
    gray = [
        f
        for f in rows
        if (f.match_confidence or 0.0) >= ER_ASSIST_MIN_CONFIDENCE
        and "llm_opinion" not in (f.resolution or {})
    ]
    if not gray:
        return {}
    candidates = [
        ERCandidateView(
            finding_id=str(f.id),
            category=f.category.value,
            sensitivity=f.sensitivity.value,
            source_name=f.source_name,
            summary=(
                _LOCKED_CREDENTIAL_SUMMARY
                if f.category == FindingCategory.CREDENTIAL
                else f.summary
            ),
            match_confidence=f.match_confidence or 0.0,
            match_reasons=list((f.resolution or {}).get("match_reasons", [])),
            corroboration_count=f.corroboration_count,
        )
        for f in gray
    ]
    result = judge_gray_zone(candidates, client)
    by_id = {str(f.id): f for f in gray}
    verdicts: dict[str, str] = {}
    for finding_id, judgment in result.judgments_by_finding.items():
        f = by_id[finding_id]  # guard guarantees membership
        resolution = dict(f.resolution or {})
        resolution["llm_opinion"] = {
            "verdict": judgment.verdict.value,
            "evidence": judgment.evidence,
            "model": result.model,
        }
        f.resolution = resolution
        verdicts[finding_id] = judgment.verdict.value
    record_scan_event(
        db,
        actor=system_actor("er-assist"),
        event_type="scan.er_assist_generated",
        scan_id=scan.id,
        subject_id=scan.subject_id,
        detail={
            "used_llm": result.used_llm,
            "model": result.model,
            "guard_ok": result.guard.ok if result.guard else None,
            "invented_finding_ids": result.guard.invented_ids if result.guard else [],
            "candidates": len(candidates),
            "judgments": len(verdicts),
            "verdict_counts": {
                v: sum(1 for x in verdicts.values() if x == v)
                for v in set(verdicts.values())
            },
            "tokens": result.usage.total_tokens if result.usage else 0,
        },
    )
    db.flush()
    return verdicts
