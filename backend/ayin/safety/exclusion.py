""""Exclude me from Ayin" — public self-exclusion flow (FR-TS-3, M3-4).

Flow: request (email only in MVP) → confirmation link to the address itself
(possession = proof of control) → confirmed exclusion:
- cached data purged: matching seed Identifiers are deleted, which cascades
  their findings (data minimization)
- honored on all future scans: the orchestrator's seed-selection chokepoint
  drops excluded identifiers, and a subject whose only verified anchor is
  excluded is refused with reason "subject_excluded"

Privacy posture: responses are identical whether or not an address was
already excluded (no membership oracle); audits record the KIND only, never
the value; the table stores hashes only.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ayin.config import Settings
from ayin.models import Identifier
from ayin.models.enums import IdentifierKind
from ayin.models.exclusion import Exclusion
from ayin.safety.audit import record_event, system_actor
from ayin.safety.hashing import identifier_hash
from ayin.services.email import EmailSender
from ayin.services.normalize import IdentifierValidationError, normalize_identifier

log = logging.getLogger("ayin.safety.exclusion")

TOKEN_TTL_MINUTES = 60 * 24
RESEND_COOLDOWN_MINUTES = 20  # anti-email-bombing


class ExclusionError(ValueError):
    pass


def _sha(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def request_exclusion(
    db: Session, settings: Settings, sender: EmailSender, *, kind: str, value: str
) -> None:
    """Always 'succeeds' from the caller's perspective (no membership oracle).
    Sends a confirmation link unless cooldown/already-confirmed applies."""
    if kind != IdentifierKind.EMAIL.value:
        raise ExclusionError(
            "Only email exclusion is self-service right now. For other "
            "identifiers, contact privacy@ayin.example."
        )
    try:
        _, normalized = normalize_identifier(IdentifierKind.EMAIL, value)
    except IdentifierValidationError as exc:
        raise ExclusionError(str(exc)) from None

    value_hash = identifier_hash(IdentifierKind.EMAIL, normalized)
    now = datetime.now(timezone.utc)
    row = db.execute(
        select(Exclusion).where(Exclusion.value_hash == value_hash)
    ).scalar_one_or_none()

    if row is not None and row.confirmed_at is not None:
        record_event(db, actor=system_actor("exclusion"), event_type="exclusion.requested",
                     detail={"kind": kind, "state": "already_confirmed"})
        db.commit()
        return  # identical outward behavior
    if row is not None and row.last_requested_at is not None and (
        now - row.last_requested_at < timedelta(minutes=RESEND_COOLDOWN_MINUTES)
    ):
        db.commit()
        return  # cooldown: no email storm

    raw_token = secrets.token_urlsafe(32)
    if row is None:
        row = Exclusion(kind=kind, value_hash=value_hash)
        db.add(row)
    row.token_hash = _sha(raw_token)
    row.token_expires_at = now + timedelta(minutes=TOKEN_TTL_MINUTES)
    row.last_requested_at = now
    db.flush()

    link = f"{settings.web_base_url}/exclude/confirm?token={raw_token}"
    sender.send(
        to=normalized,
        subject="Confirm: exclude this address from Ayin",
        body=(
            "Someone (hopefully you) asked Ayin to permanently exclude this "
            "email address from being scanned — by anyone, including themselves.\n\n"
            f"Confirm the exclusion: {link}\n\n"
            "If you didn't request this, you can ignore it; nothing changes "
            "without this confirmation. Note: exclusion is currently permanent "
            "and also removes any existing scan data tied to this address."
        ),
    )
    record_event(db, actor=system_actor("exclusion"), event_type="exclusion.requested",
                 detail={"kind": kind})
    db.commit()


def confirm_exclusion(db: Session, raw_token: str) -> dict:
    """Marks the exclusion confirmed + purges cached data. Returns counts."""
    now = datetime.now(timezone.utc)
    row = db.execute(
        select(Exclusion).where(Exclusion.token_hash == _sha(raw_token))
    ).scalar_one_or_none()
    if row is None or row.token_expires_at is None or row.token_expires_at < now:
        raise ExclusionError("Invalid or expired confirmation link.")
    row.confirmed_at = row.confirmed_at or now
    row.token_hash = None
    row.token_expires_at = None

    purged_identifiers = _purge_matching_identifiers(db, row)
    record_event(
        db, actor=system_actor("exclusion"), event_type="exclusion.confirmed",
        detail={"kind": row.kind, "identifiers_purged": purged_identifiers},
    )
    db.commit()
    return {"identifiers_purged": purged_identifiers}


def _purge_matching_identifiers(db: Session, row: Exclusion) -> int:
    """Delete seed identifiers matching the exclusion (cascades their
    findings — purge of cached data). MVP scans rows of the kind and
    hash-compares; a keyed-hash index column is the Phase-1 upgrade."""
    candidates = db.execute(
        select(Identifier).where(Identifier.kind == IdentifierKind(row.kind))
    ).scalars().all()
    purged = 0
    for ident in candidates:
        if identifier_hash(ident.kind, ident.value_normalized) == row.value_hash:
            db.delete(ident)
            purged += 1
    db.flush()
    return purged


def excluded_hashes(db: Session, hashes: list[str]) -> set[str]:
    """Which of these identifier hashes are confirmed-excluded?"""
    if not hashes:
        return set()
    rows = db.execute(
        select(Exclusion.value_hash).where(
            Exclusion.value_hash.in_(hashes), Exclusion.confirmed_at.is_not(None)
        )
    ).scalars()
    return set(rows)


def split_excluded(
    db: Session, identifiers: list[Identifier]
) -> tuple[list[Identifier], list[Identifier]]:
    """(allowed, excluded) partition of seed identifiers."""
    by_hash = {identifier_hash(i.kind, i.value_normalized): i for i in identifiers}
    excluded = excluded_hashes(db, list(by_hash))
    allowed_list = [i for h, i in by_hash.items() if h not in excluded]
    excluded_list = [i for h, i in by_hash.items() if h in excluded]
    return allowed_list, excluded_list

