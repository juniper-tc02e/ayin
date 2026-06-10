"""Vault protocol + the pre-M1-5 NullVault.

The orchestrator never writes a sensitive payload anywhere except through
this interface. NullVault *refuses to store* (drops + logs) rather than
falling back to plaintext — failing closed is the point.
"""

import logging
import uuid
from typing import Protocol

from sqlalchemy.orm import Session

from ayin.safety.audit import Actor

log = logging.getLogger("ayin.vault")


class VaultProtocol(Protocol):
    def put(
        self, db: Session, *, subject_id: uuid.UUID, kind: str, payload: dict,
        retention_days: int | None = None,
    ) -> str | None:
        """Store an encrypted payload; return a vault ref (or None if refused)."""
        ...

    def get(
        self, db: Session, *, subject_id: uuid.UUID, ref: str, actor: Actor, purpose: str
    ) -> dict | None:
        """Decrypt and return a payload; ALWAYS writes an audit record."""
        ...


class NullVault:
    """Refuses storage (logs a warning). Used until the encrypted store ships;
    sensitive payloads are dropped, never persisted in the clear."""

    def put(self, db, *, subject_id, kind, payload, retention_days=None) -> str | None:
        log.warning(
            "NullVault: dropping sensitive payload kind=%s for subject %s "
            "(encrypted vault not configured)", kind, subject_id,
        )
        return None

    def get(self, db, *, subject_id, ref, actor, purpose) -> dict | None:
        return None
