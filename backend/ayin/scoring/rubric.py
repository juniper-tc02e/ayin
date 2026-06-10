"""Exposure Score rubric v0 (PRD §23.3) — versioned; methodology changes bump
RUBRIC_VERSION so data-driven score moves and rubric-driven moves are
distinguishable in trends (PRD §8.3 'honest versioning').

points(finding) = sensitivity_base × exploitability_factor × recency_factor
                  × corroboration_factor

- sensitivity_base: how bad this class of exposure is at face value
  (live password ≫ broker listing ≫ public bio — §23.3)
- exploitability_factor: how usable it is for an attacker (connector
  estimate; neutral 0.5 when unknown)
- recency_factor: half-life decay on the exposure's event date (a 2015
  breach matters less than last year's); floor keeps old exposure non-zero
- corroboration_factor: independently-seen exposure is more reliably real

Category points sum and saturate onto 0-100 via 1 - exp(-points/K): the
first findings move the needle most, and no category can exceed 100 no
matter how many findings pile up. The overall score is the weighted sum of
category sub-scores. Only AUTO_MATCHED / CONFIRMED findings count — a
"possible" namesake never moves a person's number (FR-ER-1).
"""

import math
from datetime import datetime, timezone

from ayin.models import Finding
from ayin.models.enums import FindingCategory, Sensitivity

RUBRIC_VERSION = "0.1.0"

SENSITIVITY_BASE: dict[Sensitivity, float] = {
    Sensitivity.LOW: 1.0,
    Sensitivity.MEDIUM: 2.5,
    Sensitivity.HIGH: 5.0,
    Sensitivity.CRITICAL: 9.0,
}

# Overall weighting across categories (sums to 1.0) — credentials dominate
# because they are the most directly exploitable (PRD §23.3).
CATEGORY_WEIGHTS: dict[FindingCategory, float] = {
    FindingCategory.CREDENTIAL: 0.40,
    FindingCategory.BROKER: 0.25,
    FindingCategory.SOCIAL: 0.15,
    FindingCategory.RECORDS: 0.10,
    FindingCategory.LINKAGE: 0.10,
}

# Saturation constants: roughly "points at which a category reaches ~63/100".
CATEGORY_K: dict[FindingCategory, float] = {
    FindingCategory.CREDENTIAL: 12.0,
    FindingCategory.BROKER: 8.0,
    FindingCategory.SOCIAL: 6.0,
    FindingCategory.RECORDS: 6.0,
    FindingCategory.LINKAGE: 5.0,
}

RECENCY_HALF_LIFE_DAYS = 730.0  # exposure relevance halves every ~2 years
RECENCY_FLOOR = 0.35  # old exposure never decays to nothing
CORROBORATION_STEP = 0.15  # per extra independent source
CORROBORATION_CAP = 1.45
NEUTRAL_EXPLOITABILITY = 0.5


def exploitability_factor(exploitability: float | None) -> float:
    value = NEUTRAL_EXPLOITABILITY if exploitability is None else exploitability
    return 0.6 + 0.4 * value  # 0.6 .. 1.0


def event_date(finding: Finding) -> datetime:
    """The exposure's own date when the source provides one (e.g. breach
    date); otherwise when we captured it."""
    raw = (finding.payload or {}).get("breach_date")
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return finding.captured_at


def recency_factor(finding: Finding, *, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    age_days = max(0.0, (now - event_date(finding)).total_seconds() / 86400.0)
    return max(RECENCY_FLOOR, 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS))


def corroboration_factor(corroboration_count: int) -> float:
    extra = max(0, (corroboration_count or 1) - 1)
    return min(CORROBORATION_CAP, 1.0 + CORROBORATION_STEP * extra)


def finding_points(finding: Finding, *, now: datetime | None = None) -> float:
    return (
        SENSITIVITY_BASE[finding.sensitivity]
        * exploitability_factor(finding.exploitability)
        * recency_factor(finding, now=now)
        * corroboration_factor(finding.corroboration_count)
    )


def saturate(points: float, category: FindingCategory) -> int:
    return round(100.0 * (1.0 - math.exp(-points / CATEGORY_K[category])))
