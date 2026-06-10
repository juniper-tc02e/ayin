"""ToS/AUP gate (FR-AUTH-2) — a pipeline gate, not a UI nicety.

``require_tos`` guards anything that starts a scan: no acceptance row for the
*current* version → 403 with a machine-readable code so the frontend can
show the (re-)prompt. Version bumps therefore re-gate automatically.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ayin.api.deps import CurrentUser, DbDep, SettingsDep
from ayin.models import TosAcceptance, User

TOS_REQUIRED_CODE = "TOS_ACCEPTANCE_REQUIRED"


def has_accepted_current(db: Session, user_id: uuid.UUID, current_version: str) -> bool:
    return (
        db.execute(
            select(TosAcceptance.id).where(
                TosAcceptance.user_id == user_id,
                TosAcceptance.version == current_version,
            )
        ).scalar_one_or_none()
        is not None
    )


def require_tos(user: CurrentUser, db: DbDep, settings: SettingsDep) -> User:
    """FastAPI dependency: blocks until the current ToS/AUP version is accepted."""
    if not has_accepted_current(db, user.id, settings.tos_current_version):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "code": TOS_REQUIRED_CODE,
                "message": "Accept the current Terms of Service and Acceptable Use "
                "Policy before scanning.",
                "current_version": settings.tos_current_version,
            },
        )
    return user
