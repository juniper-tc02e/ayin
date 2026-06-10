"""Shared FastAPI dependencies — current user, step-up enforcement."""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ayin.auth.tokens import SCOPE_SESSION, SCOPE_STEP_UP, decode_token
from ayin.config import Settings, get_settings
from ayin.db import get_db
from ayin.models import User

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: DbDep, settings: SettingsDep) -> User:
    token = request.cookies.get(settings.auth_cookie_name)
    user_id = decode_token(settings, token, required_scope=SCOPE_SESSION) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_step_up(request: Request, user: CurrentUser, settings: SettingsDep) -> User:
    """Step-up verification before credential-level data (FR-AUTH-1).

    The client re-authenticates via POST /auth/step-up and presents the
    short-lived elevated token in the X-Ayin-Step-Up header.
    """
    token = request.headers.get("X-Ayin-Step-Up")
    elevated_id = decode_token(settings, token, required_scope=SCOPE_STEP_UP) if token else None
    if elevated_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Step-up verification required: re-enter your password to view this data.",
        )
    return user


StepUpUser = Annotated[User, Depends(require_step_up)]
