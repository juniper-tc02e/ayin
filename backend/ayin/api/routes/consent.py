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
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
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
from ayin.models import ConsentGrant, Subject, User
from ayin.safety.ip_throttle import IpRateLimiter
from ayin.services.email import EmailSender

log = logging.getLogger("ayin.consent")

# Per-IP throttle for the UNAUTHENTICATED token endpoints (view/accept/decline/
# revoke-by-token). Module-global so it persists across requests; process-local.
_public_limiter = IpRateLimiter(max_hits=30, window_seconds=300)


def public_throttle(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    if not _public_limiter.allow(ip):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests — please wait a moment and try again.",
        )


def require_t1_enabled(settings: SettingsDep) -> None:
    """Gate NEW consent-request creation when T1 is disabled (404, so a disabled
    deployment is indistinguishable from one without the feature).

    NOTE: this is applied ONLY to request creation — NOT to accept/decline/view
    or to either revoke path. A subject must always be able to withdraw an
    existing grant (bright line: revocable), and existing asks must stay
    actionable, regardless of whether NEW asks are currently allowed. The
    orchestrator consent gate is likewise always-on."""
    if not settings.consent_t1_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")


router = APIRouter(prefix="/consent", tags=["consent"])

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
    "minor_suspected": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "screening_failed": status.HTTP_409_CONFLICT,
}


def _http_from_flow(exc: ConsentFlowError) -> HTTPException:
    return HTTPException(
        _FLOW_HTTP.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail={"code": exc.code, "message": str(exc)},
    )


def _safe_send(sender: EmailSender, to: str, subject: str, body: str) -> None:
    """Best-effort send used as a background task — never raises into the request."""
    try:
        sender.send(to=to, subject=subject, body=body)
    except Exception:  # noqa: BLE001
        log.warning("consent email could not be delivered")  # no PII in logs


def _subject_email(db, subject_id: uuid.UUID) -> str | None:
    owner_id = db.execute(
        select(Subject.owner_user_id).where(Subject.id == subject_id)
    ).scalar_one_or_none()
    if owner_id is None:
        return None
    return db.execute(select(User.email).where(User.id == owner_id)).scalar_one_or_none()


@router.post(
    "/requests", response_model=ConsentRequestOut, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_t1_enabled)],
)
def create_request(
    body: ConsentRequestIn,
    user: CurrentUser,
    db: DbDep,
    settings: SettingsDep,
    background: BackgroundTasks,
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

    # Deliver the ask ONLY when the target isn't screened (excluded/protected/
    # minor). The send is scheduled AFTER the response (BackgroundTasks) so the
    # HTTP latency does not depend on the screening outcome — no timing oracle —
    # and a screened row is created + returned identically but never emailed.
    if not req.screened:
        link = f"{settings.web_base_url}/consent?token={raw}"
        background.add_task(
            _safe_send, email_sender, req.subject_email,
            f"{user.email} is requesting your consent to run an Ayin scan",
            (
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
    # Response is built from the real row in BOTH cases — identical shape, and the
    # purpose is the sanitized stored value (no unsanitized-echo content oracle).
    out = ConsentRequestOut(
        id=req.id, subject_email=req.subject_email, purpose=req.purpose,
        status=req.status, ttl_days=req.ttl_days, expires_at=req.expires_at,
        created_at=req.created_at,
    )
    db.commit()
    return out


@router.get(
    "/requests/{token}", response_model=ConsentAskOut,
    dependencies=[Depends(public_throttle)],
)
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


@router.post(
    "/requests/{token}/accept", response_model=ConsentAcceptOut,
    dependencies=[Depends(public_throttle)],
)
def accept_request(
    token: str,
    body: ConsentAcceptIn,
    db: DbDep,
    settings: SettingsDep,
    email_sender: EmailSender = Depends(get_email_sender),
):
    try:
        grant = flow.accept_consent(
            db, raw_token=token, adult_attested=body.adult_attested
        )
    except ConsentFlowError as exc:
        db.rollback()
        raise _http_from_flow(exc) from None
    # Capture before commit (mapped attrs expire on commit; the raw revoke token
    # is an unmapped transient set by accept_consent).
    subject_id = grant.subject_id
    requester_id = grant.requester_user_id
    scope = grant.scope
    expires_at = grant.expires_at
    raw_revoke = getattr(grant, "raw_revoke_token", None)
    db.commit()

    # Confirmation email to the SUBJECT carrying the one-click revoke link, so a
    # login-less subject can withdraw any time. Best-effort — never 500s accept.
    if raw_revoke:
        subj_email = _subject_email(db, subject_id)
        requester_email = db.execute(
            select(User.email).where(User.id == requester_id)
        ).scalar_one_or_none()
        revoke_link = f"{settings.web_base_url}/consent/revoke?token={raw_revoke}"
        if subj_email:
            try:
                email_sender.send(
                    to=subj_email,
                    subject="You authorized an Ayin scan — how to revoke",
                    body=(
                        f"You authorized {requester_email or 'a requester'} to run an "
                        f"Ayin exposure scan of your public footprint.\n\n"
                        f"This consent is time-bound and you can withdraw it at any "
                        f"time — one click, no account needed:\n{revoke_link}\n\n"
                        f"If you did not authorize this, use the link above to revoke "
                        f"immediately."
                    ),
                )
            except Exception:  # noqa: BLE001 — delivery is best-effort
                log.warning("consent revoke-link email could not be delivered")
    return ConsentAcceptOut(
        granted=True, subject_id=subject_id, scope=scope, expires_at=expires_at,
    )


@router.post(
    "/requests/{token}/decline", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(public_throttle)],
)
def decline_request(token: str, db: DbDep):
    try:
        flow.decline_consent(db, raw_token=token)
    except ConsentFlowError as exc:
        db.rollback()
        raise _http_from_flow(exc) from None
    db.commit()


@router.post(
    "/revoke/{token}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(public_throttle)],
)
def revoke_by_token_endpoint(token: str, db: DbDep):
    """The subject's one-click revoke link (no login). Revokes the whole
    (subject, requester) pair the token belongs to; 404 if the token is unknown."""
    if not flow.revoke_by_token(db, raw_token=token):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This revoke link is invalid.")
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
    """Withdraw consent. Permitted for the SUBJECT (their right, when they have an
    account) or the REQUESTER (giving up their own access) — both only ever reduce
    access. Login-less subjects use the one-click email link (POST /consent/revoke/
    {token}). Revokes ALL live grants for the pair and always audits the attempt,
    so a duplicate grant can't survive and the trail is honest."""
    grant = db.get(ConsentGrant, grant_id)
    if grant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grant not found.")
    owner_id = db.execute(
        select(Subject.owner_user_id).where(Subject.id == grant.subject_id)
    ).scalar_one_or_none()
    if user.id not in {owner_id, grant.requester_user_id}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your grant to revoke.")
    flow.revoke_consent(db, grant=grant, actor_user_id=user.id)
    db.commit()
