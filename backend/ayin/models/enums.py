"""Domain enums.

Stored as VARCHAR + CHECK constraints (``native_enum=False``) so adding values
is an additive migration, not a Postgres enum surgery.
"""

import enum


class IdentifierKind(str, enum.Enum):
    EMAIL = "email"
    PHONE = "phone"
    USERNAME = "username"
    FULL_NAME = "full_name"
    CITY = "city"


class VerificationState(str, enum.Enum):
    """Control-of-identifier proof state (FR-AUTH-1).

    Sensitive results for an identifier are only viewable once VERIFIED.
    """

    UNVERIFIED = "unverified"
    PENDING = "pending"  # challenge sent (email link / phone OTP)
    VERIFIED = "verified"


class ScanTier(str, enum.Enum):
    """Consent tiers (PRD §7.2). MVP ships T0 ONLY — the DB also enforces this
    with a CHECK constraint; widening it requires a migration + ADR."""

    T0_SELF = "t0"


class ScanStatus(str, enum.Enum):
    QUEUED = "queued"
    GATED = "gated"  # safety gates evaluating — can refuse before running
    RUNNING = "running"
    RESOLVING = "resolving"
    SCORING = "scoring"
    DONE = "done"
    FAILED = "failed"
    HELD = "held"  # safety hold for human review (FR-SCAN-5)


class JobStatus(str, enum.Enum):
    """Per-connector unit of work inside a scan (M1-1)."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class FindingCategory(str, enum.Enum):
    CREDENTIAL = "credential"  # breach / leaked-credential exposure
    BROKER = "broker"  # data-broker / people-search listing
    SOCIAL = "social"  # public web & social footprint
    RECORDS = "records"  # public records (Phase 2 — category reserved)
    LINKAGE = "linkage"  # cross-source linkability of identifiers


class Sensitivity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MatchStatus(str, enum.Enum):
    """Entity-resolution decision for a finding (FR-ER-1, M2-1).

    AUTO_MATCHED: above-threshold — counted in the profile and score.
    POSSIBLE: below threshold — shown as "possible, unconfirmed", NEVER
              auto-merged, excluded from the score until confirmed.
    CONFIRMED / REJECTED: the user's word — overrides resolution and is
              never overwritten by a re-run.
    """

    AUTO_MATCHED = "auto_matched"
    POSSIBLE = "possible"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class FindingState(str, enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    STALE = "stale"
    SUPPRESSED = "suppressed"  # e.g. excluded subject (FR-TS-3)


class PivotLinkStatus(str, enum.Enum):
    """Lifecycle of a pivot-graph edge (ADR-0005, S2-1).

    PROPOSED: a sourced candidate edge — never auto-traversed or scored.
    MATERIALIZED: promoted to a real seed (above threshold + attached to the
                  verified subject) and walked.
    CONFIRMED / REJECTED: the user's word — final, survives re-resolution.
    """

    PROPOSED = "proposed"
    MATERIALIZED = "materialized"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class RemediationType(str, enum.Enum):
    OPT_OUT = "opt_out"
    DROP = "drop"
    DSAR = "dsar"
    HARDENING = "hardening"


class RemediationStatus(str, enum.Enum):
    SUGGESTED = "suggested"
    STARTED = "started"
    REQUESTED = "requested"
    ACKNOWLEDGED = "acknowledged"
    REMOVED = "removed"
    DONE = "done"
    FAILED = "failed"
    RELISTED = "relisted"


class ActorType(str, enum.Enum):
    USER = "user"
    SYSTEM = "system"
    STAFF = "staff"  # internal access is audited like any other (CLAUDE.md #7)


class AbuseSignalKind(str, enum.Enum):
    VELOCITY = "velocity"
    MINOR_SUBJECT = "minor_subject"
    VICTIM_PROTECTION = "victim_protection"
    ANOMALY = "anomaly"
    APPEAL = "appeal"  # user-filed false-positive appeal (FR-SCAN-5)


class AbuseSignalSeverity(str, enum.Enum):
    INFO = "info"
    WARN = "warn"
    BLOCK = "block"


class AbuseSignalStatus(str, enum.Enum):
    """Lifecycle doubles as the MVP review-case workflow (PRD §10.4
    AbuseSignal/ReviewCase merged for MVP — split when reviewer tooling lands)."""

    OPEN = "open"
    REVIEWING = "reviewing"
    ACTIONED = "actioned"
    DISMISSED = "dismissed"
