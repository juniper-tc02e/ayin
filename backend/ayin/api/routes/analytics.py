"""Client-side funnel events (M4-2): report_viewed, action_started.

Only these two names are accepted from clients; properties pass the same PII
screen as server events; scan ownership is enforced."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ayin.analytics import track
from ayin.analytics.events import AnalyticsPIIError
from ayin.api.deps import CurrentUser, DbDep
from ayin.api.routes.identifiers import get_my_subject
from ayin.api.schemas import MessageOut
from ayin.models import Scan, Subject

router = APIRouter(prefix="/analytics", tags=["analytics"])

CLIENT_EVENTS = {"report_viewed", "action_started"}


class ClientEventIn(BaseModel):
    name: str
    scan_id: uuid.UUID | None = None
    properties: dict = Field(default_factory=dict)


@router.post("/events", response_model=MessageOut)
def client_event(
    body: ClientEventIn,
    user: CurrentUser,
    db: DbDep,
    subject: Subject = Depends(get_my_subject),
):
    if body.name not in CLIENT_EVENTS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Clients may emit only: {sorted(CLIENT_EVENTS)}",
        )
    if body.scan_id is not None:
        owned = db.get(Scan, body.scan_id)
        if owned is None or owned.subject_id != subject.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan not found.")
    try:
        track(db, body.name, user_id=user.id, scan_id=body.scan_id,
              properties=body.properties)
    except AnalyticsPIIError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    db.commit()
    return MessageOut(message="ok")
