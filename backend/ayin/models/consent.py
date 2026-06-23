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

from sqlalchemy import ForeignKey, Index, String, Uuid
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

    def is_active(self, now: datetime) -> bool:
        return (
            self.revoked_at is None
            and self.adult_attested
            and self.granted_at <= now < self.expires_at
        )
