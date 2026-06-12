"""Citation guard — CLAUDE.md rule 5 turned into enforceable code.

An LLM may summarize retrieved, sourced findings; it may never invent findings
or speculate about a person (a defamation/safety risk, not a UX bug). This
guard validates generated narrative against the set of finding ids that were
actually placed in the prompt context:

- every claim must cite at least one finding id  → no unsourced statements;
- every cited id must be in the allowed set      → no invented findings.

The guard is pure (no I/O), so it is trivially golden-testable. A draft that
fails is rejected and callers fall back to deterministic templates.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from ayin.llm.schemas import Claim, NarrativeDraft


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    invented_ids: list[str] = field(default_factory=list)
    unsourced_claims: list[str] = field(default_factory=list)


def validate_claims(claims: Sequence[Claim], allowed_ids: Iterable[str]) -> GuardResult:
    allowed = {str(x) for x in allowed_ids}
    violations: list[str] = []
    invented: list[str] = []
    unsourced: list[str] = []
    for claim in claims:
        cited = [str(fid) for fid in claim.finding_ids]
        if not cited:
            unsourced.append(claim.text)
            violations.append(f"unsourced claim: {claim.text!r}")
            continue
        for fid in cited:
            if fid not in allowed:
                invented.append(fid)
                violations.append(f"claim cites unknown finding id {fid!r}: {claim.text!r}")
    return GuardResult(
        ok=not violations,
        violations=violations,
        invented_ids=sorted(set(invented)),
        unsourced_claims=unsourced,
    )


def validate_narrative(draft: NarrativeDraft, allowed_ids: Iterable[str]) -> GuardResult:
    """Validate every claim in a narrative draft. The ``verdict`` line is the
    deterministic read of the (itself sourced) score and is not a per-finding
    claim, so it is exempt; all ``claims`` must be grounded."""
    return validate_claims(draft.claims, allowed_ids)
