"""Public exclusion list — "Exclude me from Ayin" (FR-TS-3, M3-4).

Anyone (user or not) can verify control of an identifier and have Ayin
permanently refuse to scan it. Only sha256("{kind}:{normalized}") is stored:
the exclusion list must never itself become a directory of people who asked
not to be looked at. Pending rows carry a hashed confirmation token.
"""

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin


class Exclusion(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "exclusions"

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    value_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # Confirmation-link token (hashed); cleared semantics: row counts only
    # once confirmed_at is set.
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Anti-email-bombing: requests in the current window.
    last_requested_at: Mapped[datetime | None] = mapped_column(nullable=True)
