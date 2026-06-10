"""AuditRecord — the spine of trust & compliance (FR-TS-1, CLAUDE.md #7).

Append-only and tamper-evident:
- a Postgres trigger (migration 0001) rejects UPDATE and DELETE outright;
- rows form a sha256 hash chain (prev_hash → hash) written by
  ``ayin.safety.audit`` (M0-6), so silent tampering breaks verification;
- BIGSERIAL id gives a total order for chain verification.

Every scan and every access to subject data — including internal/staff
access — writes a record. There is intentionally no ORM ``update`` path here.
"""

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import BigInteger, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base
from ayin.models.enums import ActorType
from ayin.models.types import str_enum

GENESIS_HASH = "0" * 64


class AuditRecord(Base):
    __tablename__ = "audit_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    actor_type: Mapped[ActorType] = mapped_column(str_enum(ActorType), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Namespaced event types, e.g. auth.signup, scan.created, data.access,
    # identifier.verified, tos.accepted, vault.read, exclusion.requested.
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scan_id: Mapped[uuid_mod.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    subject_id: Mapped[uuid_mod.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    # What data was touched (for data.access events), e.g. "identifiers", "findings.credential".
    resource: Mapped[str | None] = mapped_column(String(128), nullable=True)
    purpose: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
