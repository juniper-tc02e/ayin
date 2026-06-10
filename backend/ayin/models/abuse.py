"""AbuseSignal — safety telemetry + (for MVP) the review-case lifecycle.

PRD §10.4 lists AbuseSignal and ReviewCase separately; for the MVP the
``status`` lifecycle on the signal covers review workflow. Split into a
dedicated ReviewCase entity when reviewer tooling lands (FR-TS-2 full).
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin
from ayin.models.enums import AbuseSignalKind, AbuseSignalSeverity, AbuseSignalStatus
from ayin.models.types import str_enum


class AbuseSignal(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "abuse_signals"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    scan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[AbuseSignalKind] = mapped_column(str_enum(AbuseSignalKind), nullable=False)
    severity: Mapped[AbuseSignalSeverity] = mapped_column(
        str_enum(AbuseSignalSeverity), nullable=False, default=AbuseSignalSeverity.INFO
    )
    status: Mapped[AbuseSignalStatus] = mapped_column(
        str_enum(AbuseSignalStatus), nullable=False, default=AbuseSignalStatus.OPEN
    )
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
