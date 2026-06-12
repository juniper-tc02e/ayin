"""B3 — LLM-personalized remediation guidance over the checklist playbook.

The deterministic checklist (ayin.remediation.checklist) stays the floor:
its steps are always served. When the LLM is enabled, Qwen rewrites the
playbook steps per finding into friendlier, more concrete guidance — guarded
exactly like the narrative (CLAUDE.md #5): a draft covering a finding id that
wasn't in the input is rejected wholesale, and callers keep the playbook.

DB-free and pure; ``ayin.remediation.llm_guidance`` does the persistence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ayin.llm import prompts
from ayin.llm.citation_guard import GuardResult, validate_claims
from ayin.llm.client import LLMClient, LLMError, complete_parsed
from ayin.llm.schemas import Claim, LLMUsage, RemediationPlan

log = logging.getLogger("ayin.llm.remediation")


@dataclass(frozen=True)
class RemediationItemView:
    """Non-sensitive projection of one checklist item for the prompt. Built
    from the NON-elevated checklist — credential titles stay generic, so no
    breach detail can reach the model (FR-AUTH-1)."""

    finding_id: str
    category: str
    sensitivity: str
    title: str
    baseline_steps: list[str]
    expected_score_delta: int = 0


@dataclass(frozen=True)
class RemediationResult:
    steps_by_finding: dict[str, list[str]]  # empty = use the playbook as-is
    used_llm: bool
    guard: GuardResult | None
    model: str | None = None
    usage: LLMUsage | None = None


def _context_payload(items: list[RemediationItemView]) -> dict:
    return {
        "findings": [
            {
                "finding_id": i.finding_id,
                "category": i.category,
                "sensitivity": i.sensitivity,
                "title": i.title,
                "baseline_steps": i.baseline_steps,
                "expected_score_delta": i.expected_score_delta,
            }
            for i in items
        ]
    }


def generate_remediation(
    items: list[RemediationItemView], client: LLMClient | None
) -> RemediationResult:
    """Personalized steps per finding, or an empty result when the LLM is
    unavailable / uncited — the playbook is always the fallback."""
    if client is None or not items:
        return RemediationResult({}, used_llm=False, guard=None)
    allowed = {i.finding_id for i in items}
    try:
        resp, plan = complete_parsed(
            client, prompts.remediation_messages(_context_payload(items)), RemediationPlan
        )
    except LLMError as exc:
        log.warning("LLM remediation unavailable/invalid (%s) — keeping playbook", exc)
        return RemediationResult({}, used_llm=False, guard=None)
    # Same guard as the narrative: each draft is one "claim" citing its finding.
    guard = validate_claims(
        [
            Claim(text=" / ".join(d.steps) or "(empty)", finding_ids=[d.finding_id])
            for d in plan.items
        ],
        allowed,
    )
    if not guard.ok:
        log.warning(
            "LLM remediation failed the citation guard (%s) — keeping playbook",
            guard.violations,
        )
        return RemediationResult(
            {}, used_llm=False, guard=guard, model=resp.model, usage=resp.usage
        )
    steps = {d.finding_id: list(d.steps) for d in plan.items}
    return RemediationResult(
        steps, used_llm=True, guard=guard, model=resp.model, usage=resp.usage
    )
