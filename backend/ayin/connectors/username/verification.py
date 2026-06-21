"""Username Footprint — Tier-1 ownership verification (UF5).

A username can't be email/phone-challenged, so we offer a self-serve OWNERSHIP
PROOF: issue a short code; the user pastes it anywhere in their PUBLIC profile
(bio / display name) on one of their sites; Ayin re-fetches that public page and
confirms the code is present. Control of the page = proof of control of the handle.
On success the Identifier is marked VERIFIED, which (a) upgrades the footprint
connector's ownership tier asserted→verified, (b) lifts the anti-namesake cap in
resolution (a proven-owned handle is not a namesake), and (c) is required — with an
explicit per-scan opt-in — before any sensitive/nsfw site is probed.

Stateless: the code is an HMAC of the identifier id under the app secret, so there
is nothing to store and it is stable across retries. The code is NOT a secret (it
is meant to be posted publicly) — it only proves control of the page, never grants
access. OAuth is the stronger proof where a platform supports it; this bio-code
path is the universal fallback and needs no per-platform app registration.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from ayin.config import Settings
from ayin.connectors.username.connector import USER_AGENT
from ayin.models import Identifier
from ayin.models.enums import IdentifierKind, VerificationState

log = logging.getLogger("ayin.connectors.username.verification")

_CODE_PREFIX = "ayin-verify-"


class UsernameVerificationError(ValueError):
    """The profile could not be fetched, or the kind/input was invalid."""


def challenge_code(identifier_id: uuid.UUID, settings: Settings) -> str:
    """Deterministic, stateless ownership-proof code for this username identifier."""
    mac = hmac.new(
        settings.app_secret.encode(), str(identifier_id).encode(), hashlib.sha256
    )
    return _CODE_PREFIX + mac.hexdigest()[:12]


def profile_proves_ownership(profile_url: str, code: str, client: httpx.Client) -> bool:
    """Fetch the public profile page and return whether ``code`` appears in it.
    Raises UsernameVerificationError on fetch failure (so 'not found' and 'could
    not check' are never conflated)."""
    try:
        resp = client.get(
            profile_url, headers={"user-agent": USER_AGENT}, follow_redirects=True
        )
    except httpx.HTTPError as exc:
        raise UsernameVerificationError(f"could not fetch the profile page: {exc}") from exc
    if resp.status_code != 200:
        raise UsernameVerificationError(
            f"profile page returned HTTP {resp.status_code} — can't verify"
        )
    return code.lower() in resp.text.lower()


def verify_and_record(
    db: Session,
    identifier: Identifier,
    profile_url: str,
    settings: Settings,
    *,
    client: httpx.Client | None = None,
) -> bool:
    """Verify ownership of ``identifier`` (a username) via the bio-code on
    ``profile_url``. On success, mark the identifier VERIFIED and flush. Returns
    True iff verified. The caller commits + writes the audit record."""
    if identifier.kind is not IdentifierKind.USERNAME:
        raise UsernameVerificationError("ownership verification is for usernames only")
    code = challenge_code(identifier.id, settings)
    owns_client = client or httpx.Client(timeout=10)
    try:
        proven = profile_proves_ownership(profile_url, code, owns_client)
    finally:
        if client is None:
            owns_client.close()
    if proven:
        identifier.verification_state = VerificationState.VERIFIED
        identifier.verified_at = datetime.now(timezone.utc)
        db.flush()
        log.info("username ownership verified via bio-code (identifier %s)", identifier.id)
    return proven
