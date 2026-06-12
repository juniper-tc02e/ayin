"""B4 — gray-zone entity-resolution assist.

For findings the rules left at match_status=POSSIBLE (the band between the
anti-namesake cap and the auto-match threshold — resolution.engine), Qwen
gives a structured second opinion: match / no_match / unsure + the evidence
it relied on.

The opinion is ADVICE ONLY (FR-ER-1): it never changes match_status or
match_confidence — deterministic rules stay the floor, and the user's
confirm/reject is the only promotion path (the human-in-the-loop
checkpoint). Judgments citing a finding that wasn't offered are rejected
wholesale by the same citation guard as the narrative (CLAUDE.md #5).

DB-free and pure; ``ayin.resolution.llm_assist`` does the persistence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ayin.llm import prompts
from ayin.llm.citation_guard import GuardResult, validate_claims
from ayin.llm.client import LLMClient, LLMError, complete_parsed
from ayin.llm.schemas import Claim, ERAssistResponse, ERJudgment, LLMUsage

log = logging.getLogger("ayin.llm.er_assist")


@dataclass(frozen=True)
class ERCandidateView:
    """Non-sensitive projection of one gray-zone finding: the derived match
    evidence the rules already computed, never raw payloads or seed values
    beyond the finding's own public summary."""

    finding_id: str
    category: str
    sensitivity: str
    source_name: str
    summary: str
    match_confidence: float
    match_reasons: list[str]
    corroboration_count: int = 1


@dataclass(frozen=True)
class ERAssistResult:
    judgments_by_finding: dict[str, ERJudgment]  # empty = no opinions
    used_llm: bool
    guard: GuardResult | None
    model: str | None = None
    usage: LLMUsage | None = None


def _context_payload(candidates: list[ERCandidateView]) -> dict:
    return {
        "candidates": [
            {
                "finding_id": c.finding_id,
                "category": c.category,
                "sensitivity": c.sensitivity,
                "source_name": c.source_name,
                "summary": c.summary,
                "rules_match_confidence": c.match_confidence,
                "rules_match_reasons": c.match_reasons,
                "corroboration_count": c.corroboration_count,
            }
            for c in candidates
        ]
    }


def judge_gray_zone(
    candidates: list[ERCandidateView], client: LLMClient | None
) -> ERAssistResult:
    """Structured opinions for the offered candidates, or an empty result —
    nothing downstream may depend on one existing."""
    if client is None or not candidates:
        return ERAssistResult({}, used_llm=False, guard=None)
    allowed = {c.finding_id for c in candidates}
    try:
        resp, parsed = complete_parsed(
            client, prompts.er_assist_messages(_context_payload(candidates)), ERAssistResponse
        )
    except LLMError as exc:
        log.warning("LLM ER assist unavailable/invalid (%s) — no opinions", exc)
        return ERAssistResult({}, used_llm=False, guard=None)
    guard = validate_claims(
        [
            Claim(text=item.verdict.value, finding_ids=[item.finding_id])
            for item in parsed.items
        ],
        allowed,
    )
    if not guard.ok:
        log.warning(
            "LLM ER assist failed the citation guard (%s) — no opinions",
            guard.violations,
        )
        return ERAssistResult(
            {}, used_llm=False, guard=guard, model=resp.model, usage=resp.usage
        )
    judgments = {
        item.finding_id: ERJudgment(verdict=item.verdict, evidence=list(item.evidence))
        for item in parsed.items
    }
    return ERAssistResult(
        judgments, used_llm=True, guard=guard, model=resp.model, usage=resp.usage
    )
