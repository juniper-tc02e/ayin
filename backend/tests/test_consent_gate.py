"""Consent gate (T1) — the structural enforcement that Ayin NEVER scans a
non-consenting third party.

A scan where the requester is not the subject's owner is REFUSED unless that
subject has a live ConsentGrant for the requester. Exclude-me always wins; the
grant must be verified, current, unrevoked, and adult-attested.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from ayin.config import get_settings
from ayin.consent.store import record_grant, revoke_grant
from ayin.models import Identifier, Scan, Subject, User
from ayin.models.enums import IdentifierKind, VerificationState
from ayin.orchestrator import engine
from ayin.orchestrator.engine import GateDecision


@pytest.fixture()
def settings():
    return get_settings()


def _person(db, *, excluded=False) -> tuple[User, Subject]:
    """A user with their own Subject + a VERIFIED email anchor (so the only
    thing the consent gate decides is the requester≠owner question)."""
    now = datetime.now(timezone.utc)
    u = User(email=f"c-{uuid.uuid4().hex[:8]}@example.org")
    db.add(u)
    db.flush()
    s = Subject(owner_user_id=u.id, exclusion_state="excluded" if excluded else "none")
    db.add(s)
    db.flush()
    db.add(Identifier(
        subject_id=s.id, kind=IdentifierKind.EMAIL,
        value_raw=u.email, value_normalized=u.email,
        verification_state=VerificationState.VERIFIED, verified_at=now,
    ))
    db.flush()
    db.commit()
    return u, s


def _scan(db, requester: User, subject: Subject) -> Scan:
    sc = Scan(requester_user_id=requester.id, subject_id=subject.id)
    db.add(sc)
    db.flush()
    db.commit()
    return sc


def _grant(db, subject, requester, **kw):
    g = record_grant(
        db, subject_id=subject.id, requester_user_id=requester.id,
        purpose=kw.pop("purpose", "exec protection"),
        adult_attested=kw.pop("adult_attested", True), **kw,
    )
    db.commit()
    return g


def test_self_scan_needs_no_consent(db, settings):
    user, subject = _person(db)
    res = engine.run_gates(db, _scan(db, user, subject), settings)
    assert not res.reason.startswith("no_consent")  # self-scan (T0) unaffected


def test_third_party_scan_without_consent_is_refused(db, settings):
    requester, _ = _person(db)
    _su, subject = _person(db)
    res = engine.run_gates(db, _scan(db, requester, subject), settings)
    assert res.decision == GateDecision.REFUSE
    assert res.reason.startswith("no_consent")


def test_third_party_scan_with_valid_consent_clears_the_consent_gate(db, settings):
    requester, _ = _person(db)
    _su, subject = _person(db)
    _grant(db, subject, requester)
    res = engine.run_gates(db, _scan(db, requester, subject), settings)
    # The consent gate let it through (other gates may still apply, but the
    # no-consent refusal must NOT fire).
    assert not res.reason.startswith("no_consent")


def test_revoked_consent_is_refused(db, settings):
    requester, _ = _person(db)
    _su, subject = _person(db)
    g = _grant(db, subject, requester)
    revoke_grant(db, g)
    db.commit()
    res = engine.run_gates(db, _scan(db, requester, subject), settings)
    assert res.decision == GateDecision.REFUSE and res.reason.startswith("no_consent")


def test_expired_consent_is_refused(db, settings):
    requester, _ = _person(db)
    _su, subject = _person(db)
    past = datetime.now(timezone.utc) - timedelta(days=3)
    _grant(db, subject, requester, ttl_days=1, now=past)  # expired a day ago
    res = engine.run_gates(db, _scan(db, requester, subject), settings)
    assert res.decision == GateDecision.REFUSE and res.reason.startswith("no_consent")


def test_non_adult_attested_consent_is_not_usable(db, settings):
    requester, _ = _person(db)
    _su, subject = _person(db)
    _grant(db, subject, requester, adult_attested=False)  # no minors
    res = engine.run_gates(db, _scan(db, requester, subject), settings)
    assert res.decision == GateDecision.REFUSE and res.reason.startswith("no_consent")


def test_excluded_subject_refused_even_with_consent(db, settings):
    requester, _ = _person(db)
    _su, subject = _person(db, excluded=True)
    _grant(db, subject, requester)
    res = engine.run_gates(db, _scan(db, requester, subject), settings)
    assert res.decision == GateDecision.REFUSE
    assert res.reason == "subject_excluded"  # exclude-me wins over consent


def test_consent_is_requester_specific(db, settings):
    """Subject grants requester R1; a different requester R2 still can't scan."""
    r1, _ = _person(db)
    r2, _ = _person(db)
    _su, subject = _person(db)
    _grant(db, subject, r1)
    res = engine.run_gates(db, _scan(db, r2, subject), settings)
    assert res.decision == GateDecision.REFUSE and res.reason.startswith("no_consent")
