"""Beta invites (M5-1).

The private beta is invite-only: a recruited cohort of self/consented
subjects (BUILD-PLAN M5-1). Codes are short and human-readable, multi-use
capable (waves), expirable, revocable. Managed via the CLI
(python -m ayin.beta.invites) — no admin UI in MVP.
"""

from datetime import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin


class Invite(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "invites"

    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    # Operator context (wave name, channel) — never the invitee's identity.
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    uses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
