"""Scan job record.

Load-bearing constraints (CLAUDE.md #1): tier and purpose are DB-CHECKed to
the self-scan values. Widening them is a migration + ADR + counsel review,
not a code change.
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
        # MVP is T0 self-scan only — enforced in the schema itself.
        CheckConstraint("tier = 't0'", name="tier_t0_only"),
        CheckConstraint("purpose = 'self'", name="purpose_self_only"),
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
