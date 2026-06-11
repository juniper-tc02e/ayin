"""Victim-protection list (FR-SCAN-5, M3-3).

Staff-curated entries for at-risk people whose identifiers must trigger a
manual-review HOLD if they ever appear as scan seeds. Only a salted-format
hash of the normalized value is stored — the list must never itself become
a directory of at-risk people. Staff tooling lands Phase 1; entries are
inserted operationally for now.
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin


class ProtectionEntry(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "protection_entries"

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # sha256("{kind}:{normalized_value}") — see ayin.safety.hashing
    value_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # Internal context for reviewers ONLY (case ref, never the value/person).
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
