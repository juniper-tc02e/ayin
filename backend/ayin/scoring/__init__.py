"""Exposure Score (FR-SCORE-1, M2-3).

THE GUARDRAIL (CLAUDE.md #2, PRD §8.3): this score measures the exposure and
exploitability of a person's DATA — never the person. It must never be used,
extended, or interpreted as a trust, credit, character, or eligibility
signal. That line is load-bearing (FCRA).
"""

from ayin.scoring.engine import compute_score, verdict

__all__ = ["compute_score", "verdict"]
