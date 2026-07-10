"""Per-IP sliding-window throttle for unauthenticated endpoints.

The public consent endpoints (view / accept / decline / revoke-by-token) carry a
256-bit token, so online brute-force is infeasible — but they are still
unauthenticated and state-changing, so an IP limiter is defense-in-depth against
enumeration/replay hammering (§20.5 "rate-limit it" applied to the redemption
surface, not just request creation).

Process-local + in-memory: bounds abuse per worker without a Redis dependency.
For the MVP that is enough; a shared store is a later upgrade.
"""

import time
from collections import defaultdict, deque
from threading import Lock


class IpRateLimiter:
    def __init__(self, max_hits: int, window_seconds: float):
        self.max_hits = max_hits
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, *, now: float | None = None) -> bool:
        """Record a hit for ``key`` and return whether it is within the window
        budget. False ⇒ the caller should refuse (429)."""
        now = time.monotonic() if now is None else now
        cutoff = now - self.window
        with self._lock:
            dq = self._hits[key]
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= self.max_hits:
                return False
            dq.append(now)
            return True

    def reset(self) -> None:
        """Clear all counters (tests use this so a process-global limiter doesn't
        leak state across cases)."""
        with self._lock:
            self._hits.clear()
