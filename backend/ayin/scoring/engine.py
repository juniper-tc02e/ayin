"""Score computation (M2-3). Recomputes per scan (pipeline SCORING step) and
whenever the user confirms/rejects a match (resolution.feedback hook), so the
number always reflects the confirmed picture."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ayin.models import Finding, Scan, Score
from ayin.models.enums import FindingCategory, FindingState, MatchStatus
from ayin.safety.audit import record_scan_event, system_actor
from ayin.scoring import rubric

log = logging.getLogger("ayin.scoring")


def eligible_findings(db: Session, scan: Scan) -> list[Finding]:
    """Only what we're confident is the requester's own exposure: active
    primaries that auto-matched or were user-confirmed. 'Possible' namesakes
    and rejected findings never move the number (FR-ER-1)."""
    return list(
        db.execute(
            select(Finding).where(
                Finding.scan_id == scan.id,
                Finding.state == FindingState.ACTIVE,
                Finding.match_status.in_([MatchStatus.AUTO_MATCHED, MatchStatus.CONFIRMED]),
            )
        ).scalars()
    )


def aggregate(findings: list[Finding], *, now: datetime | None = None) -> tuple[int, dict, list]:
    """Pure scoring math over a finding set → (overall, subscores,
    contributing). Used by compute_score AND by what-if calculations
    (e.g. the hardening checklist's expected score deltas, M3-2)."""
    now = now or datetime.now(timezone.utc)
    category_points: dict[FindingCategory, float] = dict.fromkeys(FindingCategory, 0.0)
    contributing: list[dict] = []
    for f in findings:
        points = rubric.finding_points(f, now=now)
        category_points[f.category] += points
        contributing.append(
            {
                "finding_id": str(f.id),
                "category": f.category.value,
                "points": round(points, 2),
                "reason": (
                    f"{f.sensitivity.value} {f.category.value} exposure "
                    f"(source confidence {f.confidence:.2f}, "
                    f"{f.corroboration_count} source(s))"
                ),
            }
        )
    contributing.sort(key=lambda c: -c["points"])
    subscores = {
        cat.value: rubric.saturate(points, cat) for cat, points in category_points.items()
    }
    overall = round(
        sum(rubric.CATEGORY_WEIGHTS[cat] * subscores[cat.value] for cat in FindingCategory)
    )
    return max(0, min(100, overall)), subscores, contributing


def compute_score(db: Session, scan: Scan) -> Score:
    """Compute (or recompute) the scan's Exposure Score. Commits are the
    caller's job; one Score row per scan, updated in place."""
    now = datetime.now(timezone.utc)
    findings = eligible_findings(db, scan)
    overall, subscores, contributing = aggregate(findings, now=now)

    score = db.execute(select(Score).where(Score.scan_id == scan.id)).scalar_one_or_none()
    if score is None:
        score = Score(scan_id=scan.id, subject_id=scan.subject_id, overall=overall,
                      subscores=subscores, rubric_version=rubric.RUBRIC_VERSION,
                      contributing=contributing, computed_at=now)
        db.add(score)
    else:
        score.overall = overall
        score.subscores = subscores
        score.rubric_version = rubric.RUBRIC_VERSION
        score.contributing = contributing
        score.computed_at = now
    db.flush()
    record_scan_event(
        db, actor=system_actor("scoring"), event_type="scan.scored",
        scan_id=scan.id, subject_id=scan.subject_id,
        detail={"overall": overall, "rubric_version": rubric.RUBRIC_VERSION,
                "findings_counted": len(findings)},
    )
    db.flush()
    return score


def verdict(overall: int) -> str:
    """One-line plain-language read of the number — calm, not alarmist
    (PRD §12.1). Describes data exposure only, never the person."""
    if overall < 10:
        return "Your public exposure is minimal — keep it that way with periodic checks."
    if overall < 30:
        return "Your exposure is low. A few small cleanups would shrink it further."
    if overall < 55:
        return ("Your exposure is moderate. The top items below are worth fixing — "
                "each one shrinks your score.")
    if overall < 80:
        return ("Your exposure is high. Start with the credential items — they're the "
                "most exploitable and the fastest to fix.")
    return ("Your exposure is severe but fixable. Work through the top items below, "
            "starting with anything involving passwords.")
