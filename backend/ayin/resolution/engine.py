"""Resolution passes over a completed scan's findings (M2-1 + M2-2).

Pass 1 — DEDUPE (M2-2, FR-ER-2):
    Group active findings by canonical exposure key. One primary per group
    (highest source confidence, oldest as tiebreak); the rest become
    state=SUPPRESSED with ``duplicate_of`` set. The primary preserves every
    contributing source in ``merged_sources`` and counts distinct sources as
    ``corroboration_count``. Field conflicts between members (e.g. two
    providers disagree on a breach date) are FLAGGED in
    ``resolution["conflicts"]`` — never silently merged.

Pass 2 — MATCH (M2-1, FR-ER-1):
    Decide "is this exposure about the requester?" per primary finding.

    The anti-namesake invariant: findings keyed to a seed whose control the
    user PROVED (verified email/phone) start from the connector's confidence;
    findings keyed to unverifiable seeds (username/name/city) are CAPPED at
    0.65 — below the 0.70 auto-match threshold — so a single-source name or
    username match can NEVER silently join the profile. Only corroboration
    across independent sources (+0.15 each) or the user's explicit
    confirmation lifts it. User CONFIRMED/REJECTED is never overwritten.

Both passes are idempotent — safe to re-run on resume.
"""

import logging
import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ayin.models import Finding, Identifier, Scan
from ayin.models.enums import FindingState, MatchStatus
from ayin.resolution.canonical import canonical_exposure_key
from ayin.safety.audit import record_scan_event, system_actor
from ayin.services.normalize import CHALLENGEABLE_KINDS

log = logging.getLogger("ayin.resolution")

AUTO_MATCH_THRESHOLD = 0.70
UNVERIFIABLE_SEED_CAP = 0.65  # < threshold by design — the anti-namesake wall
CORROBORATION_BOOST = 0.15  # per extra independent source
MATCH_CONFIDENCE_CEILING = 0.98

# Payload fields whose disagreement across merged sources matters.
_CONFLICT_FIELDS = ("breach_date", "data_classes", "site", "platform", "title")


def resolve_scan(db: Session, scan: Scan) -> dict:
    """Run both passes; returns a summary dict (also audited)."""
    findings = list(
        db.execute(
            select(Finding).where(
                Finding.scan_id == scan.id, Finding.state == FindingState.ACTIVE
            )
        ).scalars()
    )
    dedupe_summary = _dedupe_pass(db, findings)
    primaries = [f for f in findings if f.state == FindingState.ACTIVE]
    match_summary = _match_pass(db, scan, primaries)
    summary = {**dedupe_summary, **match_summary}
    record_scan_event(
        db, actor=system_actor("resolution"), event_type="scan.resolved",
        scan_id=scan.id, subject_id=scan.subject_id, detail=summary,
    )
    db.flush()
    return summary


# ── Pass 1: dedupe + conflict flagging (M2-2) ────────────────────────


def _dedupe_pass(db: Session, findings: list[Finding]) -> dict:
    groups: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        key = canonical_exposure_key(f)
        groups[key or f"solo:{f.id}"].append(f)

    collapsed = 0
    conflicts_flagged = 0
    for members in groups.values():
        members.sort(key=lambda f: (-f.confidence, f.created_at, str(f.id)))
        primary, dupes = members[0], members[1:]

        merged = [_source_ref(m) for m in members]
        primary.merged_sources = merged
        primary.corroboration_count = len({m.source for m in members})

        conflicts = _find_conflicts(members)
        resolution = dict(primary.resolution or {})
        if conflicts:
            resolution["conflicts"] = conflicts
            conflicts_flagged += len(conflicts)
        primary.resolution = resolution

        for d in dupes:
            d.state = FindingState.SUPPRESSED
            d.duplicate_of = primary.id
            d.merged_sources = []
            collapsed += 1
    db.flush()
    return {"groups": len(groups), "duplicates_collapsed": collapsed,
            "conflicts_flagged": conflicts_flagged}


def _source_ref(f: Finding) -> dict:
    return {
        "finding_id": str(f.id),
        "source": f.source,
        "source_name": f.source_name,
        "source_url": f.source_url,
        "captured_at": f.captured_at.isoformat(),
        "confidence": f.confidence,
    }


def _find_conflicts(members: list[Finding]) -> list[dict]:
    """Disagreeing field values across a merged group → flagged, not merged."""
    if len(members) < 2:
        return []
    out = []
    for field in _CONFLICT_FIELDS:
        seen: dict[str, str] = {}
        for m in members:
            value = (m.payload or {}).get(field)
            if value is None:
                continue
            seen[repr(value)] = m.source
        if len(seen) > 1:
            out.append(
                {
                    "field": field,
                    "values": [
                        {"value": v, "source": s} for v, s in sorted(seen.items())
                    ],
                }
            )
    return out


# ── Pass 2: match decision (M2-1) ────────────────────────────────────


def _match_pass(db: Session, scan: Scan, primaries: list[Finding]) -> dict:
    verified_challengeable = {
        row
        for row in db.execute(
            select(Identifier.id).where(
                Identifier.subject_id == scan.subject_id,
                Identifier.kind.in_(list(CHALLENGEABLE_KINDS)),
            )
        ).scalars()
    }

    auto = possible = kept_user_decision = 0
    for f in primaries:
        if f.match_status in (MatchStatus.CONFIRMED, MatchStatus.REJECTED):
            kept_user_decision += 1  # the user's word stands (FR-ER-1)
            continue

        confidence, reasons = _match_confidence(f, verified_challengeable)
        f.match_confidence = round(confidence, 3)
        resolution = dict(f.resolution or {})
        resolution["match_reasons"] = reasons
        f.resolution = resolution
        if confidence >= AUTO_MATCH_THRESHOLD:
            f.match_status = MatchStatus.AUTO_MATCHED
            auto += 1
        else:
            f.match_status = MatchStatus.POSSIBLE
            possible += 1
    db.flush()
    return {"auto_matched": auto, "possible": possible,
            "user_decisions_kept": kept_user_decision}


def _match_confidence(
    f: Finding, verified_challengeable: set[uuid.UUID]
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    base = f.confidence
    if f.identifier_id is not None and f.identifier_id in verified_challengeable:
        # Keyed to an identifier the user PROVED control of (email/phone):
        # the exposure is about their account by construction.
        reasons.append("keyed to a control-verified identifier")
    else:
        if base > UNVERIFIABLE_SEED_CAP:
            reasons.append(
                f"capped at {UNVERIFIABLE_SEED_CAP} (seed not control-verifiable; "
                "single-source name/username matches never auto-merge)"
            )
        base = min(base, UNVERIFIABLE_SEED_CAP)

    extra_sources = max(0, (f.corroboration_count or 1) - 1)
    if extra_sources:
        reasons.append(f"corroborated by {extra_sources} additional source(s)")
    confidence = min(MATCH_CONFIDENCE_CEILING, base + CORROBORATION_BOOST * extra_sources)
    reasons.append(f"source confidence {f.confidence:.2f}")
    return confidence, reasons
