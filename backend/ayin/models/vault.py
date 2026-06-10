"""PII vault tables (M1-5, PRD §10.7).

vault_keys: one wrapped data-encryption key (DEK) per subject. Crypto-shred =
null the wrapped DEK → every item encrypted under it is permanently
unreadable, including in backups of vault_items.

vault_items: AES-GCM ciphertext blobs with mandatory retention expiry.
Plaintext never touches these tables; only ``ayin.vault.store`` reads them.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, LargeBinary, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin


class VaultKey(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "vault_keys"

    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # None after crypto-shred — the point of no return.
    wrapped_dek: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    destroyed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class VaultItem(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "vault_items"

    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Retention is mandatory — nothing lives in the vault indefinitely.
    expires_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
