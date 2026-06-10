"""Auth routes (FR-AUTH-1 — account creation & self-identity verification).

Every event here writes an audit record in the same transaction.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ayin.api.deps import CurrentUser, DbDep, SettingsDep
from ayin.api.schemas import (
    LoginIn,
    MessageOut,
    SignupIn,
    StepUpIn,
    StepUpOut,
    UserOut,
    VerifyEmailIn,
)
from ayin.auth.passwords import hash_password, password_problems, verify_password
from ayin.auth.tokens import issue_session_token, issue_step_up_token
from ayin.auth.verification import consume_link_token, create_link_token
from ayin.models import Subject, TokenKind, User
from ayin.safety.audit import record_event, user_actor
from ayin.services.email import EmailSender, get_email_sender_factory

log = logging.getLogger("ayin.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


def get_email_sender(settings: SettingsDep) -> EmailSender:
    return get_email_sender_factory(settings)


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        email_verified=user.email_verified_at is not None,
        created_at=user.created_at,
    )


def _set_session_cookie(response: Response, settings, user: User) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=issue_session_token(settings, user.id),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_ttl_minutes * 60,
        path="/",
    )


def _send_account_verification(
    db, settings, sender: EmailSender, user: User
) -> None:
    raw = create_link_token(
        db,
        user_id=user.id,
        kind=TokenKind.ACCOUNT_EMAIL,
        ttl_minutes=settings.verification_token_ttl_minutes,
    )
    link = f"{settings.web_base_url}/verify-email?token={raw}"
    sender.send(
        to=user.email,
        subject="Verify your Ayin account email",
        body=(
            "Confirm you control this address to activate your Ayin account.\n\n"
            f"{link}\n\n"
            "Ayin only ever scans identifiers you have verified you control. "
            "If you didn't create this account, ignore this email — the account "
            "cannot be used to view results without this verification."
        ),
    )


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(
    body: SignupIn,
    response: Response,
    db: DbDep,
    settings: SettingsDep,
    sender: EmailSender = Depends(get_email_sender),
):
    problem = password_problems(body.password)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)

    email = body.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email exists.")

    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    # T0: the requester IS the subject — created together (CLAUDE.md #1).
    db.add(Subject(owner_user_id=user.id))
    db.flush()
    record_event(db, actor=user_actor(user.id), event_type="auth.signup")
    _send_account_verification(db, settings, sender, user)
    db.commit()

    _set_session_cookie(response, settings, user)
    return _user_out(user)


@router.post("/login", response_model=UserOut)
def login(
    body: LoginIn,
    response: Response,
    db: DbDep,
    settings: SettingsDep,
):
    email = body.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if user is None or user.password_hash is None or not verify_password(
        body.password, user.password_hash
    ):
        if user is not None:
            record_event(
                db, actor=user_actor(user.id), event_type="auth.login_failed"
            )
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled.")

    record_event(db, actor=user_actor(user.id), event_type="auth.login")
    db.commit()
    _set_session_cookie(response, settings, user)
    return _user_out(user)


@router.post("/logout", response_model=MessageOut)
def logout(response: Response, settings: SettingsDep):
    response.delete_cookie(settings.auth_cookie_name, path="/")
    return MessageOut(message="Logged out.")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return _user_out(user)


@router.post("/verify-email", response_model=UserOut)
def verify_email(body: VerifyEmailIn, db: DbDep, settings: SettingsDep):
    from datetime import datetime, timezone

    row = consume_link_token(db, raw=body.token, kind=TokenKind.ACCOUNT_EMAIL)
    if row is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid or expired verification link."
        )
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Account no longer exists.")
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
    record_event(db, actor=user_actor(user.id), event_type="auth.email_verified")
    db.commit()
    return _user_out(user)


@router.post("/step-up", response_model=StepUpOut)
def step_up(body: StepUpIn, user: CurrentUser, db: DbDep, settings: SettingsDep):
    """Re-authenticate to view credential-level data (FR-AUTH-1 step-up)."""
    if user.password_hash is None or not verify_password(body.password, user.password_hash):
        record_event(db, actor=user_actor(user.id), event_type="auth.step_up_failed")
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Password incorrect.")
    record_event(db, actor=user_actor(user.id), event_type="auth.step_up")
    db.commit()
    return StepUpOut(
        step_up_token=issue_step_up_token(settings, user.id),
        expires_in_minutes=settings.step_up_ttl_minutes,
    )
