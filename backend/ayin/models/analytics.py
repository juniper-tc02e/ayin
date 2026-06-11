"""First-party analytics events (M4-2).

Strictly pseudonymous: ``user_ref`` is a keyed hash, properties pass a PII
screen before insert (ayin.analytics.events). No emails, no identifier
values, no finding contents — ever. Safe to export to any analytics tool.
"""

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin


class AnalyticsEvent(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "analytics_events"
    __table_args__ = (Index("ix_analytics_name_created", "name", "created_at"),)

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # sha256(app_secret : user_id)[:16] — stable per user, reversible by no one.
    user_ref: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # scan ids are opaque uuids (not PII); kept whole for funnel joins.
    scan_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
