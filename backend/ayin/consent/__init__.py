"""Consent for authorized third-party scans (T1+).

Self-scan (T0) needs nothing here. For any scan where the requester is not the
subject's owner, the orchestrator gate requires ``active_consent`` to return a
live grant — created only by the subject's own verified action.
"""

from ayin.consent.store import active_consent, record_grant, revoke_grant

__all__ = ["active_consent", "record_grant", "revoke_grant"]
