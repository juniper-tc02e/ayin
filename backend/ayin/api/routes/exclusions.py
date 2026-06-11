"""Public "Exclude me from Ayin" endpoints (FR-TS-3, M3-4).

Unauthenticated by design — anyone can exclude an identifier they control,
Ayin account or not. Responses never reveal whether a value was already
excluded (no membership oracle)."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ayin.api.deps import DbDep, SettingsDep
from ayin.api.routes.auth import get_email_sender
from ayin.api.schemas import MessageOut
from ayin.safety.exclusion import ExclusionError, confirm_exclusion, request_exclusion
from ayin.services.email import EmailSender

router = APIRouter(prefix="/exclusions", tags=["exclusions"])


class ExclusionRequestIn(BaseModel):
    kind: str = Field(pattern=r"^[a-z_]+$")
    value: str = Field(min_length=3, max_length=512)


class ExclusionConfirmIn(BaseModel):
    token: str = Field(min_length=16, max_length=128)


@router.post("/request", response_model=MessageOut)
def request_(
    body: ExclusionRequestIn,
    db: DbDep,
    settings: SettingsDep,
    sender: EmailSender = Depends(get_email_sender),
):
    try:
        request_exclusion(db, settings, sender, kind=body.kind, value=body.value)
    except ExclusionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    return MessageOut(
        message="If that address is valid, a confirmation link is on its way. "
        "Nothing changes until it's confirmed."
    )


@router.post("/confirm", response_model=MessageOut)
def confirm(body: ExclusionConfirmIn, db: DbDep):
    try:
        confirm_exclusion(db, body.token)
    except ExclusionError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    return MessageOut(
        message="Done. This identifier is permanently excluded from Ayin scans, "
        "and any existing scan data tied to it has been removed."
    )
