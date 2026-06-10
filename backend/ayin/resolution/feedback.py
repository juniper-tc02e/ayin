"""User confirm/reject of resolution matches (FR-ER-1, M2-1).

The user's decision is authoritative: it overrides the matcher and is never
overwritten by re-resolution. Every decision is audited and (from M2-3) the
scan's score recomputes immediately so the number always reflects the
confirmed picture.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from ayin.models import Finding, User
from ayin.models.enums import FindingState, MatchStatus
from ayin.safety.audit import record_event, user_actor

log = logging.getLogger("ayin.resolution.feedback")


class FeedbackError(ValueError):
    pass


def _apply(db: Session, user: User, finding: Finding, status: MatchStatus) -> Finding:
    if finding.state == FindingState.SUPPRESSED:
        raise FeedbackError(
            "This finding was merged into another — review the primary finding instead."
        )
    previous = finding.match_status
    finding.match_status = status
    resolution = dict(finding.resolution or {})
    resolution["user_decision"] = {
        "decision": status.value,
        "previous": previous.value,
    }
    finding.resolution = resolution
    record_event(
        db,
        actor=user_actor(user.id),
        event_type=f"resolution.{'confirmed' if status == MatchStatus.CONFIRMED else 'rejected'}",
        subject_id=finding.subject_id,
        detail={"finding_id": str(finding.id), "previous": previous.value},
    )
    _recompute_score_if_available(db, finding.scan_id)
    db.flush()
    return finding


def confirm_finding(db: Session, user: User, finding: Finding) -> Finding:
    """\"Yes, this is me.\" Counts toward the profile and the score."""
    return _apply(db, user, finding, MatchStatus.CONFIRMED)


def reject_finding(db: Session, user: User, finding: Finding) -> Finding:
    """\"Not me.\" Excluded from the profile and the score; kept visible in a
    'not you' group so the decision is reviewable."""
    return _apply(db, user, finding, MatchStatus.REJECTED)


def _recompute_score_if_available(db: Session, scan_id: uuid.UUID) -> None:
    """Score recompute lands with M2-3; this hook makes confirm/reject
    immediately consistent once scoring exists."""
    try:
        from ayin.scoring import compute_score  # noqa: PLC0415
        from ayin.models import Scan  # noqa: PLC0415

        scan = db.get(Scan, scan_id)
        if scan is not None:
            compute_score(db, scan)
    except ImportError:
        log.debug("scoring not available yet — skipping recompute")
