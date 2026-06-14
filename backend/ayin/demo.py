"""The hackathon demo account — one definition, shared by the local dev rig
(`scripts/demo_server.py`) and the production seed (`scripts/seed_demo.py`).

The account is a **self-scan** subject: a verified email anchor (so the scan
gate passes) plus an aux username (gray-zone "possible match" material). It
only ever scans its own verified identifiers — CLAUDE.md #1 holds in the demo
too. Paired with `DEMO_MODE` the deployment also enables the synthetic
`FakeConnector`, so the judge scan is reproducible with no API keys and no
real person's data on screen.

The password below is a documented public fixture for a throwaway demo
account — it is not a secret (it ships in the testing instructions so judges
can log in).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ayin.auth.passwords import hash_password
from ayin.config import Settings
from ayin.models import Subject, TosAcceptance, User
from ayin.models.enums import IdentifierKind, VerificationState
from ayin.models.subject import Identifier

DEMO_EMAIL = "demo-ayin@example.org"
DEMO_PASSWORD = "ayin-demo-password-1"  # noqa: S105 — public fixture for the demo account
DEMO_USERNAME = "fake_handle"


def seed_demo_account(db: Session, settings: Settings) -> bool:
    """Idempotently create or repair the demo account. Returns True if the
    user was created this call, False if it already existed. Self-healing: it
    re-asserts the verified email anchor, the aux username, and current-ToS
    acceptance every call, so a stray edit (or a ToS version bump) never
    strands the account. Caller commits.
    """
    now = datetime.now(timezone.utc)
    user = db.execute(
        select(User).where(User.email == DEMO_EMAIL)
    ).scalar_one_or_none()
    created = user is None
    if user is None:
        user = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            email_verified_at=now,
        )
        db.add(user)
        db.flush()
        db.add(Subject(owner_user_id=user.id))
        db.flush()

    subject = db.execute(
        select(Subject).where(Subject.owner_user_id == user.id)
    ).scalar_one()
    have = {
        (i.kind, i.value_normalized)
        for i in db.execute(
            select(Identifier).where(Identifier.subject_id == subject.id)
        ).scalars()
    }
    if (IdentifierKind.EMAIL, DEMO_EMAIL) not in have:
        # the verified anchor — without it the scan gate refuses (FR-AUTH-1)
        db.add(Identifier(
            subject_id=subject.id, kind=IdentifierKind.EMAIL,
            value_raw=DEMO_EMAIL, value_normalized=DEMO_EMAIL,
            verification_state=VerificationState.VERIFIED, verified_at=now,
        ))
    if (IdentifierKind.USERNAME, DEMO_USERNAME) not in have:
        # aux seed — surfaces the gray-zone "possible match" for the B4 demo
        db.add(Identifier(
            subject_id=subject.id, kind=IdentifierKind.USERNAME,
            value_raw=DEMO_USERNAME, value_normalized=DEMO_USERNAME,
        ))
    accepted = db.execute(
        select(TosAcceptance.id).where(
            TosAcceptance.user_id == user.id,
            TosAcceptance.version == settings.tos_current_version,
        )
    ).scalar_one_or_none()
    if accepted is None:
        db.add(TosAcceptance(user_id=user.id, version=settings.tos_current_version))
    db.flush()
    return created
