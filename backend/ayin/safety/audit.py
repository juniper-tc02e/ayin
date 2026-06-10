"""Immutable audit log writer (FR-TS-1, BUILD-PLAN M0-6).

Every scan and every access to subject data — including internal/staff
access — goes through these helpers. Properties:

- **Append-only:** a Postgres trigger (migration 0001) rejects UPDATE/DELETE.
- **Tamper-evident:** rows form a sha256 hash chain; ``verify_chain`` detects
  any silent edit (e.g. by someone with raw DB access who disabled the trigger).
- **Atomic with the action:** records are written inside the caller's
  transaction — the action and its audit record commit or roll back together.
  If there is no clean way to write an audit record, that is a bug to surface,
  not skip (CLAUDE.md).

Usage:
    record_scan_event(db, actor=user_actor(user.id), event_type="scan.created",
                      scan_id=scan.id, subject_id=subject.id)
    record_data_access(db, actor=user_actor(user.id), subject_id=subject.id,
                       resource="identifiers", purpose="self-view")
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ayin.models.audit import GENESIS_HASH, AuditRecord
from ayin.models.enums import ActorType

# Serializes chain appends across concurrent transactions (xact-scoped lock:
# released at commit/rollback, so the next writer sees the committed tail).
_AUDIT_CHAIN_LOCK_KEY = 0x41594E_01  # "AYN" + 01


@dataclass(frozen=True)
class Actor:
    type: ActorType
    id: str | None


def user_actor(user_id: uuid.UUID | str) -> Actor:
    return Actor(ActorType.USER, str(user_id))


def system_actor(component: str = "system") -> Actor:
    return Actor(ActorType.SYSTEM, component)


def staff_actor(staff_id: str) -> Actor:
    """Internal access is audited like any other access (CLAUDE.md #7)."""
    return Actor(ActorType.STAFF, staff_id)


def _canonical_payload(rec: dict) -> bytes:
    return json.dumps(rec, sort_keys=True, separators=(",", ":"), default=str).encode()


def _compute_hash(prev_hash: str, payload: dict) -> str:
    return hashlib.sha256(prev_hash.encode() + _canonical_payload(payload)).hexdigest()


def _payload_from_fields(
    *,
    occurred_at: datetime,
    actor_type: str,
    actor_id: str | None,
    event_type: str,
    scan_id: str | None,
    subject_id: str | None,
    resource: str | None,
    purpose: str | None,
    detail: dict,
) -> dict:
    return {
        "occurred_at": occurred_at.isoformat(),
        "actor_type": actor_type,
        "actor_id": actor_id,
        "event_type": event_type,
        "scan_id": scan_id,
        "subject_id": subject_id,
        "resource": resource,
        "purpose": purpose,
        "detail": detail,
    }


def append_audit_record(
    db: Session,
    *,
    actor: Actor,
    event_type: str,
    scan_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    resource: str | None = None,
    purpose: str | None = None,
    detail: dict | None = None,
) -> AuditRecord:
    """Append one record to the hash chain. Low-level — prefer the
    record_* helpers so event types stay consistent."""
    detail = detail or {}
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _AUDIT_CHAIN_LOCK_KEY})
    prev_hash = (
        db.execute(select(AuditRecord.hash).order_by(AuditRecord.id.desc()).limit(1)).scalar()
        or GENESIS_HASH
    )
    occurred_at = datetime.now(timezone.utc)
    payload = _payload_from_fields(
        occurred_at=occurred_at,
        actor_type=actor.type.value,
        actor_id=actor.id,
        event_type=event_type,
        scan_id=str(scan_id) if scan_id else None,
        subject_id=str(subject_id) if subject_id else None,
        resource=resource,
        purpose=purpose,
        detail=detail,
    )
    rec = AuditRecord(
        occurred_at=occurred_at,
        actor_type=actor.type,
        actor_id=actor.id,
        event_type=event_type,
        scan_id=scan_id,
        subject_id=subject_id,
        resource=resource,
        purpose=purpose,
        detail=detail,
        prev_hash=prev_hash,
        hash=_compute_hash(prev_hash, payload),
    )
    db.add(rec)
    db.flush()
    return rec


def record_scan_event(
    db: Session,
    *,
    actor: Actor,
    event_type: str,
    scan_id: uuid.UUID,
    subject_id: uuid.UUID | None = None,
    detail: dict | None = None,
) -> AuditRecord:
    """Scan lifecycle events: scan.created, scan.gated, scan.refused,
    scan.started, scan.completed, scan.failed, scan.held."""
    if not event_type.startswith("scan."):
        raise ValueError("scan events must be namespaced 'scan.*'")
    return append_audit_record(
        db, actor=actor, event_type=event_type, scan_id=scan_id,
        subject_id=subject_id, detail=detail,
    )


def record_data_access(
    db: Session,
    *,
    actor: Actor,
    subject_id: uuid.UUID,
    resource: str,
    purpose: str,
    scan_id: uuid.UUID | None = None,
    detail: dict | None = None,
) -> AuditRecord:
    """Any read of subject data — identifiers, findings, vault contents.
    ``resource`` names what was touched (e.g. 'identifiers', 'findings.credential',
    'vault.<ref>'); ``purpose`` names why (e.g. 'self-view', 'support-case-123')."""
    return append_audit_record(
        db, actor=actor, event_type="data.access", scan_id=scan_id,
        subject_id=subject_id, resource=resource, purpose=purpose, detail=detail,
    )


def record_event(
    db: Session,
    *,
    actor: Actor,
    event_type: str,
    subject_id: uuid.UUID | None = None,
    detail: dict | None = None,
) -> AuditRecord:
    """Other audited events: auth.signup, auth.login, auth.step_up,
    identifier.added, identifier.verified, tos.accepted,
    exclusion.requested, account.delete_requested, ..."""
    return append_audit_record(
        db, actor=actor, event_type=event_type, subject_id=subject_id, detail=detail
    )


def verify_chain(db: Session) -> tuple[bool, int | None]:
    """Recompute the whole chain. Returns (ok, first_bad_record_id)."""
    prev = GENESIS_HASH
    rows = db.execute(select(AuditRecord).order_by(AuditRecord.id.asc())).scalars()
    for rec in rows:
        payload = _payload_from_fields(
            occurred_at=rec.occurred_at,
            actor_type=rec.actor_type.value,
            actor_id=rec.actor_id,
            event_type=rec.event_type,
            scan_id=str(rec.scan_id) if rec.scan_id else None,
            subject_id=str(rec.subject_id) if rec.subject_id else None,
            resource=rec.resource,
            purpose=rec.purpose,
            detail=rec.detail,
        )
        if rec.prev_hash != prev or rec.hash != _compute_hash(prev, payload):
            return False, rec.id
        prev = rec.hash
    return True, None
