"""Consent endpoints (T1: authorized third-party scans, PRD §20.5).

The flow is consent-first and subject-driven:

- ``POST /consent/requests`` (requester, authed) — ask a subject, by their own
  email, to authorize a bounded scan. A single-use link is emailed to that
  address. This authorizes nothing.
- ``GET /consent/requests/{token}`` (public) — render the ask for the subject.
- ``POST /consent/requests/{token}/accept`` (public) — the subject, holding the
  emailed link and attesting adulthood, authorizes. Mints the grant.
- ``POST /consent/requests/{token}/decline`` (public) — the subject says no.
- ``GET /consent/grants`` (requester, authed) — the requester's live grants.
- ``POST /consent/grants/{grant_id}/revoke`` (authed) — the subject (or the
  requester) withdraws a grant; effective immediately.

The orchestrator gate (``run_gates``) is what actually enforces "no scan without
a live grant"; these endpoints only create/withdraw that grant via the subject.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from ayin.api.deps import CurrentUser, DbDep, SettingsDep
from ayin.api.schemas import (
    ConsentAcceptIn,
    ConsentAcceptOut,
    ConsentAskOut,
    ConsentGrantOut,
    ConsentRequestIn,
    ConsentRequestOut,
)
from ayin.api.routes.auth import get_email_sender
from ayin.consent import flow
from ayin.consent.flow import ConsentFlowError
from ayin.consent.store import active_consent
from ayin.models import ConsentGrant, Subject, User
from ayin.services.email import EmailSender

log = logging.getLogger("ayin.consent")


def require_t1_enabled(settings: SettingsDep) -> None:
    """Hide the entire T1 surface unless explicitly enabled. 404 (not 403) so a
    disabled deployment is indistinguishable from one that never had the feature
    — the consent GATE in the orchestrator stays on regardless."""
    if not settings.consent_t1_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")


router = APIRouter(
    prefix="/consent", tags=["consent"], dependencies=[Depends(require_t1_enabled)]
)

# Flow error code → HTTP status.
_FLOW_HTTP = {
    "purpose_required": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "invalid_subject_email": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "cannot_request_self": status.HTTP_400_BAD_REQUEST,
    "invalid_or_expired": status.HTTP_404_NOT_FOUND,
    "adult_attestation_required": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "cannot_consent_to_self": status.HTTP_409_CONFLICT,
    "already_pending": status.HTTP_409_CONFLICT,
    "rate_limited": status.HTTP_429_TOO_MANY_REQUESTS,
}


def _http_from_flow(exc: ConsentFlowError) -> HTTPException:
    return HTTPException(
        _FLOW_HTTP.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail={"code": exc.code, "message": str(exc)},
    )


def _subject_email(db, subject_id: uuid.UUID) -> str | None:
    owner_id = db.execute(
        select(Subject.owner_user_id).where(Subject.id == subject_id)
    ).scalar_one_or_none()
    if owner_id is None:
        return None
    return db.execute(select(User.email).where(User.id == owner_id)).scalar_one_or_none()


@router.post("/requests", response_model=ConsentRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    body: ConsentRequestIn,
    user: CurrentUser,
    db: DbDep,
    settings: SettingsDep,
    email_sender: EmailSender = Depends(get_email_sender),
):
    try:
        req, raw = flow.request_consent(
            db,
            requester=user,
            subject_email=str(body.subject_email),
            usernames=body.usernames,
            purpose=body.purpose,
            ttl_days=body.ttl_days,
        )
    except ConsentFlowError as exc:
        raise _http_from_flow(exc) from None

    # Deliver the ask to the SUBJECT's own channel. A delivery failure must not
    # 500 the request (the row exists; resend can follow) — mirror the
    # identifier-challenge hardening.
    link = f"{settings.web_base_url}/consent?token={raw}"
    try:
        email_sender.send(
            to=req.subject_email,
            subject=f"{user.email} is requesting your consent to run an Ayin scan",
            body=(
                f"{user.email} would like your permission to run an Ayin exposure "
                f"scan of your public footprint.\n\n"
                f"Purpose: {req.purpose}\n"
                f"If you authorize it, the scan can run for {req.ttl_days} days, "
                f"and you can revoke at any time.\n\n"
                f"Review and decide: {link}\n\n"
                f"If you don't recognize this request, just ignore this email — "
                f"nothing about you will be scanned without your explicit consent."
            ),
        )
    except Exception:  # noqa: BLE001 — delivery is best-effort; never load-bearing
        log.warning("consent ask email could not be delivered to %s", req.subject_email)
    db.commit()
    return ConsentRequestOut(
        id=req.id,
        subject_email=req.subject_email,
        purpose=req.purpose,
        status=req.status,
        ttl_days=req.ttl_days,
        expires_at=req.expires_at,
        created_at=req.created_at,
    )


@router.get("/requests/{token}", response_model=ConsentAskOut)
def view_request(token: str, db: DbDep):
    req = flow.load_request(db, raw_token=token)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This consent link is invalid or expired.")
    requester_email = db.execute(
        select(User.email).where(User.id == req.requester_user_id)
    ).scalar_one_or_none()
    usernames = [u for u in (req.scope_usernames or "").splitlines() if u.strip()]
    return ConsentAskOut(
        requester_email=requester_email or "(unknown)",
        subject_email=req.subject_email,
        purpose=req.purpose,
        usernames=usernames,
        ttl_days=req.ttl_days,
        expires_at=req.expires_at,
    )


@router.post("/requests/{token}/accept", response_model=ConsentAcceptOut)
def accept_request(token: str, body: ConsentAcceptIn, db: DbDep):
    try:
        grant = flow.accept_consent(
            db, raw_token=token, adult_attested=body.adult_attested
        )
    except ConsentFlowError as exc:
        db.rollback()
        raise _http_from_flow(exc) from None
    db.commit()
    return ConsentAcceptOut(
        granted=True, subject_id=grant.subject_id, scope=grant.scope,
        expires_at=grant.expires_at,
    )


@router.post("/requests/{token}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_request(token: str, db: DbDep):
    try:
        flow.decline_consent(db, raw_token=token)
    except ConsentFlowError as exc:
        db.rollback()
        raise _http_from_flow(exc) from None
    db.commit()


@router.get("/grants", response_model=list[ConsentGrantOut])
def my_grants(user: CurrentUser, db: DbDep):
    """Live grants the current user holds as a requester."""
    grants = flow.active_grants_for_requester(db, requester_user_id=user.id)
    return [
        ConsentGrantOut(
            id=g.id, subject_id=g.subject_id, subject_email=_subject_email(db, g.subject_id),
            purpose=g.purpose, scope=g.scope, granted_at=g.granted_at, expires_at=g.expires_at,
        )
        for g in grants
    ]


@router.post("/grants/{grant_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke_grant_endpoint(grant_id: uuid.UUID, user: CurrentUser, db: DbDep):
    """Withdraw a grant. Permitted for the SUBJECT (their right) or the REQUESTER
    (giving up their own access) — both only ever reduce access, never expand it.

    A login-less subject (created via a consent link) can't authenticate here; a
    tokened email revoke link for that case is a follow-up. The grant is always
    time-bound regardless, and the requester can revoke on the subject's behalf.
    """
    grant = db.get(ConsentGrant, grant_id)
    if grant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grant not found.")
    owner_id = db.execute(
        select(Subject.owner_user_id).where(Subject.id == grant.subject_id)
    ).scalar_one_or_none()
    if user.id not in {owner_id, grant.requester_user_id}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your grant to revoke.")
    if active_consent(db, subject_id=grant.subject_id, requester_user_id=grant.requester_user_id):
        flow.revoke_consent(db, grant=grant)
        db.commit()
