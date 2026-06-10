"""Finding visibility rules (FR-AUTH-1).

Rule (MVP):
- A finding keyed to a CHALLENGEABLE identifier (email/phone) is visible only
  once that identifier's control is VERIFIED — you never see results for an
  address you haven't proven is yours.
- A finding keyed to an AUXILIARY identifier (username/name/city — kinds that
  cannot be control-verified) is visible: auxiliary seeds only ever fan out
  alongside a verified anchor (orchestrator gate), and their findings are
  exactly the "possible, unconfirmed" queue the user reviews via
  confirm/reject (FR-ER-1, M2-1).
- Derived findings (identifier IS NULL) are visible.
- Suppressed duplicates are hidden by default (their primary carries
  merged_sources — M2-2).

Credential-category findings additionally require a step-up token at the
endpoint serving them (api.deps.require_step_up) — defense in depth.

Used by every endpoint that returns findings.
"""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ayin.models import Finding, Identifier
from ayin.models.enums import FindingState, VerificationState
from ayin.services.normalize import CHALLENGEABLE_KINDS


def visible_findings_query(subject_id: uuid.UUID, *, include_suppressed: bool = False):
    blocked_ids = select(Identifier.id).where(
        Identifier.subject_id == subject_id,
        Identifier.kind.in_(list(CHALLENGEABLE_KINDS)),
        Identifier.verification_state != VerificationState.VERIFIED,
    )
    q = select(Finding).where(
        Finding.subject_id == subject_id,
        or_(Finding.identifier_id.is_(None), Finding.identifier_id.not_in(blocked_ids)),
    )
    if not include_suppressed:
        q = q.where(Finding.state != FindingState.SUPPRESSED)
    return q


def visible_findings(db: Session, subject_id: uuid.UUID) -> list[Finding]:
    return list(db.execute(visible_findings_query(subject_id)).scalars())
