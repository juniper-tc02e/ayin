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
from ayin.consent.store import active_consent, record_grant
from ayin.models import Exclusion, Identifier, ProtectionEntry, Scan, Subject, User
from ayin.models.consent import CONSENT_GRANTED, ConsentGrant
from ayin.models.enums import IdentifierKind, VerificationState
from ayin.orchestrator import engine
from ayin.orchestrator.engine import GateDecision
from ayin.safety.hashing import identifier_hash


def _subject_record(db) -> tuple[User, Subject]:
    """A bare subject-of-record (User + Subject) to hang grants on directly."""
    u = User(email=f"su-{uuid.uuid4().hex[:8]}@example.org")
    db.add(u)
    db.flush()
    s = Subject(owner_user_id=u.id)
    db.add(s)
    db.flush()
    db.commit()
    return u, s

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


def _exclude_email(db, email):
    db.add(Exclusion(
        kind="email", value_hash=identifier_hash(IdentifierKind.EMAIL, email), confirmed_at=NOW,
    ))
    db.commit()


def _protect_email(db, email):
    db.add(ProtectionEntry(
        kind="email", value_hash=identifier_hash(IdentifierKind.EMAIL, email),
    ))
    db.commit()


def test_request_to_excluded_subject_is_silently_suppressed(db):
    r = _requester(db)
    email = _subject_email()
    _exclude_email(db, email)
    req, raw = flow.request_consent(
        db, requester=r, subject_email=email, usernames=[], purpose="x", now=NOW
    )
    assert req is None and raw is None  # no row, no email, no reason revealed


def test_request_to_protected_subject_is_silently_suppressed(db):
    r = _requester(db)
    email = _subject_email()
    _protect_email(db, email)
    req, raw = flow.request_consent(
        db, requester=r, subject_email=email, usernames=[], purpose="x", now=NOW
    )
    assert req is None and raw is None


def test_request_with_minor_handle_is_suppressed(db):
    r = _requester(db)
    req, raw = flow.request_consent(
        db, requester=r, subject_email=_subject_email(), usernames=["skater2015"],
        purpose="x", now=NOW,
    )
    assert req is None and raw is None  # birth-year handle → minor signal


def test_accept_refuses_when_subject_excluded_after_request(db):
    r = _requester(db)
    email = _subject_email()
    _req, raw = flow.request_consent(
        db, requester=r, subject_email=email, usernames=[], purpose="x", now=NOW
    )
    db.commit()
    _exclude_email(db, email)  # subject opts out between the ask and accepting
    with pytest.raises(ConsentFlowError) as ei:
        flow.accept_consent(db, raw_token=raw, adult_attested=True, now=NOW)
    assert ei.value.code == "screening_failed"  # grant never minted


def test_accept_attaches_to_existing_user_without_creating_one(db, settings):
    # Subject is already a registered Ayin user.
    email = _subject_email()
    existing = User(email=email, password_hash="real-hash")
    db.add(existing)
    db.flush()
    existing_subject = Subject(owner_user_id=existing.id)
    db.add(existing_subject)
    db.flush()
    # An UNVERIFIED email on the real account, to prove accept doesn't flip it.
    db.add(Identifier(
        subject_id=existing_subject.id, kind=IdentifierKind.EMAIL,
        value_raw=email, value_normalized=email,
    ))
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

    # #3: a PRE-EXISTING real account is NOT mutated via the accept side-door —
    # the requester's proposed handle isn't seeded, and the email isn't verified.
    idents = db.query(Identifier).filter(Identifier.subject_id == existing_subject.id).all()
    assert not any(
        i.kind == IdentifierKind.USERNAME and i.value_normalized == "carol" for i in idents
    )
    email_ids = [i for i in idents if i.kind == IdentifierKind.EMAIL]
    assert email_ids and all(
        i.verification_state != VerificationState.VERIFIED for i in email_ids
    )


def test_revoke_revokes_all_duplicate_grants_for_the_pair(db, settings):
    # Two live grants for the same (subject, requester) — revoking must kill BOTH,
    # or active_consent still returns the survivor and the gate stays open.
    r = _requester(db)
    _su, subject = _subject_record(db)
    g1 = record_grant(db, subject_id=subject.id, requester_user_id=r.id, purpose="x", adult_attested=True)
    g2 = record_grant(db, subject_id=subject.id, requester_user_id=r.id, purpose="x", adult_attested=True)
    db.commit()
    assert active_consent(db, subject_id=subject.id, requester_user_id=r.id) is not None
    n = flow.revoke_consent(db, grant=g1)
    db.commit()
    assert n == 2
    assert active_consent(db, subject_id=subject.id, requester_user_id=r.id) is None
    db.refresh(g2)
    assert g2.revoked_at is not None


def test_revoke_of_expired_grant_is_honest(db):
    # An expired-but-unrevoked row gets revoked_at set (honest trail), not silently
    # skipped.
    r = _requester(db)
    _su, subject = _subject_record(db)
    past = NOW - timedelta(days=40)
    g = record_grant(
        db, subject_id=subject.id, requester_user_id=r.id, purpose="x",
        adult_attested=True, ttl_days=1, now=past,
    )
    db.commit()
    assert g.revoked_at is None
    flow.revoke_consent(db, grant=g, now=NOW)
    db.commit()
    db.refresh(g)
    assert g.revoked_at is not None


def test_subject_revoke_link_token(db, settings):
    # The one-click revoke token minted on accept withdraws consent with no login.
    r = _requester(db)
    _req, raw = flow.request_consent(
        db, requester=r, subject_email=_subject_email(), usernames=["h"], purpose="x", now=NOW,
    )
    db.commit()
    grant = flow.accept_consent(db, raw_token=raw, adult_attested=True, now=NOW)
    raw_revoke = grant.raw_revoke_token
    db.commit()
    assert raw_revoke and grant.revoke_token_hash
    assert not _gate(db, settings, r, grant.subject_id).reason.startswith("no_consent")

    assert flow.revoke_by_token(db, raw_token=raw_revoke, now=NOW) is True
    db.commit()
    res = _gate(db, settings, r, grant.subject_id)
    assert res.decision == GateDecision.REFUSE and res.reason.startswith("no_consent")


def test_revoke_by_unknown_token_is_false(db):
    assert flow.revoke_by_token(db, raw_token="not-a-real-token-xxxxx") is False


def test_purpose_urls_are_stripped(db):
    # A phishing link in the purpose must never reach the subject's inbox / page.
    r = _requester(db)
    req, _ = flow.request_consent(
        db, requester=r, subject_email=_subject_email(), usernames=[],
        purpose="please verify at http://evil.example/login and phish.com/y today",
        now=NOW,
    )
    db.commit()
    low = req.purpose.lower()
    assert "http" not in low and "phish.com" not in low and "evil" not in low
    assert "[link removed]" in req.purpose
