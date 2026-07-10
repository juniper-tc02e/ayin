"""Consent grants for authorized third-party scans (T1+, PRD §20.5).

A scan of a subject who is NOT the requester's own self is REFUSED by the
orchestrator gate (``run_gates``) unless that subject has granted the requester
a verified, unexpired, unrevoked ``ConsentGrant``. The grant is created ONLY by
the subject's own verified action (``ayin.consent`` flow) — never by the
requester self-asserting it. Self-scan (T0) never needs one.

This row is the structural enforcement of CLAUDE.md #1 for the consented tier:
Ayin never scans a non-consenting person. The grant is time-bound, revocable,
scoped, adult-attested, and every use is audited.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin


class ConsentGrant(Base, UuidPkMixin, CreatedAtMixin):
    """One subject's authorization for one requester to scan them.

    Validity (all required): ``revoked_at`` is null, ``granted_at <= now <
    expires_at``, and ``adult_attested`` is true. ``active_consent`` in
    ``ayin.consent.store`` is the single source of that truth — never inline
    a partial check at a call site.
    """

    __tablename__ = "consent_grants"
    __table_args__ = (
        Index("ix_consent_subject_requester", "subject_id", "requester_user_id"),
    )

    # The person being scanned (their own Subject). FK cascade: if the subject
    # deletes their account, their consents vanish with them.
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    # Who is authorized to scan the subject.
    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Bounded purpose + scope the subject authorized (purpose-binding, §20.5).
    purpose: Mapped[str] = mapped_column(String(200), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, default="footprint")
    # When the subject affirmatively granted (via their own verified channel).
    granted_at: Mapped[datetime] = mapped_column(nullable=False)
    # Time-bound: a grant always expires; the subject sets/accepts the window.
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    # Revocable any time by the subject.
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # The subject attested they are 18+ (no minors — CLAUDE.md / ToS).
    adult_attested: Mapped[bool] = mapped_column(nullable=False, default=False)
    # How the subject's affirmative action was proven (e.g. "link_token").
    verified_via: Mapped[str] = mapped_column(String(40), nullable=False, default="link_token")
    # sha256 of a single-use revoke token emailed to the subject on accept, so a
    # login-less subject (no account, no password) can still withdraw consent with
    # one click — the raw token is never stored. Null on legacy/self-scan rows.
    revoke_token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )

    def is_active(self, now: datetime) -> bool:
        return (
            self.revoked_at is None
            and self.adult_attested
            and self.granted_at <= now < self.expires_at
        )


# Request statuses.
CONSENT_PENDING = "pending"
CONSENT_GRANTED = "granted"
CONSENT_DECLINED = "declined"
CONSENT_EXPIRED = "expired"


class ConsentRequest(Base, UuidPkMixin, CreatedAtMixin):
    """A requester's pending *ask* for a subject's consent — NOT authorization.

    The requester names the subject by email and proposes a bounded purpose +
    handles to scan. A link carrying a single-use token is sent to that email;
    possession of the link proves the subject controls the address (same basis
    as identifier email-verification). The subject reviews the ask and either
    accepts — which mints a :class:`ConsentGrant` via the subject's own action —
    or declines. This row holds the ask only; it grants nothing on its own, and
    the orchestrator gate never consults it.
    """

    __tablename__ = "consent_requests"
    __table_args__ = (
        Index("ix_consent_req_token", "token_hash"),
        Index("ix_consent_req_subject_email", "subject_email"),
    )

    # Who is asking.
    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The subject's own email — the channel the ask is delivered to (normalized).
    subject_email: Mapped[str] = mapped_column(String(320), nullable=False)
    # Handles the requester proposes to scan, newline-joined (the subject is
    # confirming these are theirs by accepting). Bounded at accept time.
    scope_usernames: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Bounded purpose the subject is being asked to authorize.
    purpose: Mapped[str] = mapped_column(String(200), nullable=False)
    # Window the resulting grant should last, in days.
    ttl_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    # pending | granted | declined | expired.
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=CONSENT_PENDING)
    # True when the target was excluded/protected/minor: the row is created and
    # counts toward rate limits (so the endpoint response is indistinguishable
    # from a normal ask — no protection-list oracle), but NO email is sent and it
    # can NEVER be accepted. See flow.request_consent / accept_consent.
    screened: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    # sha256 of the single-use link token (raw token is emailed, never stored).
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # When the *ask* itself expires (distinct from the grant's own window).
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    # When the subject accepted/declined.
    responded_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # The grant minted on accept (audit linkage).
    grant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("consent_grants.id", ondelete="SET NULL"), nullable=True
    )
