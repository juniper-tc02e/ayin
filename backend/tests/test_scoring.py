"""M2-3 acceptance: Exposure Score v0.

- score recomputes per scan (pipeline) and on confirm/reject (feedback)
- contributors trace every point to finding ids; rubric version labeled
- 'possible' / rejected findings never move the number
- weighting behaves: sensitivity, recency decay, corroboration
- bounds hold 0-100; empty scan scores 0
- measures exposure only (verdict copy never describes the person)
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from ayin.config import get_settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.fake import FakeConnector
from ayin.models import AuditRecord, Finding, Identifier, Scan, Score, Subject, User
from ayin.models.enums import (
    FindingCategory,
    IdentifierKind,
    MatchStatus,
    Sensitivity,
    VerificationState,
)
from ayin.orchestrator import engine as orch
from ayin.resolution.feedback import confirm_finding, reject_finding
from ayin.scoring import compute_score, verdict
from ayin.scoring import rubric
from ayin.vault import NullVault

NOW = datetime(2026, 6, 10, tzinfo=timezone.utc)


@pytest.fixture()
def ctx(db):
    user = User(email=f"score-{uuid.uuid4().hex[:8]}@example.org")
    db.add(user)
    db.flush()
    subject = Subject(owner_user_id=user.id)
    db.add(subject)
    db.flush()
    email = Identifier(
        subject_id=subject.id, kind=IdentifierKind.EMAIL,
        value_raw=user.email, value_normalized=user.email,
        verification_state=VerificationState.VERIFIED, verified_at=NOW,
    )
    db.add(email)
    db.flush()
    scan = Scan(requester_user_id=user.id, subject_id=subject.id)
    db.add(scan)
    db.flush()
    db.commit()
    return {"user": user, "subject": subject, "scan": scan, "email": email}


def _finding(db, ctx, *, category=FindingCategory.CREDENTIAL,
             sensitivity=Sensitivity.HIGH, confidence=0.9, exploitability=None,
             match=MatchStatus.AUTO_MATCHED, corroboration=1, payload=None,
             captured_at=None):
    f = Finding(
        scan_id=ctx["scan"].id,
        subject_id=ctx["subject"].id,
        identifier_id=ctx["email"].id,
        category=category,
        sensitivity=sensitivity,
        source="fixture",
        source_name="Fixture Source",
        captured_at=captured_at or NOW,
        confidence=confidence,
        exploitability=exploitability,
        summary="Clearly-fake fixture finding.",
        payload=payload or {},
        dedupe_key=f"fx:{uuid.uuid4().hex[:10]}",
        match_status=match,
        corroboration_count=corroboration,
    )
    db.add(f)
    db.flush()
    return f


def test_empty_scan_scores_zero(db, ctx):
    score = compute_score(db, ctx["scan"])
    db.commit()
    assert score.overall == 0
    assert set(score.subscores) == {c.value for c in FindingCategory}
    assert all(v == 0 for v in score.subscores.values())
    assert score.rubric_version == rubric.RUBRIC_VERSION
    assert score.contributing == []


def test_points_match_rubric_and_trace_to_findings(db, ctx):
    f1 = _finding(db, ctx, sensitivity=Sensitivity.CRITICAL, exploitability=0.8,
                  payload={"breach_name": "FakeBreach", "breach_date": "2026-01-01"})
    f2 = _finding(db, ctx, category=FindingCategory.BROKER,
                  sensitivity=Sensitivity.HIGH, corroboration=2)
    db.commit()
    score = compute_score(db, ctx["scan"])
    db.commit()

    by_id = {c["finding_id"]: c for c in score.contributing}
    assert set(by_id) == {str(f1.id), str(f2.id)}  # every point traces to a finding
    db.expire_all()
    for f in (f1, f2):
        expected = rubric.finding_points(db.get(Finding, f.id))
        assert by_id[str(f.id)]["points"] == pytest.approx(expected, abs=0.01)
    assert by_id[str(f2.id)]["reason"]
    # contributors sorted by impact
    points = [c["points"] for c in score.contributing]
    assert points == sorted(points, reverse=True)


def test_possible_and_rejected_never_move_the_number(db, ctx):
    _finding(db, ctx, match=MatchStatus.POSSIBLE, sensitivity=Sensitivity.CRITICAL)
    _finding(db, ctx, match=MatchStatus.REJECTED, sensitivity=Sensitivity.CRITICAL)
    db.commit()
    score = compute_score(db, ctx["scan"])
    assert score.overall == 0
    assert score.contributing == []


def test_confirming_a_possible_finding_recomputes_upward(db, ctx):
    f = _finding(db, ctx, match=MatchStatus.POSSIBLE, sensitivity=Sensitivity.HIGH)
    db.commit()
    assert compute_score(db, ctx["scan"]).overall == 0

    confirm_finding(db, ctx["user"], f)  # feedback hook recomputes
    db.commit()
    score = db.execute(select(Score).where(Score.scan_id == ctx["scan"].id)).scalar_one()
    assert score.overall > 0

    reject_finding(db, ctx["user"], f)
    db.commit()
    db.expire_all()
    score = db.execute(select(Score).where(Score.scan_id == ctx["scan"].id)).scalar_one()
    assert score.overall == 0  # the user's 'not me' immediately zeroes it back


def test_sensitivity_orders_impact(db, ctx):
    low = _finding(db, ctx, category=FindingCategory.SOCIAL, sensitivity=Sensitivity.LOW)
    crit = _finding(db, ctx, sensitivity=Sensitivity.CRITICAL)
    db.commit()
    score = compute_score(db, ctx["scan"])
    by_id = {c["finding_id"]: c["points"] for c in score.contributing}
    assert by_id[str(crit.id)] > by_id[str(low.id)] * 3


def test_recency_decay_old_breach_scores_less(db, ctx):
    fresh = _finding(db, ctx, payload={"breach_date": (NOW - timedelta(days=30)).date().isoformat()})
    stale = _finding(db, ctx, payload={"breach_date": "2014-01-01"})
    db.commit()
    score = compute_score(db, ctx["scan"])
    by_id = {c["finding_id"]: c["points"] for c in score.contributing}
    assert by_id[str(fresh.id)] > by_id[str(stale.id)]
    # but old exposure never decays to zero (floor)
    assert by_id[str(stale.id)] >= rubric.SENSITIVITY_BASE[Sensitivity.HIGH] * 0.6 * rubric.RECENCY_FLOOR * 0.99


def test_corroboration_raises_points(db, ctx):
    single = _finding(db, ctx, corroboration=1)
    multi = _finding(db, ctx, corroboration=3)
    db.commit()
    score = compute_score(db, ctx["scan"])
    by_id = {c["finding_id"]: c["points"] for c in score.contributing}
    assert by_id[str(multi.id)] == pytest.approx(by_id[str(single.id)] * 1.30, rel=0.01)


def test_scores_saturate_and_stay_bounded(db, ctx):
    for _ in range(60):
        _finding(db, ctx, sensitivity=Sensitivity.CRITICAL, exploitability=1.0,
                 corroboration=4)
    db.commit()
    score = compute_score(db, ctx["scan"])
    assert score.subscores["credential"] <= 100
    assert 0 <= score.overall <= 100
    # with everything else empty, overall = credential weight × 100
    assert score.overall == round(rubric.CATEGORY_WEIGHTS[FindingCategory.CREDENTIAL] * 100)


def test_recompute_updates_one_row_per_scan(db, ctx):
    _finding(db, ctx)
    db.commit()
    s1 = compute_score(db, ctx["scan"])
    first_overall = s1.overall
    _finding(db, ctx, sensitivity=Sensitivity.CRITICAL)
    db.commit()
    s2 = compute_score(db, ctx["scan"])
    db.commit()
    rows = db.execute(select(Score).where(Score.scan_id == ctx["scan"].id)).scalars().all()
    assert len(rows) == 1  # updated in place, not duplicated
    assert s2.overall > first_overall  # monotone in new exposure


def test_full_pipeline_produces_audited_score(db):
    from tests.test_orchestrator import _mk_user

    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.enable("fake", environment="test")
    user = _mk_user(db, with_aux=False)
    scan, _ = orch.start_scan(
        db, requester=user, settings=get_settings(), registry=reg,
        vault=NullVault(), inline=True,
    )
    score = db.execute(select(Score).where(Score.scan_id == scan.id)).scalar_one()
    assert score.overall > 0  # fake breach (critical-ish) + broker listing
    assert score.rubric_version == rubric.RUBRIC_VERSION
    events = db.execute(
        select(AuditRecord.event_type).where(AuditRecord.scan_id == scan.id)
    ).scalars().all()
    assert "scan.scored" in events
    assert "scan.resolved" in events


def test_verdict_describes_exposure_never_the_person():
    for n in (0, 25, 50, 70, 95):
        text = verdict(n).lower()
        assert "exposure" in text
        # the FCRA line: no person-judgment language
        for banned in ("trustworth", "character", "credit", "eligib", "reliab"):
            assert banned not in text
