"""ToS/AUP acceptance endpoints (FR-AUTH-2, M0-5)."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ayin.api.deps import CurrentUser, DbDep, SettingsDep
from ayin.models import TosAcceptance
from ayin.safety.audit import record_event, user_actor
from ayin.safety.tos import has_accepted_current

router = APIRouter(prefix="/tos", tags=["tos"])


class TosStatusOut(BaseModel):
    current_version: str
    accepted_current: bool


class TosAcceptIn(BaseModel):
    version: str


@router.get("", response_model=TosStatusOut)
def tos_status(user: CurrentUser, db: DbDep, settings: SettingsDep):
    return TosStatusOut(
        current_version=settings.tos_current_version,
        accepted_current=has_accepted_current(db, user.id, settings.tos_current_version),
    )


@router.post("/accept", response_model=TosStatusOut)
def accept_tos(body: TosAcceptIn, user: CurrentUser, db: DbDep, settings: SettingsDep):
    current = settings.tos_current_version
    if body.version != current:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"The terms changed (current version: {current}). Review and accept the "
            "current version.",
        )
    if not has_accepted_current(db, user.id, current):
        db.add(TosAcceptance(user_id=user.id, version=current))
        record_event(
            db, actor=user_actor(user.id), event_type="tos.accepted",
            detail={"version": current},
        )
        db.commit()
    return TosStatusOut(current_version=current, accepted_current=True)
