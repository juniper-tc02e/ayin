"""Seed identifier management + control verification (FR-AUTH-1, M0-4).

- email → verification link; phone → 6-digit OTP (dev: console SMS)
- username / full_name / city are auxiliary seeds: not challengeable, and at
  scan-start (M1) usable only alongside a verified anchor identifier
- every list/read is a subject-data access → audit record
- findings keyed to an unverified identifier are never visible
  (ayin.safety.visibility — enforced by every findings endpoint)
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from ayin.api.deps import CurrentUser, DbDep, SettingsDep
from ayin.api.routes.auth import get_email_sender
from ayin.api.schemas import IdentifierIn, IdentifierOut, MessageOut, OtpIn, VerifyIdentifierEmailIn
from ayin.auth.verification import consume_link_token, consume_otp, create_link_token, create_otp
from ayin.models import Identifier, Subject, TokenKind, User
from ayin.models.enums import IdentifierKind, VerificationState
from ayin.safety.audit import record_data_access, record_event, user_actor
from ayin.services.email import EmailSender
from ayin.services.normalize import (
    CHALLENGEABLE_KINDS,
    IdentifierValidationError,
    normalize_identifier,
)
from ayin.services.sms import SmsSender, get_sms_sender_factory

log = logging.getLogger("ayin.identifiers")
router = APIRouter(prefix="/identifiers", tags=["identifiers"])


def get_sms_sender(settings: SettingsDep) -> SmsSender:
    return get_sms_sender_factory(settings)


def get_my_subject(user: CurrentUser, db: DbDep) -> Subject:
    subject = db.execute(
        select(Subject).where(Subject.owner_user_id == user.id)
    ).scalar_one_or_none()
    if subject is None:  # pragma: no cover — signup always creates it
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Subject missing.")
    return subject


def _out(ident: Identifier) -> IdentifierOut:
    return IdentifierOut(
        id=ident.id,
        kind=ident.kind.value,
        value=ident.value_raw,
        verification_state=ident.verification_state.value,
        challengeable=ident.kind in CHALLENGEABLE_KINDS,
        verified_at=ident.verified_at,
        created_at=ident.created_at,
    )


def _owned_identifier(db, subject: Subject, identifier_id: uuid.UUID) -> Identifier:
    ident = db.execute(
        select(Identifier).where(
            Identifier.id == identifier_id, Identifier.subject_id == subject.id
        )
    ).scalar_one_or_none()
    if ident is None:
        # 404 (not 403): do not confirm another user's identifier exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Identifier not found.")
    return ident


def _send_identifier_challenge(
    db, settings, email_sender: EmailSender, sms_sender: SmsSender,
    user: User, ident: Identifier,
) -> None:
    if ident.kind == IdentifierKind.EMAIL:
        raw = create_link_token(
            db,
            user_id=user.id,
            kind=TokenKind.IDENTIFIER_EMAIL,
            ttl_minutes=settings.verification_token_ttl_minutes,
            identifier_id=ident.id,
        )
        link = f"{settings.web_base_url}/verify-identifier?token={raw}"
        email_sender.send(
            to=ident.value_normalized,
            subject="Verify this email for your Ayin self-scan",
            body=(
                "Someone (hopefully you) added this address to their Ayin account "
                "to include it in their own exposure scan.\n\n"
                f"Confirm you control it: {link}\n\n"
                "If this wasn't you, ignore this email — the address cannot be "
                "scanned without this confirmation."
            ),
        )
    elif ident.kind == IdentifierKind.PHONE:
        code = create_otp(
            db,
            user_id=user.id,
            identifier_id=ident.id,
            ttl_minutes=min(settings.verification_token_ttl_minutes, 15),
        )
        sms_sender.send_otp(to=ident.value_normalized, code=code)
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"'{ident.kind.value}' identifiers can't be challenge-verified; they are "
            "auxiliary seeds used alongside your verified email/phone.",
        )
    if ident.verification_state == VerificationState.UNVERIFIED:
        ident.verification_state = VerificationState.PENDING
    record_event(
        db, actor=user_actor(user.id), event_type="identifier.challenge_sent",
        subject_id=ident.subject_id, detail={"identifier_id": str(ident.id)},
    )


@router.get("", response_model=list[IdentifierOut])
def list_identifiers(user: CurrentUser, db: DbDep, subject: Subject = Depends(get_my_subject)):
    record_data_access(
        db, actor=user_actor(user.id), subject_id=subject.id,
        resource="identifiers", purpose="self-view",
    )
    db.commit()
    rows = db.execute(
        select(Identifier)
        .where(Identifier.subject_id == subject.id)
        .order_by(Identifier.created_at)
    ).scalars()
    return [_out(i) for i in rows]


@router.post("", response_model=IdentifierOut, status_code=status.HTTP_201_CREATED)
def add_identifier(
    body: IdentifierIn,
    user: CurrentUser,
    db: DbDep,
    settings: SettingsDep,
    subject: Subject = Depends(get_my_subject),
    email_sender: EmailSender = Depends(get_email_sender),
    sms_sender: SmsSender = Depends(get_sms_sender),
):
    try:
        kind = IdentifierKind(body.kind)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown kind '{body.kind}'. One of: {[k.value for k in IdentifierKind]}",
        ) from None
    try:
        value_raw, value_norm = normalize_identifier(kind, body.value)
    except IdentifierValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None

    dupe = db.execute(
        select(Identifier).where(
            Identifier.subject_id == subject.id,
            Identifier.kind == kind,
            Identifier.value_normalized == value_norm,
        )
    ).scalar_one_or_none()
    if dupe is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already added this identifier.")

    ident = Identifier(
        subject_id=subject.id, kind=kind, value_raw=value_raw, value_normalized=value_norm
    )
    db.add(ident)
    db.flush()
    record_event(
        db, actor=user_actor(user.id), event_type="identifier.added",
        subject_id=subject.id, detail={"identifier_id": str(ident.id), "kind": kind.value},
    )
    from ayin.analytics import track  # noqa: PLC0415

    track(db, "identifier_added", user_id=user.id, properties={"kind": kind.value})
    if kind in CHALLENGEABLE_KINDS:
        _send_identifier_challenge(db, settings, email_sender, sms_sender, user, ident)
    db.commit()
    return _out(ident)


@router.post("/{identifier_id}/send-challenge", response_model=MessageOut)
def send_challenge(
    identifier_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    settings: SettingsDep,
    subject: Subject = Depends(get_my_subject),
    email_sender: EmailSender = Depends(get_email_sender),
    sms_sender: SmsSender = Depends(get_sms_sender),
):
    ident = _owned_identifier(db, subject, identifier_id)
    if ident.verification_state == VerificationState.VERIFIED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Already verified.")
    _send_identifier_challenge(db, settings, email_sender, sms_sender, user, ident)
    db.commit()
    return MessageOut(message="Challenge sent.")


@router.post("/verify-email", response_model=MessageOut)
def verify_identifier_email(body: VerifyIdentifierEmailIn, db: DbDep):
    """Unauthenticated by design: possession of the emailed link is the proof
    of control. The token is single-use, TTL'd, and stored hashed."""
    row = consume_link_token(db, raw=body.token, kind=TokenKind.IDENTIFIER_EMAIL)
    if row is None or row.identifier_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired verification link.")
    ident = db.get(Identifier, row.identifier_id)
    if ident is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Identifier no longer exists.")
    _mark_verified(db, row.user_id, ident)
    db.commit()
    return MessageOut(message="Identifier verified.")


@router.post("/{identifier_id}/verify-otp", response_model=MessageOut)
def verify_identifier_otp(
    identifier_id: uuid.UUID,
    body: OtpIn,
    user: CurrentUser,
    db: DbDep,
    subject: Subject = Depends(get_my_subject),
):
    ident = _owned_identifier(db, subject, identifier_id)
    if ident.verification_state == VerificationState.VERIFIED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Already verified.")
    row = consume_otp(db, identifier_id=ident.id, code=body.code)
    if row is None:
        db.commit()  # persist the attempt counter
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Incorrect or expired code. Request a new one if attempts run out.",
        )
    _mark_verified(db, user.id, ident)
    db.commit()
    return MessageOut(message="Identifier verified.")


@router.delete("/{identifier_id}", response_model=MessageOut)
def remove_identifier(
    identifier_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    subject: Subject = Depends(get_my_subject),
):
    """Removes the seed AND its findings (FK cascade) — data minimization."""
    ident = _owned_identifier(db, subject, identifier_id)
    db.delete(ident)
    record_event(
        db, actor=user_actor(user.id), event_type="identifier.removed",
        subject_id=subject.id, detail={"identifier_id": str(identifier_id)},
    )
    db.commit()
    return MessageOut(message="Identifier and its findings removed.")


def _mark_verified(db, user_id, ident: Identifier) -> None:
    ident.verification_state = VerificationState.VERIFIED
    ident.verified_at = datetime.now(timezone.utc)
    record_event(
        db, actor=user_actor(user_id), event_type="identifier.verified",
        subject_id=ident.subject_id,
        detail={"identifier_id": str(ident.id), "kind": ident.kind.value},
    )
    from ayin.analytics import track  # noqa: PLC0415

    track(db, "identifier_verified", user_id=user_id, properties={"kind": ident.kind.value})
