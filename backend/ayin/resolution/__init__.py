"""Entity resolution (M2-1/M2-2, FR-ER-1/2).

MVP scope is deliberately narrow: resolution runs only over the verified
requester's own scan results — "is this finding about me?" — not open
cross-person identity resolution. False merges are the enemy: the design
makes silently absorbing a namesake structurally impossible.
"""

from ayin.resolution.engine import resolve_scan

__all__ = ["resolve_scan"]
