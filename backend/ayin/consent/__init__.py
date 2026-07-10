"""Consent for authorized third-party scans (T1+).

Self-scan (T0) needs nothing here. For any scan where the requester is not the
subject's owner, the orchestrator gate requires ``active_consent`` to return a
live grant — created only by the subject's own verified action.
"""

from ayin.consent.flow import (
    ConsentFlowError,
    accept_consent,
    active_grants_for_requester,
    decline_consent,
    load_request,
    request_consent,
    revoke_by_token,
    revoke_consent,
)
from ayin.consent.store import (
    active_consent,
    record_grant,
    revoke_all_active,
    revoke_grant,
)

__all__ = [
    "active_consent",
    "record_grant",
    "revoke_grant",
    "revoke_all_active",
    "ConsentFlowError",
    "request_consent",
    "load_request",
    "accept_consent",
    "decline_consent",
    "revoke_consent",
    "revoke_by_token",
    "active_grants_for_requester",
]
