"""Abuse heuristics — pipeline gate, not an afterthought (FR-SCAN-5, FR-TS-2).

Decisions:
- REFUSE — the scan must not run (e.g. subject appears to be a minor:
  data about minors is permanently out of scope, CLAUDE.md #3).
- HOLD — a human reviews before anything runs (victim-protection match,
  anomaly pattern). The user-facing reason for holds is deliberately
  GENERIC: confirming a victim-protection match to the requester would
  itself endanger the protected person. The real kind lives only in the
  audit record and the T&S review queue (AbuseSignal).

Every refusal/hold writes an AbuseSignal review-queue row and is audited.
False positives have an appeal path (POST /scans/{id}/appeal).

These heuristics are deliberately conservative MVP rules; T&S tunes them
operationally (they live server-side, not in clients).
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ayin.models import AbuseSignal, Identifier, Scan
from ayin.models.enums import (
    AbuseSignalKind,
    AbuseSignalSeverity,
    IdentifierKind,
)
from ayin.models.protection import ProtectionEntry
from ayin.safety.hashing import identifier_hash

log = logging.getLogger("ayin.safety.abuse")

GENERIC_HOLD_REASON = (
    "manual_review: this scan needs a quick human check before it runs. "
    "You'll be notified — or appeal from the scan page."
)

# Email domains shaped like US K-12 school districts → subject likely a minor.
_K12_RE = re.compile(r"\.k12\.[a-z]{2}\.us$|(^|\.)k12\.|highschool|middleschool")
# Birth-year tokens implying age < 18 at scan time (rolling window).
_BIRTHYEAR_RE = re.compile(r"(?<!\d)(20[0-2]\d)(?!\d)")


@dataclass(frozen=True)
class AbuseDecision:
    decision: str  # "pass" | "refuse" | "hold"
    public_reason: str = ""  # safe to show the requester
    internal_kind: AbuseSignalKind | None = None
    internal_detail: str = ""  # audit/review queue only


def _minor_signals(identifiers: list[Identifier], now: datetime) -> str | None:
    cutoff_year = now.year - 18
    for ident in identifiers:
        value = ident.value_normalized
        if ident.kind == IdentifierKind.EMAIL and _K12_RE.search(value.split("@")[-1]):
            return f"k12-pattern email domain ({ident.kind.value})"
        if ident.kind in (IdentifierKind.USERNAME, IdentifierKind.FULL_NAME):
            for match in _BIRTHYEAR_RE.findall(value):
                if int(match) > cutoff_year:
                    return f"possible birth year {match} in {ident.kind.value}"
    return None


def _protection_match(db: Session, identifiers: list[Identifier]) -> ProtectionEntry | None:
    if not identifiers:
        return None
    hashes = {identifier_hash(i.kind, i.value_normalized): i for i in identifiers}
    return db.execute(
        select(ProtectionEntry).where(ProtectionEntry.value_hash.in_(list(hashes)))
    ).scalars().first()


def screen_subject_identifiers(
    db: Session, identifiers: list[Identifier], *, now: datetime | None = None
) -> str | None:
    """Reusable minor/protection pre-screen for flows OUTSIDE the scan gate
    (e.g. consent request/accept). Returns a machine reason ('minor:…' or
    'protected') or None. Read-only: writes no signals and does not consult the
    exclusion list (callers add that). Accepts transient (unsaved) Identifiers —
    only ``.kind`` / ``.value_normalized`` are read."""
    now = now or datetime.now(timezone.utc)
    minor = _minor_signals(identifiers, now)
    if minor:
        return f"minor:{minor}"
    if _protection_match(db, identifiers) is not None:
        return "protected"
    return None


def _anomaly_state(db: Session, scan: Scan) -> tuple[int, int]:
    """(block_count, warn_count) of open signals for this requester, 24h."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = db.execute(
        select(AbuseSignal.severity, func.count(AbuseSignal.id))
        .where(
            AbuseSignal.user_id == scan.requester_user_id,
            AbuseSignal.created_at >= cutoff,
            AbuseSignal.kind != AbuseSignalKind.APPEAL,
        )
        .group_by(AbuseSignal.severity)
    ).all()
    counts = {sev: n for sev, n in rows}
    return (
        counts.get(AbuseSignalSeverity.BLOCK, 0),
        counts.get(AbuseSignalSeverity.WARN, 0),
    )


def evaluate_scan(db: Session, scan: Scan, identifiers: list[Identifier]) -> AbuseDecision:
    now = datetime.now(timezone.utc)

    minor = _minor_signals(identifiers, now)
    if minor:
        _signal(db, scan, AbuseSignalKind.MINOR_SUBJECT, AbuseSignalSeverity.BLOCK, minor)
        return AbuseDecision(
            decision="refuse",
            public_reason=(
                "minor_subject: this scan appears to involve someone under 18 — "
                "Ayin never scans minors. If this is a mistake (e.g. a school "
                "alumni address), appeal from the scan page."
            ),
            internal_kind=AbuseSignalKind.MINOR_SUBJECT,
            internal_detail=minor,
        )

    protected = _protection_match(db, identifiers)
    if protected is not None:
        _signal(
            db, scan, AbuseSignalKind.VICTIM_PROTECTION, AbuseSignalSeverity.BLOCK,
            f"protection entry {protected.id}",
        )
        # NEVER reveal the match to the requester.
        return AbuseDecision(
            decision="hold",
            public_reason=GENERIC_HOLD_REASON,
            internal_kind=AbuseSignalKind.VICTIM_PROTECTION,
            internal_detail=f"entry={protected.id}",
        )

    blocks, warns = _anomaly_state(db, scan)
    if blocks:
        return AbuseDecision(
            decision="refuse",
            public_reason=(
                "account_flagged: scanning is paused on this account while our "
                "team reviews unusual activity. Appeal from the scan page."
            ),
            internal_kind=AbuseSignalKind.ANOMALY,
            internal_detail=f"open block-severity signals: {blocks}",
        )
    if warns >= 2:
        _signal(
            db, scan, AbuseSignalKind.ANOMALY, AbuseSignalSeverity.WARN,
            f"{warns} warn-severity signals in 24h",
        )
        return AbuseDecision(
            decision="hold",
            public_reason=GENERIC_HOLD_REASON,
            internal_kind=AbuseSignalKind.ANOMALY,
            internal_detail=f"warn signals in 24h: {warns}",
        )
    return AbuseDecision(decision="pass")


def _signal(
    db: Session, scan: Scan, kind: AbuseSignalKind, severity: AbuseSignalSeverity, detail: str
) -> None:
    db.add(
        AbuseSignal(
            user_id=scan.requester_user_id,
            scan_id=scan.id,
            kind=kind,
            severity=severity,
            detail={"heuristic": detail},
        )
    )
    db.flush()


def file_appeal(db: Session, scan: Scan, message: str) -> AbuseSignal:
    """False-positive appeal → open review case (FR-SCAN-5 acceptance)."""
    existing = db.execute(
        select(AbuseSignal).where(
            AbuseSignal.scan_id == scan.id, AbuseSignal.kind == AbuseSignalKind.APPEAL
        )
    ).scalars().first()
    if existing is not None:
        raise ValueError("An appeal for this scan is already under review.")
    signal = AbuseSignal(
        user_id=scan.requester_user_id,
        scan_id=scan.id,
        kind=AbuseSignalKind.APPEAL,
        severity=AbuseSignalSeverity.INFO,
        detail={"message": message[:2000], "scan_error": scan.error},
    )
    db.add(signal)
    db.flush()
    return signal
