"""The consent FLOW — a usable grant exists ONLY as the product of the subject's
own verified, adult-attested acceptance of a specific requester's ask.

These tests drive request → accept/decline → revoke and assert the orchestrator
gate's verdict flips accordingly, plus the bright-line refusals (no minors, no
self-asserted consent, single-use/expiring link).
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from ayin.config import get_settings
from ayin.consent import flow
from ayin.consent.flow import ConsentFlowError
from ayin.models import Identifier, Scan, Subject, User
from ayin.models.consent import CONSENT_GRANTED, ConsentGrant
from ayin.models.enums import IdentifierKind, VerificationState
from ayin.orchestrator import engine
from ayin.orchestrator.engine import GateDecision

NOW = datetime(2026, 6, 23, tzinfo=timezone.utc)


@pytest.fixture()
def settings():
    return get_settings()


def _requester(db) -> User:
    u = User(email=f"req-{uuid.uuid4().hex[:8]}@example.org", password_hash="x")
    db.add(u)
    db.flush()
    db.commit()
    return u


def _subject_email() -> str:
    return f"subj-{uuid.uuid4().hex[:8]}@example.org"


def _gate(db, settings, requester: User, subject_id) -> object:
    sc = Scan(requester_user_id=requester.id, subject_id=subject_id)
    db.add(sc)
    db.flush()
    db.commit()
    return engine.run_gates(db, sc, settings)


def _grant_subject_id(db, grant_id):
    return db.get(ConsentGrant, grant_id).subject_id


# ── happy path ───────────────────────────────────────────────────────


def test_request_then_accept_mints_usable_consent(db, settings):
    r = _requester(db)
    email = _subject_email()
    req, raw = flow.request_consent(
        db, requester=r, subject_email=email, usernames=["alice_w", "AliceWright"],
        purpose="exec protection", ttl_days=30, now=NOW,
    )
    db.commit()

    # The subject sees the ask via the link.
    assert flow.load_request(db, raw_token=raw, now=NOW).id == req.id

    grant = flow.accept_consent(db, raw_token=raw, adult_attested=True, now=NOW)
    db.commit()

    # A passwordless subject-of-record was created, email VERIFIED, handles seeded.
    subject = db.get(Subject, grant.subject_id)
    owner = db.get(User, subject.owner_user_id)
    assert owner.email == email and owner.password_hash is None
    idents = db.query(Identifier).filter(Identifier.subject_id == subject.id).all()
    email_id = [i for i in idents if i.kind == IdentifierKind.EMAIL]
    assert email_id and email_id[0].verification_state == VerificationState.VERIFIED
    handles = {i.value_normalized for i in idents if i.kind == IdentifierKind.USERNAME}
    assert handles == {"alice_w", "alicewright"}

    # The gate now lets the requester scan this subject.
    res = _gate(db, settings, r, grant.subject_id)
    assert not res.reason.startswith("no_consent")

    # The ask is spent (single-use) and recorded as granted.
    assert flow.load_request(db, raw_token=raw, now=NOW) is None
    db.refresh(req)
    assert req.status == CONSENT_GRANTED and req.grant_id == grant.id


def test_accept_then_revoke_refuses_again(db, settings):
    r = _requester(db)
    _req, raw = flow.request_consent(
        db, requester=r, subject_email=_subject_email(), usernames=["bob"],
        purpose="x", now=NOW,
    )
    db.commit()
    grant = flow.accept_consent(db, raw_token=raw, adult_attested=True, now=NOW)
    db.commit()
    assert not _gate(db, settings, r, grant.subject_id).reason.startswith("no_consent")

    flow.revoke_consent(db, grant=grant, now=NOW)
    db.commit()
    res = _gate(db, settings, r, grant.subject_id)
    assert res.decision == GateDecision.REFUSE and res.reason.startswith("no_consent")


# ── bright-line refusals ─────────────────────────────────────────────


def test_adult_attestation_is_required(db, settings):
    r = _requester(db)
    _req, raw = flow.request_consent(
        db, requester=r, subject_email=_subject_email(), usernames=[], purpose="x", now=NOW,
    )
    db.commit()
    with pytest.raises(ConsentFlowError) as ei:
        flow.accept_consent(db, raw_token=raw, adult_attested=False, now=NOW)
    assert ei.value.code == "adult_attestation_required"
    # Nothing was minted; the ask is still pending.
    db.rollback()
    assert flow.load_request(db, raw_token=raw, now=NOW) is not None


def test_cannot_request_your_own_email(db):
    r = _requester(db)
    with pytest.raises(ConsentFlowError) as ei:
        flow.request_consent(
            db, requester=r, subject_email=r.email.upper(), usernames=[], purpose="x", now=NOW,
        )
    assert ei.value.code == "cannot_request_self"


def test_declined_ask_cannot_be_accepted(db):
    r = _requester(db)
    _req, raw = flow.request_consent(
        db, requester=r, subject_email=_subject_email(), usernames=[], purpose="x", now=NOW,
    )
    db.commit()
    flow.decline_consent(db, raw_token=raw, now=NOW)
    db.commit()
    with pytest.raises(ConsentFlowError) as ei:
        flow.accept_consent(db, raw_token=raw, adult_attested=True, now=NOW)
    assert ei.value.code == "invalid_or_expired"


def test_expired_ask_cannot_be_accepted(db):
    r = _requester(db)
    _req, raw = flow.request_consent(
        db, requester=r, subject_email=_subject_email(), usernames=[], purpose="x", now=NOW,
    )
    db.commit()
    later = NOW + timedelta(days=flow.REQUEST_TTL_DAYS + 1)
    with pytest.raises(ConsentFlowError) as ei:
        flow.accept_consent(db, raw_token=raw, adult_attested=True, now=later)
    assert ei.value.code == "invalid_or_expired"


def test_link_is_single_use(db):
    r = _requester(db)
    _req, raw = flow.request_consent(
        db, requester=r, subject_email=_subject_email(), usernames=[], purpose="x", now=NOW,
    )
    db.commit()
    flow.accept_consent(db, raw_token=raw, adult_attested=True, now=NOW)
    db.commit()
    with pytest.raises(ConsentFlowError) as ei:
        flow.accept_consent(db, raw_token=raw, adult_attested=True, now=NOW)
    assert ei.value.code == "invalid_or_expired"


def test_duplicate_pending_request_is_refused(db):
    r = _requester(db)
    email = _subject_email()
    flow.request_consent(db, requester=r, subject_email=email, usernames=[], purpose="x", now=NOW)
    db.commit()
    with pytest.raises(ConsentFlowError) as ei:
        flow.request_consent(db, requester=r, subject_email=email, usernames=[], purpose="x", now=NOW)
    assert ei.value.code == "already_pending"


def test_per_target_weekly_cap_blocks_repeated_asks(db):
    r = _requester(db)
    email = _subject_email()
    for _ in range(flow.MAX_REQUESTS_PER_TARGET_PER_WEEK):
        _req, raw = flow.request_consent(
            db, requester=r, subject_email=email, usernames=[], purpose="x", now=NOW
        )
        db.commit()
        flow.decline_consent(db, raw_token=raw, now=NOW)  # clear pending for the next ask
        db.commit()
    with pytest.raises(ConsentFlowError) as ei:
        flow.request_consent(db, requester=r, subject_email=email, usernames=[], purpose="x", now=NOW)
    assert ei.value.code == "rate_limited"


def test_per_requester_daily_cap_blocks_email_bomb(db):
    r = _requester(db)
    for i in range(flow.MAX_REQUESTS_PER_DAY):
        flow.request_consent(
            db, requester=r, subject_email=f"t{i}-{uuid.uuid4().hex[:6]}@example.org",
            usernames=[], purpose="x", now=NOW,
        )
        db.commit()
    with pytest.raises(ConsentFlowError) as ei:
        flow.request_consent(
            db, requester=r, subject_email=_subject_email(), usernames=[], purpose="x", now=NOW
        )
    assert ei.value.code == "rate_limited"


def test_accept_attaches_to_existing_user_without_creating_one(db, settings):
    # Subject is already a registered Ayin user.
    email = _subject_email()
    existing = User(email=email, password_hash="real-hash")
    db.add(existing)
    db.flush()
    existing_subject = Subject(owner_user_id=existing.id)
    db.add(existing_subject)
    db.flush()
    db.commit()

    r = _requester(db)
    _req, raw = flow.request_consent(
        db, requester=r, subject_email=email, usernames=["carol"], purpose="x", now=NOW,
    )
    db.commit()
    grant = flow.accept_consent(db, raw_token=raw, adult_attested=True, now=NOW)
    db.commit()

    # Same user, same subject — no duplicate account, password untouched.
    assert grant.subject_id == existing_subject.id
    db.refresh(existing)
    assert existing.password_hash == "real-hash"
    assert db.query(User).filter(User.email == email).count() == 1
