"""User account (requester). For T0 the requester and the subject are the same
person; the Subject entity stays separate so later tiers don't rework the core."""

from datetime import datetime

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin


class User(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "users"

    # Stored lowercased/normalized; uniqueness enforced on the normalized form.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    # Null for OAuth-only accounts (Google OAuth is env-gated, off by default in MVP).
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="free")
