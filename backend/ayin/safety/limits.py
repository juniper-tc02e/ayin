"""Scan rate/volume enforcement (FR-SCAN-3, M1-6).

Checked inside the scan gate (the critical path). Policies live in the
``rate_limit_policies`` table so limits change WITHOUT a deploy; environment
settings are only the fallback/seed values. Repeated hammering after refusals
writes an AbuseSignal (velocity) for the T&S review queue.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ayin.config import Settings
from ayin.models import AbuseSignal, Scan, User
from ayin.models.enums import AbuseSignalKind, AbuseSignalSeverity

# Refusals inside this window before we raise an abuse signal.
_HAMMERING_WINDOW_MINUTES = 60
_HAMMERING_THRESHOLD = 3


@dataclass(frozen=True)
class LimitDecision:
    allowed: bool
    message: str = ""
    retry_after_seconds: int | None = None


@dataclass(frozen=True)
class Policy:
    scans_per_day: int
    scan_burst: int
    burst_window_minutes: int


def get_policy(db: Session, plan: str, settings: Settings) -> Policy:
    """DB row for the plan if present (live-changeable), else env defaults."""
    from ayin.models.ratelimit import RateLimitPolicy  # noqa: PLC0415

    row = db.execute(
        select(RateLimitPolicy).where(RateLimitPolicy.scope == plan)
    ).scalar_one_or_none()
    if row is None and plan != "free":
        row = db.execute(  # unknown plan → free-plan caps, never uncapped
            select(RateLimitPolicy).where(RateLimitPolicy.scope == "free")
        ).scalar_one_or_none()
    if row is not None:
        return Policy(
            scans_per_day=row.scans_per_day,
            scan_burst=row.scan_burst,
            burst_window_minutes=row.burst_window_minutes,
        )
    return Policy(
        scans_per_day=settings.rate_limit_scans_per_day,
        scan_burst=settings.rate_limit_burst,
        burst_window_minutes=10,
    )


def check_scan_allowed(
    db: Session, user_id: uuid.UUID, settings: Settings,
    *, exclude_scan_id: uuid.UUID | None = None,
) -> LimitDecision:
    """``exclude_scan_id``: the scan being gated right now — it must not
    count toward its own limit."""
    user = db.get(User, user_id)
    policy = get_policy(db, user.plan if user else "free", settings)
    now = datetime.now(timezone.utc)

    def _count_since(cutoff: datetime) -> int:
        q = select(func.count(Scan.id)).where(
            Scan.requester_user_id == user_id, Scan.created_at >= cutoff
        )
        if exclude_scan_id is not None:
            q = q.where(Scan.id != exclude_scan_id)
        return db.execute(q).scalar_one()

    burst_cutoff = now - timedelta(minutes=policy.burst_window_minutes)
    if _count_since(burst_cutoff) >= policy.scan_burst:
        _maybe_signal_hammering(db, user_id)
        return LimitDecision(
            allowed=False,
            message=(
                f"Too many scans at once — at most {policy.scan_burst} per "
                f"{policy.burst_window_minutes} minutes. Try again shortly."
            ),
            retry_after_seconds=policy.burst_window_minutes * 60,
        )

    day_cutoff = now - timedelta(hours=24)
    if _count_since(day_cutoff) >= policy.scans_per_day:
        _maybe_signal_hammering(db, user_id)
        return LimitDecision(
            allowed=False,
            message=(
                f"Daily scan limit reached ({policy.scans_per_day} per 24h). "
                "Your exposure rarely changes hour-to-hour — check back tomorrow."
            ),
            retry_after_seconds=3600,
        )
    return LimitDecision(allowed=True)


def _maybe_signal_hammering(db: Session, user_id: uuid.UUID) -> None:
    """≥N rate-limit refusals within the window → velocity AbuseSignal
    (FR-TS-2 telemetry; review tooling lands in M3)."""
    window_start = datetime.now(timezone.utc) - timedelta(minutes=_HAMMERING_WINDOW_MINUTES)
    refusals = db.execute(
        select(func.count(Scan.id)).where(
            Scan.requester_user_id == user_id,
            Scan.error.like("rate_limited%"),
            Scan.created_at >= window_start,
        )
    ).scalar_one()
    if refusals < _HAMMERING_THRESHOLD:
        return
    recent_signal = db.execute(
        select(AbuseSignal.id).where(
            AbuseSignal.user_id == user_id,
            AbuseSignal.kind == AbuseSignalKind.VELOCITY,
            AbuseSignal.created_at >= window_start,
        )
    ).first()
    if recent_signal is None:
        db.add(
            AbuseSignal(
                user_id=user_id,
                kind=AbuseSignalKind.VELOCITY,
                severity=AbuseSignalSeverity.WARN,
                detail={"refusals_in_window": int(refusals)},
            )
        )
        db.flush()
