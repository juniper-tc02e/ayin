"""The consent FLOW — how a subject's verified, affirmative authorization comes
to exist. This is the *only* way a usable :class:`ConsentGrant` is minted.

Shape (consent-first; the subject is always the one who acts):

1. ``request_consent`` — a requester names a subject by email and proposes a
   bounded purpose + handles. A single-use link token is created and returned
   for delivery to that email. Nothing is authorized yet.
2. ``load_request`` — render the pending ask for the subject (the consent page).
3. ``accept_consent`` — the subject, holding the emailed link (which proves
   control of the address) and attesting they are an adult, affirmatively
   authorizes. This mints the grant, verifies the subject's email, and seeds the
   handles the subject confirmed are theirs. Every step is audited.
4. ``decline_consent`` / ``revoke_consent`` — the subject says no, or withdraws
   a live grant; revocation is effective immediately.

There is deliberately NO function that lets a requester self-assert a subject's
consent. The grant is always the product of the subject's own action here.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ayin.consent.store import record_grant, revoke_grant
from ayin.models.consent import (
    CONSENT_DECLINED,
    CONSENT_GRANTED,
    CONSENT_PENDING,
    ConsentGrant,
    ConsentRequest,
)
from ayin.models.enums import IdentifierKind, VerificationState
from ayin.models.subject import Identifier, Subject
from ayin.models.user import User
from ayin.safety.audit import record_event, user_actor
from ayin.services.normalize import IdentifierValidationError, normalize_identifier

REQUEST_TTL_DAYS = 7  # how long the *ask* (the link) stays valid
MAX_USERNAMES = 25  # bound the handles a single request can carry
# Anti-abuse caps (§20.5 "rate-limit it"): a consent request emails an arbitrary
# address with requester-controlled text, so it is a harassment / email-bomb
# vector if unbounded. Cap per-requester volume and re-asks of the same person.
MAX_REQUESTS_PER_DAY = 20  # across all targets, per requester
MAX_REQUESTS_PER_TARGET_PER_WEEK = 3  # re-asking the same person


class ConsentFlowError(ValueError):
    """A consent step could not proceed. ``code`` is a stable machine reason."""

    def __init__(self, code: str, message: str | None = None):
        self.code = code
        super().__init__(message or code)


def _sha(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _clean_usernames(raw_block: str) -> list[str]:
    """Split the newline-joined proposal into a bounded, de-duped list of
    raw handle strings (normalization/validation happens when seeding)."""
    out: list[str] = []
    seen: set[str] = set()
    for line in raw_block.splitlines():
        handle = line.strip()
        key = handle.lower()
        if handle and key not in seen:
            seen.add(key)
            out.append(handle)
        if len(out) >= MAX_USERNAMES:
            break
    return out


# ── 1. Requester asks ────────────────────────────────────────────────


def _enforce_request_limits(
    db: Session, *, requester_id: uuid.UUID, email_norm: str, now: datetime
) -> None:
    """Pure read-only pre-check (no writes) that bounds the email-bomb /
    harassment surface before any row is created. Raises ConsentFlowError."""
    # An already-pending ask to this person — don't re-email them.
    pending = db.execute(
        select(ConsentRequest.id).where(
            ConsentRequest.requester_user_id == requester_id,
            ConsentRequest.subject_email == email_norm,
            ConsentRequest.status == CONSENT_PENDING,
            ConsentRequest.expires_at > now,
        )
    ).first()
    if pending is not None:
        raise ConsentFlowError(
            "already_pending",
            "You already have a pending consent request to this person — "
            "wait for them to respond before sending another.",
        )
    # Re-asking the same person too often is harassment.
    week = db.execute(
        select(func.count(ConsentRequest.id)).where(
            ConsentRequest.requester_user_id == requester_id,
            ConsentRequest.subject_email == email_norm,
            ConsentRequest.created_at >= now - timedelta(days=7),
        )
    ).scalar_one()
    if week >= MAX_REQUESTS_PER_TARGET_PER_WEEK:
        raise ConsentFlowError(
            "rate_limited",
            "You've asked this person several times recently. Please give them "
            "space to respond.",
        )
    # Mass-emailing many targets is an email bomb.
    day = db.execute(
        select(func.count(ConsentRequest.id)).where(
            ConsentRequest.requester_user_id == requester_id,
            ConsentRequest.created_at >= now - timedelta(days=1),
        )
    ).scalar_one()
    if day >= MAX_REQUESTS_PER_DAY:
        raise ConsentFlowError(
            "rate_limited",
            "You've sent the maximum number of consent requests for today.",
        )


def request_consent(
    db: Session,
    *,
    requester: User,
    subject_email: str,
    usernames: list[str],
    purpose: str,
    ttl_days: int = 30,
    now: datetime | None = None,
) -> tuple[ConsentRequest, str]:
    """Create a pending ask and return ``(request, raw_token)``. The caller
    delivers the token via a link to ``subject_email`` (the subject's channel).

    Nothing is authorized by this call — only the subject's later acceptance is.
    """
    now = _now(now)
    purpose = (purpose or "").strip()
    if not purpose:
        raise ConsentFlowError("purpose_required", "A purpose for the scan is required.")
    try:
        _, email_norm = normalize_identifier(IdentifierKind.EMAIL, subject_email)
    except IdentifierValidationError as exc:
        raise ConsentFlowError("invalid_subject_email", str(exc)) from None
    if email_norm == requester.email.lower().strip():
        # Scanning yourself is the self-scan (T0) path; it never needs a grant.
        raise ConsentFlowError(
            "cannot_request_self",
            "That's your own address — scan yourself directly; no consent needed.",
        )
    _enforce_request_limits(db, requester_id=requester.id, email_norm=email_norm, now=now)

    raw = secrets.token_urlsafe(32)
    req = ConsentRequest(
        requester_user_id=requester.id,
        subject_email=email_norm,
        scope_usernames="\n".join(_clean_usernames("\n".join(usernames or []))),
        purpose=purpose[:200],
        ttl_days=max(1, min(int(ttl_days), 365)),
        status=CONSENT_PENDING,
        token_hash=_sha(raw),
        expires_at=now + timedelta(days=REQUEST_TTL_DAYS),
    )
    db.add(req)
    db.flush()
    record_event(
        db,
        actor=user_actor(requester.id),
        event_type="consent.requested",
        detail={"subject_email": email_norm, "purpose": req.purpose, "ttl_days": req.ttl_days},
    )
    return req, raw


def load_request(
    db: Session, *, raw_token: str, now: datetime | None = None
) -> ConsentRequest | None:
    """The still-actionable ask behind a link token, or None (so the consent
    page can show details before the subject decides). Read-only."""
    now = _now(now)
    req = db.execute(
        select(ConsentRequest).where(ConsentRequest.token_hash == _sha(raw_token))
    ).scalar_one_or_none()
    if req is None or req.status != CONSENT_PENDING or req.expires_at < now:
        return None
    return req


# ── 2. Subject decides ───────────────────────────────────────────────


def _subject_for(db: Session, *, email_norm: str) -> tuple[User, Subject, bool]:
    """Find (or create, passwordless) the subject-of-record and their Subject.

    A subject who isn't already an Ayin user is created as a login-less record
    (``password_hash`` stays NULL — they only ever act through consent links).
    Returns ``(user, subject, created)``.
    """
    user = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    created = False
    if user is None:
        user = User(email=email_norm, password_hash=None)
        db.add(user)
        db.flush()
        created = True
    subject = db.execute(
        select(Subject).where(Subject.owner_user_id == user.id)
    ).scalar_one_or_none()
    if subject is None:
        subject = Subject(owner_user_id=user.id)
        db.add(subject)
        db.flush()
    return user, subject, created


def _ensure_email_verified(db: Session, subject: Subject, email_norm: str, now: datetime) -> None:
    ident = db.execute(
        select(Identifier).where(
            Identifier.subject_id == subject.id,
            Identifier.kind == IdentifierKind.EMAIL,
            Identifier.value_normalized == email_norm,
        )
    ).scalar_one_or_none()
    if ident is None:
        ident = Identifier(
            subject_id=subject.id,
            kind=IdentifierKind.EMAIL,
            value_raw=email_norm,
            value_normalized=email_norm,
        )
        db.add(ident)
    ident.verification_state = VerificationState.VERIFIED
    ident.verified_at = now
    db.flush()


def _seed_usernames(db: Session, subject: Subject, raw_block: str) -> None:
    for handle in _clean_usernames(raw_block):
        try:
            value_raw, value_norm = normalize_identifier(IdentifierKind.USERNAME, handle)
        except IdentifierValidationError:
            continue  # skip handles that aren't valid usernames
        exists = db.execute(
            select(Identifier).where(
                Identifier.subject_id == subject.id,
                Identifier.kind == IdentifierKind.USERNAME,
                Identifier.value_normalized == value_norm,
            )
        ).scalar_one_or_none()
        if exists is None:
            db.add(Identifier(
                subject_id=subject.id, kind=IdentifierKind.USERNAME,
                value_raw=value_raw, value_normalized=value_norm,
            ))
    db.flush()


def accept_consent(
    db: Session,
    *,
    raw_token: str,
    adult_attested: bool,
    now: datetime | None = None,
) -> ConsentGrant:
    """The subject's verified, affirmative authorization — mints the grant.

    Holding ``raw_token`` proves the subject controls the email it was sent to;
    ``adult_attested`` must be True (no minors). Verifies the subject's email,
    seeds the confirmed handles, records the grant, and audits the act with the
    *subject* as actor. Raises :class:`ConsentFlowError` if the ask is gone,
    already answered, expired, or adulthood isn't attested.
    """
    now = _now(now)
    req = db.execute(
        select(ConsentRequest).where(ConsentRequest.token_hash == _sha(raw_token))
    ).scalar_one_or_none()
    if req is None or req.status != CONSENT_PENDING or req.expires_at < now:
        raise ConsentFlowError(
            "invalid_or_expired", "This consent link is invalid, used, or expired."
        )
    if not adult_attested:
        # Bright line: Ayin does not scan minors. Without this attestation the
        # subject's authorization is not usable, so we refuse to record it.
        raise ConsentFlowError(
            "adult_attestation_required",
            "You must confirm you are 18 or older to authorize a scan.",
        )

    user, subject, _created = _subject_for(db, email_norm=req.subject_email)
    if subject.owner_user_id == req.requester_user_id:
        raise ConsentFlowError(
            "cannot_consent_to_self", "Requester and subject are the same account."
        )

    _ensure_email_verified(db, subject, req.subject_email, now)
    _seed_usernames(db, subject, req.scope_usernames)

    grant = record_grant(
        db,
        subject_id=subject.id,
        requester_user_id=req.requester_user_id,
        purpose=req.purpose,
        adult_attested=True,
        scope="footprint",
        ttl_days=req.ttl_days,
        verified_via="consent_link",
        now=now,
    )
    req.status = CONSENT_GRANTED
    req.responded_at = now
    req.grant_id = grant.id
    db.flush()
    record_event(
        db,
        actor=user_actor(user.id),  # the SUBJECT is the actor — they authorized
        event_type="consent.granted",
        subject_id=subject.id,
        detail={
            "requester_user_id": str(req.requester_user_id),
            "purpose": req.purpose,
            "scope": grant.scope,
            "expires_at": grant.expires_at.isoformat(),
        },
    )
    return grant


def decline_consent(
    db: Session, *, raw_token: str, now: datetime | None = None
) -> ConsentRequest:
    """The subject says no. Idempotent-ish: only a pending ask can be declined."""
    now = _now(now)
    req = db.execute(
        select(ConsentRequest).where(ConsentRequest.token_hash == _sha(raw_token))
    ).scalar_one_or_none()
    if req is None or req.status != CONSENT_PENDING or req.expires_at < now:
        raise ConsentFlowError("invalid_or_expired", "This consent link is invalid or expired.")
    req.status = CONSENT_DECLINED
    req.responded_at = now
    db.flush()
    record_event(
        db,
        actor=user_actor(req.requester_user_id),
        event_type="consent.declined",
        detail={"subject_email": req.subject_email},
    )
    return req


# ── 3. Subject withdraws ─────────────────────────────────────────────


def revoke_consent(
    db: Session, *, grant: ConsentGrant, now: datetime | None = None
) -> None:
    """Withdraw a live grant — effective immediately (``active_consent`` then
    returns None and the gate refuses again). Audited as the subject's act."""
    now = _now(now)
    revoke_grant(db, grant, now=now)
    owner_id = db.execute(
        select(Subject.owner_user_id).where(Subject.id == grant.subject_id)
    ).scalar_one_or_none()
    record_event(
        db,
        actor=user_actor(owner_id) if owner_id else user_actor(grant.requester_user_id),
        event_type="consent.revoked",
        subject_id=grant.subject_id,
        detail={"requester_user_id": str(grant.requester_user_id)},
    )


def active_grants_for_requester(
    db: Session, *, requester_user_id: uuid.UUID, now: datetime | None = None
) -> list[ConsentGrant]:
    """Live grants a requester currently holds (for their 'authorized subjects'
    view). Ordered newest-expiry first."""
    now = _now(now)
    return list(db.execute(
        select(ConsentGrant)
        .where(
            ConsentGrant.requester_user_id == requester_user_id,
            ConsentGrant.revoked_at.is_(None),
            ConsentGrant.adult_attested.is_(True),
            ConsentGrant.granted_at <= now,
            ConsentGrant.expires_at > now,
        )
        .order_by(ConsentGrant.expires_at.desc())
    ).scalars().all())
