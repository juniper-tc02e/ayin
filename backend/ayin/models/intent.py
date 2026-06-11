"""Monitoring/removal intent signals (M4-4, PRD §13.2).

Measures the pull toward the paid engine WITHOUT building it: a user raising
their hand for "watch for new exposure" or "remove these listings for me".
One signal per (user, kind); reported as % of activated users (§13.7).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin
from ayin.models.types import str_enum


class IntentKind(str, enum.Enum):
    MONITORING = "monitoring"  # "watch for new exposure"
    REMOVAL = "removal"  # "remove these listings for me"


class IntentSignal(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "intent_signals"
    __table_args__ = (UniqueConstraint("user_id", "kind", name="uq_intent_user_kind"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[IntentKind] = mapped_column(str_enum(IntentKind), nullable=False)
    scan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="SET NULL"), nullable=True
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(nullable=True)
