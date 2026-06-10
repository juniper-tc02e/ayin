"""Finding review endpoints (FR-ER-1, M2-1): confirm / reject matches."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from ayin.api.deps import CurrentUser, DbDep
from ayin.api.routes.identifiers import get_my_subject
from ayin.api.schemas import MessageOut
from ayin.models import Finding, Subject
from ayin.resolution.feedback import FeedbackError, confirm_finding, reject_finding

router = APIRouter(prefix="/findings", tags=["findings"])


def _owned_finding(db, subject: Subject, finding_id: uuid.UUID) -> Finding:
    finding = db.execute(
        select(Finding).where(Finding.id == finding_id, Finding.subject_id == subject.id)
    ).scalar_one_or_none()
    if finding is None:
        # 404, not 403 — never confirm another subject's finding exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found.")
    return finding


@router.post("/{finding_id}/confirm", response_model=MessageOut)
def confirm(
    finding_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    subject: Subject = Depends(get_my_subject),
):
    finding = _owned_finding(db, subject, finding_id)
    try:
        confirm_finding(db, user, finding)
    except FeedbackError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    db.commit()
    return MessageOut(message="Confirmed — this now counts toward your exposure picture.")


@router.post("/{finding_id}/reject", response_model=MessageOut)
def reject(
    finding_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    subject: Subject = Depends(get_my_subject),
):
    finding = _owned_finding(db, subject, finding_id)
    try:
        reject_finding(db, user, finding)
    except FeedbackError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    db.commit()
    return MessageOut(
        message="Marked as not you — it no longer counts toward your exposure picture."
    )
