"""Scan job record.

Load-bearing constraints (CLAUDE.md #1): tier and purpose are DB-CHECKed and
TIED — t0 ⇔ self, t1 ⇔ a non-self (consented) purpose (ADR-0007/0008). A scan
can never be recorded as self while targeting someone else. Widening beyond
these tiers is a migration + ADR + counsel review, not a code change.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin
from ayin.models.enums import ScanStatus, ScanTier
from ayin.models.types import str_enum


class Scan(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "scans"
    __table_args__ = (
        # tier ⇔ purpose, enforced in the schema itself: a t0 scan is always
        # 'self'; a t1 (consented) scan is always a non-self purpose. The set of
        # allowed tier VALUES is CHECKed separately by str_enum(ScanTier).
        CheckConstraint(
            "(tier = 't0' AND purpose = 'self') OR (tier = 't1' AND purpose <> 'self')",
            name="tier_purpose",
        ),
        Index("ix_scans_requester_created", "requester_user_id", "created_at"),
    )

    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tier: Mapped[ScanTier] = mapped_column(
        str_enum(ScanTier), nullable=False, default=ScanTier.T0_SELF
    )
    purpose: Mapped[str] = mapped_column(String(64), nullable=False, default="self")
    status: Mapped[ScanStatus] = mapped_column(
        str_enum(ScanStatus), nullable=False, default=ScanStatus.QUEUED
    )
    # Connector ids fanned out to for this scan (versioned source set).
    source_set: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
