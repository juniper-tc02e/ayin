"""REPORT step (pipeline step 6) — assemble the grounded narrative for a
scored scan (B1, ADR-0003).

The LLM (Qwen) may only summarize the sourced findings placed in its prompt
context; the citation guard rejects any draft citing an unknown finding id,
and the report falls back to deterministic templates (CLAUDE.md #5).

Safety properties:
- The narrative is built ONLY from findings that are visible (verified-seed
  rule) AND score-eligible (auto-matched/confirmed) — "possible" namesakes are
  never narrated as the user's exposure (FR-ER-1).
- Credential findings enter the context with a generic locked summary; the
  narrative never carries breach details, with or without step-up, so it is
  safe to serve (and cache) at the base elevation (FR-AUTH-1, FR-DISC-1).
- Every generation writes an audit record with the guard outcome and token
  spend; serving the report writes a data-access record at the route.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ayin.config import Settings
from ayin.llm import (
    FindingView,
    NarrativeContext,
    NarrativeResult,
    generate_narrative,
    get_llm_client,
)
from ayin.models import Finding, Scan, Score
from ayin.models.enums import FindingCategory
from ayin.remediation import build_checklist
from ayin.safety.audit import record_scan_event, system_actor
from ayin.safety.visibility import visible_findings_query
from ayin.scoring.engine import eligible_findings, verdict

log = logging.getLogger("ayin.report")

# What the narrative (and the LLM prompt) sees for a credential finding —
# never the connector summary, which may name the breach (step-up data).
LOCKED_CREDENTIAL_SUMMARY = (
    "A password or other credential tied to this identity appeared in a known "
    "data breach. Details are shown in the report after re-verification."
)


def build_narrative_context(db: Session, scan: Scan, score: Score) -> NarrativeContext:
    """Project the scan's findings into the non-sensitive ``FindingView`` set
    the narrative (template or LLM) is allowed to talk about."""
    _, items = build_checklist(db, scan, elevated=False)
    delta_by_id = {i.finding_id: i.expected_score_delta for i in items}
    visible_ids = {
        f.id
        for f in db.execute(
            visible_findings_query(scan.subject_id).where(Finding.scan_id == scan.id)
        ).scalars()
    }
    views = []
    for f in eligible_findings(db, scan):
        if f.id not in visible_ids:
            continue
        summary = (
            LOCKED_CREDENTIAL_SUMMARY
            if f.category == FindingCategory.CREDENTIAL
            else f.summary
        )
        views.append(
            FindingView(
                finding_id=str(f.id),
                category=f.category.value,
                sensitivity=f.sensitivity.value,
                source_name=f.source_name,
                summary=summary,
                corroboration_count=f.corroboration_count,
                expected_score_delta=delta_by_id.get(str(f.id), 0),
            )
        )
    return NarrativeContext(
        overall=score.overall, verdict=verdict(score.overall), findings=views
    )


def _cache_fresh(score: Score, client_available: bool) -> bool:
    """A cached narrative is served iff it matches the current score
    computation AND it can't be improved: an LLM-written cache is final; a
    template cache stands only while no LLM is available (or there was
    nothing to narrate — regenerating an empty report buys nothing)."""
    meta = score.narrative_meta or {}
    if score.narrative is None:
        return False
    if meta.get("score_computed_at") != score.computed_at.isoformat():
        return False
    return bool(
        meta.get("used_llm")
        or not client_available
        or meta.get("findings_in_context") == 0
    )


def get_or_generate_narrative(
    db: Session, scan: Scan, score: Score, settings: Settings | None = None
) -> tuple[dict, dict]:
    """Serve the cached narrative when still valid for this score; otherwise
    generate (Qwen when enabled, templates otherwise), persist it on the
    Score row, and audit the generation decision. Caller commits.

    Returns ``(narrative, meta)`` — both plain dicts, as persisted.
    """
    client = get_llm_client(settings)
    if _cache_fresh(score, client is not None):
        return score.narrative, score.narrative_meta or {}

    ctx = build_narrative_context(db, scan, score)
    result: NarrativeResult = generate_narrative(ctx, client if ctx.findings else None)
    now = datetime.now(timezone.utc)
    meta = {
        "used_llm": result.used_llm,
        "model": result.model,
        "generated_at": now.isoformat(),
        "score_computed_at": score.computed_at.isoformat(),
        "findings_in_context": len(ctx.findings),
        "guard_ok": result.guard.ok if result.guard else None,
        "usage": result.usage.model_dump() if result.usage else None,
    }
    score.narrative = result.draft.model_dump()
    score.narrative_meta = meta
    # Auditability of the generation decision (CLAUDE.md #7): what wrote the
    # narrative, whether the guard passed, and what it cost. Guard details
    # stay id/count-only — no claim text in the audit log (minimization).
    record_scan_event(
        db,
        actor=system_actor("report"),
        event_type="scan.narrative_generated",
        scan_id=scan.id,
        subject_id=scan.subject_id,
        detail={
            "used_llm": result.used_llm,
            "model": result.model,
            "guard_ok": result.guard.ok if result.guard else None,
            "invented_finding_ids": result.guard.invented_ids if result.guard else [],
            "unsourced_claim_count": (
                len(result.guard.unsourced_claims) if result.guard else 0
            ),
            "tokens": result.usage.total_tokens if result.usage else 0,
            "findings_in_context": len(ctx.findings),
        },
    )
    db.flush()
    return score.narrative, meta
