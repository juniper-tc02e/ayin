"""PivotLink — sourced, candidate linkage edges for the agentic self-scan.

ADR-0005 (S2-1). A finding on one source can yield a NEW, *sourced* fact (a
username → an email → a city) that seeds the next source, so the scan reaches
the long tail of a person's OWN exposure. A ``PivotLink`` is one such edge.

Three invariants are structural, not conventions:

- **Sourced, never invented** (CLAUDE.md #5): every edge carries the connector
  that *asserted* it (``source``) plus ``captured_at`` + ``confidence``. The
  planner may propose *traversing* an edge; it never authors one.
- **Subject-scoped** (CLAUDE.md #1): every edge carries ``subject_id`` and hangs
  off a finding for that subject — there is no path here that links to a third
  party, so T0/self-only is preserved.
- **Candidate until promoted** (FR-ER-1): an edge is a hypothesis. It becomes a
  real seed (``materialized_identifier_id``) only above threshold AND attached
  to the verified subject or user-confirmed; below threshold it stays a
  reviewable candidate and is never auto-traversed. ``hop_depth`` bounds the walk.

Sensitive derived values go to the PII vault via ``vault_ref``;
``derived_value_normalized`` holds the matchable, non-sensitive normalized form
(the same class of operational subject data as a seed Identifier's value).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin
from ayin.models.enums import IdentifierKind, PivotLinkStatus
from ayin.models.types import str_enum


class PivotLink(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "pivot_links"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="pivot_confidence_range"),
        CheckConstraint("hop_depth >= 1", name="pivot_hop_depth_positive"),
        # A connector must not assert the same edge twice within one scan.
        UniqueConstraint(
            "scan_id",
            "from_finding_id",
            "derived_identifier_kind",
            "derived_value_normalized",
            name="uq_pivot_link_edge",
        ),
    )

    scan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The finding that yielded this edge. CASCADE: drop the finding, drop its
    # derived edges (data minimization, mirrors Finding.identifier_id).
    from_finding_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Originating seed provenance, if the source finding traced to one.
    from_identifier_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("identifiers.id", ondelete="SET NULL"), nullable=True
    )

    # The new fact this edge points at.
    derived_identifier_kind: Mapped[IdentifierKind] = mapped_column(
        str_enum(IdentifierKind), nullable=False
    )
    derived_value_normalized: Mapped[str] = mapped_column(String(512), nullable=False)
    # Sensitive raw form (if any) → PII vault, never operational tables (M1-5).
    vault_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Attribution — mandatory (every edge is sourced; CLAUDE.md #5).
    source: Mapped[str] = mapped_column(String(64), nullable=False)  # connector id
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)  # human label
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Bounded traversal (ADR-0005): hops from the seed; the planner respects a cap.
    hop_depth: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    # PROPOSED → MATERIALIZED → CONFIRMED | REJECTED. A candidate edge never
    # auto-traverses or scores until promoted (the human-in-the-loop gate).
    status: Mapped[PivotLinkStatus] = mapped_column(
        str_enum(PivotLinkStatus),
        nullable=False,
        default=PivotLinkStatus.PROPOSED,
        server_default=PivotLinkStatus.PROPOSED.value,
    )
    # The seed this edge became, once materialized (NULL while a candidate).
    materialized_identifier_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("identifiers.id", ondelete="SET NULL"), nullable=True
    )
    # Non-sensitive working notes (planner reasoning ref, threshold detail).
    detail: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
