"""M0-2 acceptance tests.

- migrations apply cleanly (session fixture would fail otherwise);
- every Finding requires source, captured_at, confidence, sensitivity;
- Identifier has a verification_state (default: unverified);
- Scan tier/purpose are DB-locked to self-scan (CLAUDE.md #1).

All data is clearly fake.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from ayin.models import Finding, Identifier, Scan, Score, Subject, User
from ayin.models.enums import FindingCategory, IdentifierKind, Sensitivity, VerificationState

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _user(db, email=None) -> User:
    u = User(email=email or f"fake-{uuid.uuid4().hex[:8]}@example.invalid")
    db.add(u)
    db.flush()
    return u


def _subject(db, user: User) -> Subject:
    s = Subject(owner_user_id=user.id)
    db.add(s)
    db.flush()
    return s


def _scan(db, user: User, subject: Subject) -> Scan:
    sc = Scan(requester_user_id=user.id, subject_id=subject.id)
    db.add(sc)
    db.flush()
    return sc


def _finding_kwargs(scan: Scan, subject: Subject, **overrides) -> dict:
    base = dict(
        scan_id=scan.id,
        subject_id=subject.id,
        category=FindingCategory.CREDENTIAL,
        sensitivity=Sensitivity.HIGH,
        source="fake_connector",
        source_name="Fake Source (fixture)",
        captured_at=NOW,
        confidence=0.9,
        summary="Clearly-fake fixture finding.",
        dedupe_key="fake:1",
    )
    base.update(overrides)
    return base


def test_all_core_tables_exist(engine):
    tables = set(inspect(engine).get_table_names())
    expected = {
        "users",
        "subjects",
        "identifiers",
        "scans",
        "findings",
        "scores",
        "remediation_tasks",
        "audit_records",
        "abuse_signals",
    }
    assert expected <= tables


@pytest.mark.parametrize("missing", ["source", "captured_at", "confidence", "sensitivity"])
def test_finding_requires_full_attribution(db, missing):
    """No mystery data: a Finding without attribution must be unstorable."""
    u = _user(db)
    s = _subject(db, u)
    sc = _scan(db, u, s)
    kwargs = _finding_kwargs(sc, s, **{missing: None})
    db.add(Finding(**kwargs))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_finding_confidence_must_be_probability(db):
    u = _user(db)
    s = _subject(db, u)
    sc = _scan(db, u, s)
    db.add(Finding(**_finding_kwargs(sc, s, confidence=1.5)))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_identifier_defaults_to_unverified(db):
    u = _user(db)
    s = _subject(db, u)
    ident = Identifier(
        subject_id=s.id,
        kind=IdentifierKind.EMAIL,
        value_raw="Fake.Person@Example.Invalid",
        value_normalized="fake.person@example.invalid",
    )
    db.add(ident)
    db.flush()
    assert ident.verification_state == VerificationState.UNVERIFIED
    assert ident.verified_at is None


def test_identifier_rejects_bogus_verification_state(db, engine):
    u = _user(db)
    s = _subject(db, u)
    db.commit()
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO identifiers "
                "(id, subject_id, kind, value_raw, value_normalized, "
                "verification_state, confidence) "
                "VALUES (:id, :sid, 'email', 'x@example.invalid', 'x@example.invalid', "
                "'totally-verified-trust-me', 1.0)"
            ),
            {"id": str(uuid.uuid4()), "sid": str(s.id)},
        )


def test_scan_tier_is_locked_to_t0_in_the_schema(db, engine):
    """CLAUDE.md #1: no third-party scanning — even a buggy code path can't
    write a non-T0 scan, because the DB refuses it."""
    u = _user(db)
    s = _subject(db, u)
    db.commit()
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO scans "
                "(id, requester_user_id, subject_id, tier, purpose, status, source_set) "
                "VALUES (:id, :uid, :sid, 't2', 'self', 'queued', '[]')"
            ),
            {"id": str(uuid.uuid4()), "uid": str(u.id), "sid": str(s.id)},
        )


def test_scan_purpose_is_locked_to_self(db, engine):
    u = _user(db)
    s = _subject(db, u)
    db.commit()
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO scans "
                "(id, requester_user_id, subject_id, tier, purpose, status, source_set) "
                "VALUES (:id, :uid, :sid, 't0', 'tenant-screening', 'queued', '[]')"
            ),
            {"id": str(uuid.uuid4()), "uid": str(u.id), "sid": str(s.id)},
        )


def test_score_is_bounded_0_100(db):
    u = _user(db)
    s = _subject(db, u)
    sc = _scan(db, u, s)
    db.add(Score(scan_id=sc.id, subject_id=s.id, overall=150, rubric_version="v0"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_duplicate_finding_within_scan_rejected(db):
    u = _user(db)
    s = _subject(db, u)
    sc = _scan(db, u, s)
    db.add(Finding(**_finding_kwargs(sc, s)))
    db.flush()
    db.add(Finding(**_finding_kwargs(sc, s)))  # same dedupe_key, same scan
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
