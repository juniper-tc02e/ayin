"""Create/consume single-use verification secrets (FR-AUTH-1).

Links carry a random 256-bit URL-safe token; phones get a 6-digit OTP with an
attempt cap. The DB stores sha256(secret) only.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ayin.models import TokenKind, VerificationToken

OTP_MAX_ATTEMPTS = 5


def _sha(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_link_token(
    db: Session,
    *,
    user_id: uuid.UUID,
    kind: TokenKind,
    ttl_minutes: int,
    identifier_id: uuid.UUID | None = None,
) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(
        VerificationToken(
            user_id=user_id,
            identifier_id=identifier_id,
            kind=kind,
            token_hash=_sha(raw),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        )
    )
    db.flush()
    return raw


def create_otp(
    db: Session,
    *,
    user_id: uuid.UUID,
    identifier_id: uuid.UUID,
    ttl_minutes: int,
) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        VerificationToken(
            user_id=user_id,
            identifier_id=identifier_id,
            kind=TokenKind.IDENTIFIER_PHONE_OTP,
            token_hash=_sha(code),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        )
    )
    db.flush()
    return code


def consume_link_token(db: Session, *, raw: str, kind: TokenKind) -> VerificationToken | None:
    """Single-use: marks the token used. None if unknown/expired/already used."""
    row = db.execute(
        select(VerificationToken).where(
            VerificationToken.token_hash == _sha(raw), VerificationToken.kind == kind
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row is None or row.used_at is not None or row.expires_at < now:
        return None
    row.used_at = now
    db.flush()
    return row


def consume_otp(
    db: Session, *, identifier_id: uuid.UUID, code: str
) -> VerificationToken | None:
    """OTP check with attempt counting; None on failure (attempt recorded)."""
    now = datetime.now(timezone.utc)
    row = db.execute(
        select(VerificationToken)
        .where(
            VerificationToken.identifier_id == identifier_id,
            VerificationToken.kind == TokenKind.IDENTIFIER_PHONE_OTP,
            VerificationToken.used_at.is_(None),
        )
        .order_by(VerificationToken.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None or row.expires_at < now or row.attempts >= OTP_MAX_ATTEMPTS:
        return None
    row.attempts += 1
    if row.token_hash != _sha(code):
        db.flush()
        return None
    row.used_at = now
    db.flush()
    return row
