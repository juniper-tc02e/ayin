"""M4-3 acceptance: a repeatable harness reports finding precision and the
ER false-merge rate on a sample."""


import pytest
from sqlalchemy import select

from ayin.config import get_settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.fake import FakeConnector
from ayin.models import AuditRecord
from ayin.orchestrator import engine as orch
from ayin.qa.harness import (
    PRECISION_TARGET,
    compute_metrics,
    format_metrics,
    read_jsonl,
    sample_findings,
    write_jsonl,
)
from ayin.vault import NullVault
from tests.test_orchestrator import _mk_user


@pytest.fixture()
def scanned_db(db):
    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.enable("fake", environment="test")
    user = _mk_user(db)  # verified email + aux username
    orch.start_scan(
        db, requester=user, settings=get_settings(), registry=reg,
        vault=NullVault(), inline=True,
    )
    return db


def test_sampler_exports_reviewable_lines_and_audits(scanned_db, tmp_path):
    lines = sample_findings(scanned_db, n=10, reviewer="fixture-reviewer", seed=42)
    assert 1 <= len(lines) <= 10
    for line in lines:
        assert line["finding_id"] and line["category"] and line["source"]
        assert line["summary"] and line["captured_at"]
        assert line["verdict"] == "" and line["is_subject"] == ""  # blank for review

    # repeatable: same seed → same sample
    again = sample_findings(scanned_db, n=10, reviewer="fixture-reviewer", seed=42)
    assert [x["finding_id"] for x in again] == [x["finding_id"] for x in lines]

    # staff access audited like any other (CLAUDE.md #7)
    audits = scanned_db.execute(
        select(AuditRecord).where(AuditRecord.resource == "findings.qa_sample")
    ).scalars().all()
    assert audits
    assert audits[0].actor_type.value == "staff"
    assert audits[0].actor_id == "fixture-reviewer"
    assert audits[0].purpose.startswith("accuracy-qa")

    # round-trips through JSONL
    path = tmp_path / "sample.jsonl"
    write_jsonl(str(path), lines)
    assert [x["finding_id"] for x in read_jsonl(str(path))] == [
        x["finding_id"] for x in lines
    ]


def test_metrics_math_and_targets(scanned_db, tmp_path):
    lines = sample_findings(scanned_db, n=10, seed=7)
    # simulate a manual review: 1 incorrect, 1 unsure, rest correct;
    # one auto-matched line marked not-the-subject (a false merge)
    for i, line in enumerate(lines):
        line["verdict"] = "incorrect" if i == 0 else "unsure" if i == 1 else "correct"
        line["is_subject"] = "yes"
    auto = [ln for ln in lines if ln["match_status"] == "auto_matched"]
    assert auto, "fixture scan should auto-match email-keyed findings"
    auto[0]["is_subject"] = "no"

    m = compute_metrics(lines)
    decided = m.correct + m.incorrect
    assert m.reviewed == len(lines)
    assert m.incorrect == 1
    assert m.unsure == 1
    assert m.precision == pytest.approx(m.correct / decided)
    assert m.false_merges == 1
    assert m.false_merge_rate == pytest.approx(1 / m.auto_matched_reviewed)
    assert set(m.precision_by_category) <= {"credential", "broker", "social"}

    text = format_metrics(m)
    assert "precision" in text and "false-merge" in text
    # with 1 bad out of ~2-3 decided, precision is below 90% → flagged
    if m.precision is not None and m.precision < PRECISION_TARGET:
        assert "BELOW TARGET" in text


def test_clean_review_passes_targets(scanned_db):
    lines = sample_findings(scanned_db, n=10, seed=9)
    for line in lines:
        line["verdict"] = "correct"
        line["is_subject"] = "yes"
    m = compute_metrics(lines)
    assert m.precision == 1.0
    assert m.precision_ok
    assert m.false_merge_rate in (0.0, None)
    assert m.false_merge_ok
    assert "✓" in format_metrics(m)


def test_unreviewed_lines_are_ignored_not_counted(scanned_db):
    lines = sample_findings(scanned_db, n=10, seed=3)
    m = compute_metrics(lines)  # nobody reviewed anything yet
    assert m.reviewed == 0
    assert m.precision is None
    assert m.precision_ok  # no data ≠ failing; the gate needs reviews to pass meaningfully
