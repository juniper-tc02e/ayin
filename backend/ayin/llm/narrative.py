"""B1 seam: turn a scored, sourced finding set into a grounded narrative, with
the citation guard enforced and a deterministic template fallback.

This is the foundation slice that proves the architecture end-to-end while
staying DB-free and pure. The full B1 ticket (report-route + DB wiring, richer
per-category prose, "top 3 to fix now") builds on this — see
docs/adr/0003-qwen-llm-integration.md.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass

from ayin.llm import prompts
from ayin.llm.citation_guard import GuardResult, validate_narrative
from ayin.llm.client import LLMClient, LLMError
from ayin.llm.schemas import Claim, NarrativeDraft

log = logging.getLogger("ayin.llm.narrative")


@dataclass(frozen=True)
class FindingView:
    """Non-sensitive projection of a Finding for the narrative prompt. Built by
    the report layer from eligible findings; kept DB-free so this slice is
    pure and unit-testable."""

    finding_id: str
    category: str
    sensitivity: str
    source_name: str
    summary: str
    corroboration_count: int = 1


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


def _context_payload(ctx: NarrativeContext) -> dict:
    return {
        "overall": ctx.overall,
        "verdict": ctx.verdict,
        "findings": [dataclasses.asdict(f) for f in ctx.findings],
    }


def template_narrative(ctx: NarrativeContext) -> NarrativeDraft:
    """Deterministic fallback: the band verdict plus one claim per finding,
    each citing its own finding and reusing the connector's non-sensitive
    summary. Always citation-clean by construction."""
    claims = [Claim(text=f.summary, finding_ids=[f.finding_id]) for f in ctx.findings]
    return NarrativeDraft(verdict=ctx.verdict, claims=claims)


def generate_narrative(ctx: NarrativeContext, client: LLMClient | None) -> NarrativeResult:
    """Grounded LLM narrative when available and citation-clean; deterministic
    templates otherwise. The LLM can never introduce an unsourced or invented
    claim into the report (CLAUDE.md #5)."""
    if client is None:
        return NarrativeResult(template_narrative(ctx), used_llm=False, guard=None)
    allowed = {f.finding_id for f in ctx.findings}
    try:
        draft = client.complete_json(
            prompts.narrative_messages(_context_payload(ctx)), NarrativeDraft
        )
    except LLMError as exc:
        log.warning("LLM narrative unavailable/invalid (%s) — using templates", exc)
        return NarrativeResult(template_narrative(ctx), used_llm=False, guard=None)
    guard = validate_narrative(draft, allowed)
    if not guard.ok:
        log.warning(
            "LLM narrative failed the citation guard (%s) — using templates", guard.violations
        )
        return NarrativeResult(template_narrative(ctx), used_llm=False, guard=guard)
    return NarrativeResult(draft, used_llm=True, guard=guard)
