"""B1: turn a scored, sourced finding set into a grounded narrative — verdict,
claims, per-category summaries, and "top fixes" — with the citation guard
enforced and a deterministic template fallback.

DB-free and pure: the report layer (``ayin.report``) builds the
``NarrativeContext`` from eligible findings and persists the result. See
docs/adr/0003-qwen-llm-integration.md.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass

from ayin.llm import prompts
from ayin.llm.citation_guard import GuardResult, validate_narrative
from ayin.llm.client import LLMClient, LLMError, parse_into
from ayin.llm.schemas import MAX_TEXT, CategorySummary, Claim, LLMUsage, NarrativeDraft

log = logging.getLogger("ayin.llm.narrative")

TOP_FIXES_MAX = 3

# Generic, deterministic remediation phrasing per category (template path).
_FIX_TEXT = {
    "credential": "Rotate the exposed password and turn on multi-factor authentication",
    "broker": "Follow the opt-out steps to remove the people-search listing",
    "social": "Review the public page and tighten what it shows",
}
_FIX_FALLBACK = "Review this exposure and decide whether it should be public"


@dataclass(frozen=True)
class FindingView:
    """Non-sensitive projection of a Finding for the narrative prompt. Built by
    the report layer from eligible findings; kept DB-free so this slice is
    pure and unit-testable. ``expected_score_delta`` is the honest what-if
    number from the hardening checklist (re-running the rubric without the
    finding), used to rank "top fixes"."""

    finding_id: str
    category: str
    sensitivity: str
    source_name: str
    summary: str
    corroboration_count: int = 1
    expected_score_delta: int = 0


@dataclass(frozen=True)
class NarrativeContext:
    overall: int
    verdict: str  # deterministic band text (e.g. scoring.verdict(overall))
    findings: list[FindingView]


@dataclass(frozen=True)
class NarrativeResult:
    draft: NarrativeDraft
    used_llm: bool
    guard: GuardResult | None  # None when templates were used without an LLM attempt
    model: str | None = None  # the model actually called, when a call was made
    usage: LLMUsage | None = None  # token spend of that call (cost telemetry)


def _context_payload(ctx: NarrativeContext) -> dict:
    return {
        "overall": ctx.overall,
        "verdict": ctx.verdict,
        "findings": [dataclasses.asdict(f) for f in ctx.findings],
    }


def _template_category_summaries(views: list[FindingView]) -> list[CategorySummary]:
    by_cat: dict[str, list[FindingView]] = {}
    for v in views:
        by_cat.setdefault(v.category, []).append(v)
    out = []
    for cat in sorted(by_cat):
        vs = by_cat[cat]
        sources = sorted({v.source_name for v in vs})
        n = len(vs)
        text = (
            f"{n} {cat} exposure{'s' if n != 1 else ''} found "
            f"(source{'s' if len(sources) != 1 else ''}: {', '.join(sources)})."
        )
        out.append(
            CategorySummary(
                category=cat,
                text=text[:MAX_TEXT],
                finding_ids=[v.finding_id for v in vs][:500],
            )
        )
    return out


def _template_top_fixes(views: list[FindingView]) -> list[Claim]:
    ranked = sorted(views, key=lambda v: -v.expected_score_delta)
    fixes: list[Claim] = []
    for v in ranked[:TOP_FIXES_MAX]:
        if v.expected_score_delta <= 0 and fixes:
            break  # only the top item rides along when no delta is positive
        action = _FIX_TEXT.get(v.category, _FIX_FALLBACK)
        suffix = (
            f" — expected to lower your score by about {v.expected_score_delta} points"
            if v.expected_score_delta > 0
            else ""
        )
        fixes.append(Claim(text=f"{action}{suffix}.", finding_ids=[v.finding_id]))
    return fixes


def template_narrative(ctx: NarrativeContext) -> NarrativeDraft:
    """Deterministic fallback: the band verdict, one claim per finding reusing
    the connector's non-sensitive summary, per-category counts, and top fixes
    ranked by honest score deltas. Always citation-clean by construction."""
    # slices keep template drafts inside the schema's model-abuse bounds even
    # for unusually long connector summaries
    claims = [
        Claim(text=f.summary[:MAX_TEXT], finding_ids=[f.finding_id]) for f in ctx.findings
    ]
    return NarrativeDraft(
        verdict=ctx.verdict[:MAX_TEXT],
        claims=claims,
        category_summaries=_template_category_summaries(ctx.findings),
        top_fixes=_template_top_fixes(ctx.findings),
    )


def generate_narrative(ctx: NarrativeContext, client: LLMClient | None) -> NarrativeResult:
    """Grounded LLM narrative when available and citation-clean; deterministic
    templates otherwise. The LLM can never introduce an unsourced or invented
    claim into the report (CLAUDE.md #5)."""
    if client is None:
        return NarrativeResult(template_narrative(ctx), used_llm=False, guard=None)
    allowed = {f.finding_id for f in ctx.findings}
    try:
        resp = client.complete(prompts.narrative_messages(_context_payload(ctx)))
        draft = parse_into(resp.content, NarrativeDraft)
    except LLMError as exc:
        log.warning("LLM narrative unavailable/invalid (%s) — using templates", exc)
        return NarrativeResult(template_narrative(ctx), used_llm=False, guard=None)
    guard = validate_narrative(draft, allowed)
    if not guard.ok:
        log.warning(
            "LLM narrative failed the citation guard (%s) — using templates", guard.violations
        )
        return NarrativeResult(
            template_narrative(ctx), used_llm=False, guard=guard,
            model=resp.model, usage=resp.usage,
        )
    # The verdict line is exempt from the citation guard (it summarizes the
    # score, not a finding), so it must not be model-steerable: the report's
    # most prominent line is always the deterministic band text. The model's
    # voice lives in the cited sections only.
    draft = draft.model_copy(update={"verdict": ctx.verdict})
    return NarrativeResult(draft, used_llm=True, guard=guard, model=resp.model, usage=resp.usage)
