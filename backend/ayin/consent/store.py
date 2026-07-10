"""Consent-grant storage + validity — the single source of truth.

``active_consent`` is the ONLY place the gate asks "may this requester scan this
subject?". Never inline a partial check elsewhere.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ayin.models.consent import ConsentGrant


def active_consent(
    db: Session,
    *,
    subject_id: uuid.UUID,
    requester_user_id: uuid.UUID,
    now: datetime | None = None,
) -> ConsentGrant | None:
    """The requester's currently-valid consent to scan the subject, or None.

    Valid = not revoked, not expired, adult-attested, already-effective. The
    orchestrator gate calls this for any non-self scan; None ⇒ refuse.
    """
    now = now or datetime.now(timezone.utc)
    return db.execute(
        select(ConsentGrant)
        .where(
            ConsentGrant.subject_id == subject_id,
            ConsentGrant.requester_user_id == requester_user_id,
            ConsentGrant.revoked_at.is_(None),
            ConsentGrant.adult_attested.is_(True),
            ConsentGrant.granted_at <= now,
            ConsentGrant.expires_at > now,
        )
        .order_by(ConsentGrant.expires_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def record_grant(
    db: Session,
    *,
    subject_id: uuid.UUID,
    requester_user_id: uuid.UUID,
    purpose: str,
    adult_attested: bool,
    scope: str = "footprint",
    ttl_days: int = 30,
    verified_via: str = "link_token",
    now: datetime | None = None,
) -> ConsentGrant:
    """Record a consent the SUBJECT has already affirmatively, verifiably given.

    This does NOT itself verify the subject — the caller (the ``ayin.consent``
    flow, driven by the subject's own channel) must have proven the affirmative
    action first. ``adult_attested`` must be True for the grant to be usable.
    """
    now = now or datetime.now(timezone.utc)
    grant = ConsentGrant(
        subject_id=subject_id,
        requester_user_id=requester_user_id,
        purpose=purpose[:200],
        scope=scope[:64],
        granted_at=now,
        expires_at=now + timedelta(days=max(1, min(ttl_days, 365))),
        adult_attested=bool(adult_attested),
        verified_via=verified_via[:40],
    )
    db.add(grant)
    db.flush()
    return grant


def revoke_grant(db: Session, grant: ConsentGrant, *, now: datetime | None = None) -> None:
    """Subject revokes ONE grant — effective immediately. Prefer
    ``revoke_all_active`` at call sites so a duplicate live grant can't survive a
    revoke (audit finding: revoking one grant_id left a sibling active)."""
    if grant.revoked_at is None:
        grant.revoked_at = now or datetime.now(timezone.utc)
        db.flush()


def revoke_all_active(
    db: Session,
    *,
    subject_id: uuid.UUID,
    requester_user_id: uuid.UUID,
    now: datetime | None = None,
) -> list[ConsentGrant]:
    """Revoke EVERY not-yet-revoked grant for this (subject, requester) pair —
    the honest revoke. Targets ``revoked_at IS NULL`` regardless of expiry, so an
    expired-but-unrevoked row is also honestly closed, and duplicate live grants
    can't leave the pair still-authorized after a revoke. Returns the rows it
    revoked (possibly empty)."""
    now = now or datetime.now(timezone.utc)
    grants = list(db.execute(
        select(ConsentGrant).where(
            ConsentGrant.subject_id == subject_id,
            ConsentGrant.requester_user_id == requester_user_id,
            ConsentGrant.revoked_at.is_(None),
        )
    ).scalars().all())
    for g in grants:
        g.revoked_at = now
    if grants:
        db.flush()
    return grants
