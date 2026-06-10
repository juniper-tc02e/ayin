"""Encrypted PII vault store (M1-5, PRD §10.7).

Envelope encryption with AES-256-GCM:

    master key (env/KMS) ── wraps ──► per-subject DEK ── encrypts ──► items

Properties:
- **Field-level isolation**: each item is bound (via AEAD associated data) to
  its row id + subject + kind — a ciphertext moved to another row fails auth.
- **Crypto-shred**: destroying a subject's wrapped DEK makes all their items
  permanently unreadable (even in backups); items are also deleted.
- **Retention**: every item carries an expiry; ``purge_expired`` enforces it.
- **Audited**: every successful read writes a data-access audit record;
  stores and shreds write event records.

Master key: ``VAULT_MASTER_KEY`` (32 bytes, base64). In production this comes
from a KMS and is REQUIRED; in dev/test an insecure key is derived from the
app secret with a loud warning.
"""

import base64
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ayin.config import Settings
from ayin.models import VaultItem, VaultKey
from ayin.safety.audit import Actor, record_data_access, record_event, system_actor

log = logging.getLogger("ayin.vault")

NONCE_BYTES = 12
DEK_BYTES = 32


class VaultNotConfigured(RuntimeError):
    pass


class VaultShredded(RuntimeError):
    """The subject's key was destroyed; their old items are gone for good."""


def _master_key(settings: Settings) -> bytes:
    if settings.vault_master_key:
        try:
            key = base64.b64decode(settings.vault_master_key)
        except Exception as exc:
            raise VaultNotConfigured("VAULT_MASTER_KEY is not valid base64") from exc
        if len(key) != DEK_BYTES:
            raise VaultNotConfigured("VAULT_MASTER_KEY must decode to exactly 32 bytes")
        return key
    if settings.is_production:
        raise VaultNotConfigured("VAULT_MASTER_KEY is required in production (KMS-backed)")
    log.warning(
        "vault: deriving a DEV-ONLY master key from APP_SECRET — set VAULT_MASTER_KEY "
        "for anything beyond local development"
    )
    return hashlib.sha256(f"{settings.app_secret}:vault-dev-key".encode()).digest()


class DbVault:
    """The VaultProtocol implementation backed by vault_keys/vault_items."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._master = AESGCM(_master_key(settings))

    # ── key management ───────────────────────────────────────────────
    def _wrap(self, dek: bytes, subject_id: uuid.UUID) -> bytes:
        nonce = os.urandom(NONCE_BYTES)
        return nonce + self._master.encrypt(nonce, dek, str(subject_id).encode())

    def _unwrap(self, wrapped: bytes, subject_id: uuid.UUID) -> bytes:
        nonce, ct = wrapped[:NONCE_BYTES], wrapped[NONCE_BYTES:]
        return self._master.decrypt(nonce, ct, str(subject_id).encode())

    def _get_or_create_dek(self, db: Session, subject_id: uuid.UUID) -> bytes:
        row = db.execute(
            select(VaultKey).where(VaultKey.subject_id == subject_id).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            dek = os.urandom(DEK_BYTES)
            db.add(VaultKey(subject_id=subject_id, wrapped_dek=self._wrap(dek, subject_id)))
            db.flush()
            return dek
        if row.wrapped_dek is None:
            # Key was crypto-shredded. New data after a shred gets a fresh key;
            # the old items are already gone and unrecoverable.
            dek = os.urandom(DEK_BYTES)
            row.wrapped_dek = self._wrap(dek, subject_id)
            row.destroyed_at = None
            db.flush()
            return dek
        return self._unwrap(row.wrapped_dek, subject_id)

    # ── VaultProtocol ────────────────────────────────────────────────
    def put(
        self, db: Session, *, subject_id: uuid.UUID, kind: str, payload: dict,
        retention_days: int | None = None,
    ) -> str:
        dek = self._get_or_create_dek(db, subject_id)
        item_id = uuid.uuid4()
        nonce = os.urandom(NONCE_BYTES)
        aad = f"{item_id}:{subject_id}:{kind}".encode()
        ciphertext = AESGCM(dek).encrypt(
            nonce, json.dumps(payload, default=str).encode(), aad
        )
        days = retention_days or self._settings.pii_retention_days
        db.add(
            VaultItem(
                id=item_id,
                subject_id=subject_id,
                kind=kind,
                nonce=nonce,
                ciphertext=ciphertext,
                expires_at=datetime.now(timezone.utc) + timedelta(days=days),
            )
        )
        record_event(
            db, actor=system_actor("vault"), event_type="vault.stored",
            subject_id=subject_id, detail={"kind": kind, "retention_days": days},
        )
        db.flush()
        return str(item_id)

    def get(
        self, db: Session, *, subject_id: uuid.UUID, ref: str, actor: Actor, purpose: str
    ) -> dict | None:
        try:
            item_id = uuid.UUID(ref)
        except ValueError:
            return None
        item = db.execute(
            select(VaultItem).where(
                VaultItem.id == item_id, VaultItem.subject_id == subject_id
            )
        ).scalar_one_or_none()
        if item is None or item.expires_at < datetime.now(timezone.utc):
            return None
        key_row = db.execute(
            select(VaultKey).where(VaultKey.subject_id == subject_id)
        ).scalar_one_or_none()
        if key_row is None or key_row.wrapped_dek is None:
            return None  # shredded — unreadable forever
        dek = self._unwrap(key_row.wrapped_dek, subject_id)
        aad = f"{item.id}:{subject_id}:{item.kind}".encode()
        try:
            plaintext = AESGCM(dek).decrypt(item.nonce, item.ciphertext, aad)
        except InvalidTag:
            log.error("vault: integrity failure on item %s — refusing to return data", ref)
            return None
        # Every vault read is a subject-data access — audited, no exceptions.
        record_data_access(
            db, actor=actor, subject_id=subject_id, resource=f"vault.{item.kind}",
            purpose=purpose, detail={"ref": ref},
        )
        db.flush()
        return json.loads(plaintext)

    # ── rights + retention ───────────────────────────────────────────
    def shred_subject(self, db: Session, *, subject_id: uuid.UUID, actor: Actor) -> int:
        """Crypto-shred: destroy the subject's DEK and delete their items.
        Returns the number of items destroyed."""
        count = len(
            db.execute(
                select(VaultItem.id).where(VaultItem.subject_id == subject_id)
            ).scalars().all()
        )
        key_row = db.execute(
            select(VaultKey).where(VaultKey.subject_id == subject_id).with_for_update()
        ).scalar_one_or_none()
        if key_row is not None:
            key_row.wrapped_dek = None
            key_row.destroyed_at = datetime.now(timezone.utc)
        db.execute(delete(VaultItem).where(VaultItem.subject_id == subject_id))
        record_event(
            db, actor=actor, event_type="vault.shredded", subject_id=subject_id,
            detail={"items_destroyed": count},
        )
        db.flush()
        return count


def purge_expired(db: Session) -> int:
    """Retention enforcement: hard-delete expired items. Runs on the beat
    schedule (hourly) and is safe to run any time."""
    now = datetime.now(timezone.utc)
    expired = db.execute(
        select(VaultItem.id).where(VaultItem.expires_at < now)
    ).scalars().all()
    if not expired:
        return 0
    db.execute(delete(VaultItem).where(VaultItem.id.in_(expired)))
    record_event(
        db, actor=system_actor("vault.retention"), event_type="vault.purged",
        detail={"items_purged": len(expired)},
    )
    db.commit()
    return len(expired)
