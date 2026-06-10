"""Single-use verification tokens (account email, identifier email, phone OTP).

Only a sha256 of the secret is stored — a DB leak doesn't yield usable links.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin
from ayin.models.types import str_enum


class TokenKind(str, enum.Enum):
    ACCOUNT_EMAIL = "account_email"
    IDENTIFIER_EMAIL = "identifier_email"
    IDENTIFIER_PHONE_OTP = "identifier_phone_otp"


class VerificationToken(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "verification_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("identifiers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind: Mapped[TokenKind] = mapped_column(str_enum(TokenKind), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
