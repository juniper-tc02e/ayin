"""Session / step-up JWTs (HS256, app secret).

Scopes:
- ``session``  — normal logged-in browsing (httpOnly cookie).
- ``step_up``  — short-lived elevation issued after re-entering the password;
  required before credential-level data is revealed (FR-AUTH-1). Issued here,
  enforced from M0-4 on.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt

from ayin.config import Settings

ALGORITHM = "HS256"
SCOPE_SESSION = "session"
SCOPE_STEP_UP = "step_up"


def issue_token(settings: Settings, *, user_id: uuid.UUID, scope: str, ttl_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "scope": scope,
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.app_secret, algorithm=ALGORITHM)


def issue_session_token(settings: Settings, user_id: uuid.UUID) -> str:
    return issue_token(
        settings, user_id=user_id, scope=SCOPE_SESSION,
        ttl_minutes=settings.access_token_ttl_minutes,
    )


def issue_step_up_token(settings: Settings, user_id: uuid.UUID) -> str:
    return issue_token(
        settings, user_id=user_id, scope=SCOPE_STEP_UP,
        ttl_minutes=settings.step_up_ttl_minutes,
    )


def decode_token(settings: Settings, token: str, *, required_scope: str) -> uuid.UUID | None:
    """Return the user id, or None if the token is invalid/expired/wrong-scope."""
    try:
        payload = jwt.decode(token, settings.app_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("scope") != required_scope:
        return None
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        return None
