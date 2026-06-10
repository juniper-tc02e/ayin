"""Seed identifier validation + normalization (FR-SCAN-1: validate/normalize).

Third-party data is untrusted; so is user input. Everything entering the
identifiers table passes through here.
"""

import re

from email_validator import EmailNotValidError, validate_email

from ayin.models.enums import IdentifierKind

# Kinds whose control can be proven with a challenge (email link / phone OTP).
# Other kinds are auxiliary seeds: usable only alongside a verified anchor
# (enforced at scan-start, M1) and never a key to sensitive results.
CHALLENGEABLE_KINDS = {IdentifierKind.EMAIL, IdentifierKind.PHONE}

_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_PHONE_STRIP_RE = re.compile(r"[\s\-().]")


class IdentifierValidationError(ValueError):
    pass


def normalize_identifier(kind: IdentifierKind, raw: str) -> tuple[str, str]:
    """Return (value_raw_cleaned, value_normalized) or raise IdentifierValidationError."""
    raw = raw.strip()
    if not raw:
        raise IdentifierValidationError("Value is empty.")
    if kind == IdentifierKind.EMAIL:
        try:
            result = validate_email(raw, check_deliverability=False)
        except EmailNotValidError as exc:
            raise IdentifierValidationError(f"Not a valid email address: {exc}") from exc
        return raw, result.normalized.lower()
    if kind == IdentifierKind.PHONE:
        cleaned = _PHONE_STRIP_RE.sub("", raw)
        digits = cleaned[1:] if cleaned.startswith("+") else cleaned
        if not digits.isdigit() or not (8 <= len(digits) <= 15):
            raise IdentifierValidationError(
                "Not a valid phone number (use international format, e.g. +15551234567)."
            )
        # MVP normalization; swap in the `phonenumbers` lib for real E.164 in Phase 1.
        return raw, f"+{digits}" if cleaned.startswith("+") else digits
    if kind == IdentifierKind.USERNAME:
        normalized = raw.lower()
        if not _USERNAME_RE.match(normalized):
            raise IdentifierValidationError(
                "Usernames are 1-64 chars: letters, digits, '.', '_', '-'."
            )
        return raw, normalized
    if kind in (IdentifierKind.FULL_NAME, IdentifierKind.CITY):
        collapsed = re.sub(r"\s+", " ", raw)
        if len(collapsed) > 200:
            raise IdentifierValidationError("Too long (200 chars max).")
        return collapsed, collapsed.lower()
    raise IdentifierValidationError(f"Unsupported identifier kind: {kind}")
