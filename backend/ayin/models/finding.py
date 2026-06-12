"""Finding, Score, RemediationTask.

Sources, not assertions (CLAUDE.md #5): a Finding cannot exist without
source + captured_at + confidence + sensitivity — enforced NOT NULL/CHECK
at the schema level, not just in code.

Sensitive payloads (e.g. which data classes leaked for a credential) go to
the PII vault (M1-5) via ``vault_ref``; ``payload`` holds only non-sensitive
normalized detail. Never store full plaintext credentials anywhere (FR-DISC-1).
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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin
from ayin.models.enums import (
    FindingCategory,
    FindingState,
    MatchStatus,
    RemediationStatus,
    RemediationType,
    Sensitivity,
)
from ayin.models.types import str_enum


class Finding(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint(
            "exploitability IS NULL OR (exploitability >= 0 AND exploitability <= 1)",
            name="exploitability_range",
        ),
        # A connector must not emit the same finding twice within one scan.
        UniqueConstraint("scan_id", "dedupe_key", name="uq_finding_scan_dedupe"),
    )

    scan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Which seed identifier produced this finding (NULL = derived/cross-seed).
    # CASCADE: removing a seed removes its findings — data minimization.
    # Gate: findings keyed to an UNVERIFIED identifier are never shown
    # (ayin.safety.visibility, FR-AUTH-1).
    identifier_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("identifiers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    category: Mapped[FindingCategory] = mapped_column(str_enum(FindingCategory), nullable=False)
    sensitivity: Mapped[Sensitivity] = mapped_column(str_enum(Sensitivity), nullable=False)
    # Attribution — mandatory (no mystery data).
    source: Mapped[str] = mapped_column(String(64), nullable=False)  # connector id
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)  # human label
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    exploitability: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[FindingState] = mapped_column(
        str_enum(FindingState), nullable=False, default=FindingState.ACTIVE
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)  # plain-language, non-sensitive
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    vault_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(256), nullable=False)

    # ── Resolution (M2-1/M2-2) ───────────────────────────────────────
    # New findings start POSSIBLE; resolution promotes/demotes; the user's
    # confirm/reject is final and survives re-resolution (FR-ER-1).
    match_status: Mapped[MatchStatus] = mapped_column(
        str_enum(MatchStatus),
        nullable=False,
        default=MatchStatus.POSSIBLE,
        server_default=MatchStatus.POSSIBLE.value,
    )
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Distinct sources that corroborate this exposure (≥1; set by dedupe).
    corroboration_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    # Duplicate collapse (M2-2): suppressed duplicates point at their primary;
    # the primary preserves every contributing source in merged_sources.
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("findings.id", ondelete="SET NULL"), nullable=True
    )
    merged_sources: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    # Resolution working notes: match reasons, flagged conflicts (never
    # silently merged — FR-ER-2).
    resolution: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class Score(Base, UuidPkMixin):
    __tablename__ = "scores"
    __table_args__ = (
        CheckConstraint("overall >= 0 AND overall <= 100", name="overall_range"),
        UniqueConstraint("scan_id", name="uq_score_scan"),
    )

    scan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Measures exposure/exploitability of data — NEVER the person (FCRA line, CLAUDE.md #2).
    overall: Mapped[int] = mapped_column(Integer, nullable=False)
    subscores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rubric_version: Mapped[str] = mapped_column(String(32), nullable=False)
    # [{finding_id, points, reason}] — every point traces to findings (FR-SCORE-1).
    contributing: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    computed_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    # Grounded report narrative (B1): the citation-guarded NarrativeDraft as
    # JSON, cached per score computation; meta records generator (LLM vs
    # template), model, guard outcome, and token spend. Non-sensitive by
    # construction — credential findings enter the narrative context with
    # their generic locked summary only (ayin.report).
    narrative: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    narrative_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class RemediationTask(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "remediation_tasks"

    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("findings.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[RemediationType] = mapped_column(str_enum(RemediationType), nullable=False)
    target: Mapped[str] = mapped_column(String(256), nullable=False)  # e.g. broker site, account
    status: Mapped[RemediationStatus] = mapped_column(
        str_enum(RemediationStatus), nullable=False, default=RemediationStatus.SUGGESTED
    )
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    expected_score_impact: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_score_impact: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now(), nullable=True)
