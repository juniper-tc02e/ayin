"""S2-1 acceptance: the pivot-graph schema (ADR-0005).

A ``PivotLink`` is a sourced, candidate linkage edge for the agentic self-scan.
The invariants that keep it safe are enforced at the schema level, not just in
code: every edge is sourced + confidence-bounded, hops are positive, the same
edge can't be asserted twice in one scan, and dropping the source finding drops
its edges (data minimization). ``correlation_group_id`` clusters findings that
describe the same exposure across sources.

All data clearly fake.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ayin.models import Finding, Identifier, PivotLink, Scan, Subject, User
from ayin.models.enums import (
    FindingCategory,
    IdentifierKind,
    PivotLinkStatus,
    Sensitivity,
    VerificationState,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def ctx(db):
    """user + subject + verified email seed + scan + one source finding."""
    user = User(email=f"pivot-{uuid.uuid4().hex[:8]}@example.org")
    db.add(user)
    db.flush()
    subject = Subject(owner_user_id=user.id)
    db.add(subject)
    db.flush()
    email = Identifier(
        subject_id=subject.id,
        kind=IdentifierKind.EMAIL,
        value_raw=user.email,
        value_normalized=user.email,
        verification_state=VerificationState.VERIFIED,
        verified_at=NOW,
    )
    db.add(email)
    db.flush()
    scan = Scan(requester_user_id=user.id, subject_id=subject.id)
    db.add(scan)
    db.flush()
    finding = _finding(scan.id, subject.id, source="breach_hibp", key="breach:seed",
                       category=FindingCategory.CREDENTIAL, sensitivity=Sensitivity.HIGH,
                       confidence=0.9, identifier_id=email.id)
    db.add(finding)
    db.flush()
    db.commit()
    return {"user": user, "subject": subject, "scan": scan, "email": email, "finding": finding}


def _finding(scan_id, subject_id, *, source, key, category=FindingCategory.SOCIAL,
             sensitivity=Sensitivity.LOW, confidence=0.5, identifier_id=None):
    return Finding(
        scan_id=scan_id,
        subject_id=subject_id,
        identifier_id=identifier_id,
        category=category,
        sensitivity=sensitivity,
        source=source,
        source_name=source,
        captured_at=NOW,
        confidence=confidence,
        summary="fake finding",
        dedupe_key=key,
    )


def _edge(ctx, **over):
    kw = dict(
        scan_id=ctx["scan"].id,
        subject_id=ctx["subject"].id,
        from_finding_id=ctx["finding"].id,
        from_identifier_id=ctx["email"].id,
        derived_identifier_kind=IdentifierKind.USERNAME,
        derived_value_normalized="fake_handle",
        source="websearch",
        source_name="Web Search",
        captured_at=NOW,
        confidence=0.6,
    )
    kw.update(over)
    return PivotLink(**kw)


def test_pivot_link_persists_with_safe_defaults(db, ctx):
    link = _edge(ctx)
    db.add(link)
    db.commit()
    db.refresh(link)
    # A candidate until promoted — never auto-traversed or scored (ADR-0005).
    assert link.status is PivotLinkStatus.PROPOSED
    assert link.hop_depth == 1
    assert link.detail == {}
    assert link.materialized_identifier_id is None


def test_confidence_must_be_in_range(db, ctx):
    db.add(_edge(ctx, confidence=1.5))
    with pytest.raises(IntegrityError):
        db.flush()


def test_hop_depth_must_be_positive(db, ctx):
    db.add(_edge(ctx, hop_depth=0))
    with pytest.raises(IntegrityError):
        db.flush()


def test_edge_must_be_sourced(db, ctx):
    # Sources, not assertions (CLAUDE.md #5): no edge without a source connector.
    db.add(_edge(ctx, source=None))
    with pytest.raises(IntegrityError):
        db.flush()


def test_same_edge_cannot_be_asserted_twice_in_a_scan(db, ctx):
    db.add(_edge(ctx))
    db.flush()
    db.add(_edge(ctx))  # same (scan, from_finding, derived kind+value)
    with pytest.raises(IntegrityError):
        db.flush()


def test_dropping_source_finding_drops_its_edges(db, ctx):
    link = _edge(ctx)
    db.add(link)
    db.commit()
    link_id = link.id
    db.delete(ctx["finding"])
    db.commit()
    # CASCADE — removing the source finding removes its derived edges.
    # Column-level select bypasses the session identity map for a true DB read.
    remaining = db.execute(
        select(PivotLink.id).where(PivotLink.id == link_id)
    ).scalar_one_or_none()
    assert remaining is None


def test_correlation_group_clusters_findings_across_sources(db, ctx):
    gid = uuid.uuid4()
    a = _finding(ctx["scan"].id, ctx["subject"].id, source="broker_detect", key="a")
    b = _finding(ctx["scan"].id, ctx["subject"].id, source="websearch", key="b")
    a.correlation_group_id = gid
    b.correlation_group_id = gid
    db.add_all([a, b])
    db.commit()
    grouped = db.execute(
        select(Finding.id).where(Finding.correlation_group_id == gid)
    ).scalars().all()
    assert set(grouped) == {a.id, b.id}
    # The pre-existing seed finding is not pulled into the group.
    assert ctx["finding"].id not in grouped
