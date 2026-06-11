"""Event tracking with a hard PII screen (M4-2).

Rules, enforced at write time (not by convention):
- Only ALLOWED_EVENTS names are accepted.
- Only allowlisted property KEYS are accepted.
- Property VALUES are screened: no '@' (emails), no 7+ digit runs (phones),
  no values longer than 64 chars (free text = leak risk), only scalar types.
- The user is referenced by a keyed pseudonymous hash, never an id that
  appears in operational tables' foreign keys, never an email.

A violating property raises in development/tests (so leaks fail loudly) and
is dropped with a warning in production (so analytics bugs never break the
product path).
"""

import hashlib
import logging
import re
import uuid

from sqlalchemy.orm import Session

from ayin.config import get_settings
from ayin.models.analytics import AnalyticsEvent

log = logging.getLogger("ayin.analytics")

ALLOWED_EVENTS = {
    "signup_completed",
    "invite_redeemed",
    "identifier_added",
    "identifier_verified",
    "tos_accepted",
    "scan_started",
    "scan_refused",
    "scan_held",
    "scan_completed",
    "report_viewed",
    "action_started",
    "finding_reviewed",
    "monitoring_intent_captured",
    "removal_intent_captured",
    "account_deleted",
}

ALLOWED_PROPERTY_KEYS = {
    "kind",  # identifier kind / intent kind — enum-ish strings only
    "category",
    "reason_code",  # first token of a gate reason, e.g. 'rate_limited'
    "score_band",  # minimal|low|moderate|high|severe — never the raw score? band is fine
    "overall",  # 0-100 int — a number about data exposure, not identity
    "findings_count",
    "duration_seconds",
    "connectors",
    "decision",
    "effort",
    "source",  # connector id
}

_DIGIT_RUN_RE = re.compile(r"\d{7,}")


class AnalyticsPIIError(ValueError):
    pass


def user_ref_for(user_id: uuid.UUID | str) -> str:
    secret = get_settings().app_secret
    return hashlib.sha256(f"{secret}:{user_id}".encode()).hexdigest()[:16]


def _screen_value(key: str, value) -> bool:
    if isinstance(value, bool | int | float) or value is None:
        return True
    if isinstance(value, str):
        if len(value) > 64 or "@" in value or _DIGIT_RUN_RE.search(value):
            return False
        return True
    if isinstance(value, list):
        return all(_screen_value(key, v) for v in value)
    return False  # dicts/objects: too easy to smuggle PII


def _screened(properties: dict | None) -> dict:
    if not properties:
        return {}
    settings = get_settings()
    clean: dict = {}
    for key, value in properties.items():
        ok = key in ALLOWED_PROPERTY_KEYS and _screen_value(key, value)
        if ok:
            clean[key] = value
            continue
        message = f"analytics: property {key!r} rejected by PII screen"
        if settings.is_production:  # never break product paths in prod
            log.warning("%s — dropped", message)
        else:
            raise AnalyticsPIIError(message)
    return clean


def track(
    db: Session,
    name: str,
    *,
    user_id: uuid.UUID | str | None = None,
    scan_id: uuid.UUID | str | None = None,
    properties: dict | None = None,
) -> None:
    """Record one funnel event. Never raises in production; raises loudly on
    PII-screen violations everywhere else."""
    if name not in ALLOWED_EVENTS:
        message = f"analytics: unknown event {name!r}"
        if get_settings().is_production:
            log.warning("%s — dropped", message)
            return
        raise AnalyticsPIIError(message)
    db.add(
        AnalyticsEvent(
            name=name,
            user_ref=user_ref_for(user_id) if user_id is not None else None,
            scan_ref=str(scan_id) if scan_id is not None else None,
            properties=_screened(properties),
        )
    )
    db.flush()
