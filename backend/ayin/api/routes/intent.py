"""Intent capture endpoints (M4-4): join/leave the monitoring & removal
waitlists from the report. Idempotent; counted once per user in the funnel."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from ayin.analytics import track
from ayin.api.deps import CurrentUser, DbDep
from ayin.models.intent import IntentKind, IntentSignal
from ayin.safety.audit import record_event, user_actor

router = APIRouter(prefix="/intent", tags=["intent"])


class IntentIn(BaseModel):
    kind: IntentKind
    scan_id: uuid.UUID | None = None


class IntentOut(BaseModel):
    monitoring: bool
    removal: bool


def _state(db, user_id) -> IntentOut:
    rows = db.execute(
        select(IntentSignal).where(
            IntentSignal.user_id == user_id, IntentSignal.withdrawn_at.is_(None)
        )
    ).scalars()
    kinds = {r.kind for r in rows}
    return IntentOut(
        monitoring=IntentKind.MONITORING in kinds, removal=IntentKind.REMOVAL in kinds
    )


@router.get("", response_model=IntentOut)
def get_intent(user: CurrentUser, db: DbDep):
    return _state(db, user.id)


@router.post("", response_model=IntentOut)
def capture_intent(body: IntentIn, user: CurrentUser, db: DbDep):
    existing = db.execute(
        select(IntentSignal).where(
            IntentSignal.user_id == user.id, IntentSignal.kind == body.kind
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(IntentSignal(user_id=user.id, kind=body.kind, scan_id=body.scan_id))
        record_event(
            db, actor=user_actor(user.id), event_type="intent.captured",
            detail={"kind": body.kind.value},
        )
        track(
            db,
            "monitoring_intent_captured"
            if body.kind == IntentKind.MONITORING
            else "removal_intent_captured",
            user_id=user.id,
            scan_id=body.scan_id,
            properties={"kind": body.kind.value},
        )
    elif existing.withdrawn_at is not None:
        existing.withdrawn_at = None
    db.commit()
    return _state(db, user.id)
