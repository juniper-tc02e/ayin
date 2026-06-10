"""Versioned ToS/AUP acceptance (FR-AUTH-2). One row per (user, version) —
history is kept; the gate checks for the *current* version."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, UuidPkMixin


class TosAcceptance(Base, UuidPkMixin):
    __tablename__ = "tos_acceptances"
    __table_args__ = (UniqueConstraint("user_id", "version", name="uq_tos_user_version"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
