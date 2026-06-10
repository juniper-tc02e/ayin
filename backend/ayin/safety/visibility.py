"""Finding visibility rules (FR-AUTH-1).

Rule (MVP): a finding keyed to a seed identifier is visible only once that
identifier's control is VERIFIED. Findings not keyed to a single identifier
(derived/linkage, identifier_id IS NULL) are visible. Credential-category
findings additionally require a step-up token at the endpoint serving them
(api.deps.require_step_up) — defense in depth on top of this filter.

Used by every endpoint that returns findings (M1+). Tested directly in M0-4.
"""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ayin.models import Finding, Identifier
from ayin.models.enums import FindingState, VerificationState


def visible_findings_query(subject_id: uuid.UUID, *, include_suppressed: bool = False):
    """SELECT over findings for a subject, excluding any finding keyed to an
    identifier whose control is not verified — and (default) excluding
    suppressed duplicates, whose primaries carry their merged_sources."""
    verified_ids = select(Identifier.id).where(
        Identifier.subject_id == subject_id,
        Identifier.verification_state == VerificationState.VERIFIED,
    )
    q = select(Finding).where(
        Finding.subject_id == subject_id,
        or_(Finding.identifier_id.is_(None), Finding.identifier_id.in_(verified_ids)),
    )
    if not include_suppressed:
        q = q.where(Finding.state != FindingState.SUPPRESSED)
    return q


def visible_findings(db: Session, subject_id: uuid.UUID) -> list[Finding]:
    return list(db.execute(visible_findings_query(subject_id)).scalars())
