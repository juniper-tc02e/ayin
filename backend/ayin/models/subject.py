"""Subject (the person being scanned) and their seed Identifiers.

PII note: identifier values (emails, phones, names) are operational subject
data — every read goes through an audited accessor (ayin.safety.audit), and
*sensitive finding payloads* live in the PII vault (M1-5), not here.

MVP invariant: one Subject per User, owner == subject (T0 self-scan only).
The UNIQUE constraint on owner_user_id makes that structural; relaxing it for
higher tiers is a deliberate future migration + ADR.
"""

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin
from ayin.models.enums import IdentifierKind, VerificationState
from ayin.models.types import str_enum


class Subject(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "subjects"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 'none' | 'excluded' — FR-TS-3 "Exclude me from Ayin" (flow lands in M3-4).
    exclusion_state: Mapped[str] = mapped_column(String(16), nullable=False, default="none")

    identifiers: Mapped[list["Identifier"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan"
    )


class Identifier(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "identifiers"
    __table_args__ = (
        UniqueConstraint("subject_id", "kind", "value_normalized", name="uq_identifier_seed"),
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[IdentifierKind] = mapped_column(str_enum(IdentifierKind), nullable=False)
    value_raw: Mapped[str] = mapped_column(String(512), nullable=False)
    value_normalized: Mapped[str] = mapped_column(String(512), nullable=False)
    # FR-AUTH-1: sensitive results stay hidden until control is VERIFIED.
    verification_state: Mapped[VerificationState] = mapped_column(
        str_enum(VerificationState),
        nullable=False,
        default=VerificationState.UNVERIFIED,
        server_default=VerificationState.UNVERIFIED.value,
    )
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    subject: Mapped[Subject] = relationship(back_populates="identifiers")
