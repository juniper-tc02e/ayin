"""M5-2 acceptance: the go/no-go instrument measures §13.7 honestly.

- safety hard gates verified from the DB (audited scans, chain, T0-only)
- funnel rates vs targets with insufficient-data handling
- accuracy from a reviewed QA sample; kill criteria trip NO-GO
"""

import uuid

import pytest

from ayin.analytics import track
from ayin.beta.gonogo import MIN_COHORT, evaluate, format_gonogo
from ayin.config import get_settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.fake import FakeConnector
from ayin.models import Scan
from ayin.orchestrator import engine as orch
from ayin.qa.harness import QAMetrics, compute_metrics, sample_findings
from ayin.vault import NullVault
from tests.test_orchestrator import _mk_user


def _simulate_cohort(db, *, started=14, completed=12, viewed=10, acted=5, intent=4):
    """Pseudonymous funnel events for a synthetic cohort."""
    users = [uuid.uuid4() for _ in range(started)]
    for i, u in enumerate(users):
        track(db, "scan_started", user_id=u)
        if i < completed:
            track(db, "scan_completed", user_id=u)
        if i < viewed:
            track(db, "report_viewed", user_id=u)
        if i < acted:
            track(db, "action_started", user_id=u)
        if i < intent:
            track(db, "monitoring_intent_captured", user_id=u)
    db.commit()


def _real_scan(db):
    """One genuine scan so the safety gates have something to verify."""
    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.enable("fake", environment="test")
    user = _mk_user(db, with_aux=False)
    orch.start_scan(db, requester=user, settings=get_settings(), registry=reg,
                    vault=NullVault(), inline=True)


def _clean_qa(db) -> QAMetrics:
    lines = sample_findings(db, n=10, seed=5)
    for line in lines:
        line["verdict"] = "correct"
        line["is_subject"] = "yes"
    return compute_metrics(lines)


def test_go_when_everything_passes_on_sufficient_data(db):
    _real_scan(db)
    _simulate_cohort(db)  # 14 started / 12 completed / 10 viewed / 5 acted / 4 intent
    result = evaluate(db, qa_metrics=_clean_qa(db), min_cohort=MIN_COHORT)
    text = format_gonogo(result)
    assert all(c.status == "pass" for c in result.safety), text
    assert all(c.status == "pass" for c in result.funnel), text
    assert all(c.status == "pass" for c in result.accuracy), text
    assert result.verdict == "GO"
    assert result.exit_code == 0


def test_insufficient_data_with_tiny_cohort(db):
    _real_scan(db)
    _simulate_cohort(db, started=3, completed=3, viewed=3, acted=2, intent=1)
    result = evaluate(db, qa_metrics=_clean_qa(db))
    assert result.verdict == "INSUFFICIENT DATA"
    assert result.exit_code == 2
    assert any(c.status == "needs_data" for c in result.funnel)


def test_missing_qa_sample_is_insufficient_not_go(db):
    _real_scan(db)
    _simulate_cohort(db)
    result = evaluate(db, qa_metrics=None)
    assert result.verdict == "INSUFFICIENT DATA"
    assert all(c.status == "needs_data" for c in result.accuracy)


def test_activation_kill_criterion_trips_nogo(db):
    _real_scan(db)
    _simulate_cohort(db, started=14, completed=14, viewed=3, acted=1, intent=1)  # ~21% activation
    result = evaluate(db, qa_metrics=_clean_qa(db))
    assert result.verdict == "NO-GO"
    assert any("activation" in k for k in result.kill_criteria)
    assert result.exit_code == 1


def test_precision_kill_criterion_trips_nogo(db):
    _real_scan(db)
    _simulate_cohort(db)
    lines = sample_findings(db, n=10, seed=6)
    for i, line in enumerate(lines):  # 50% wrong — way below the gate
        line["verdict"] = "incorrect" if i % 2 == 0 else "correct"
        line["is_subject"] = "yes"
    result = evaluate(db, qa_metrics=compute_metrics(lines))
    assert result.verdict == "NO-GO"
    assert any("precision" in k for k in result.kill_criteria)


def test_unaudited_scan_fails_the_safety_hard_gate(db):
    """A scan row with no scan.created audit record = a hole in the spine."""
    _real_scan(db)
    user = _mk_user(db, with_aux=False)
    from sqlalchemy import select
    from ayin.models import Subject
    subject = db.execute(
        select(Subject).where(Subject.owner_user_id == user.id)
    ).scalar_one()
    db.add(Scan(requester_user_id=user.id, subject_id=subject.id))  # raw, unaudited
    db.commit()
    _simulate_cohort(db)
    result = evaluate(db, qa_metrics=_clean_qa(db))
    audited = next(c for c in result.safety if "audited" in c.name)
    assert audited.status == "fail"
    assert result.verdict == "NO-GO"
