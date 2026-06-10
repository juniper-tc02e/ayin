"""Rate-limit policy rows (FR-SCAN-3, M1-6).

Limits are data, not deploys: support/T&S can tighten or loosen a plan's
caps with an UPDATE. Environment settings only seed/fallback these rows.
"""

from datetime import datetime

from sqlalchemy import Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, UuidPkMixin


class RateLimitPolicy(Base, UuidPkMixin):
    __tablename__ = "rate_limit_policies"

    # plan name ('free', 'pro', ...) — per-tier caps when tiers arrive
    scope: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    scans_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    scan_burst: Mapped[int] = mapped_column(Integer, nullable=False)
    burst_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
