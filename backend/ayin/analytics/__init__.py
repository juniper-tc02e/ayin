"""Privacy-respecting product analytics (M4-2, PRD §13.7).

The funnel must be measurable without ever shipping PII: every event passes
an allowlist + content screen before it is stored.
"""

from ayin.analytics.events import track

__all__ = ["track"]
