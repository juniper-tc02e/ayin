"""Outbound SMS (phone OTP). MVP ships no real SMS provider — dev/console only,
behind the same provider interface a Twilio-class connector will implement."""

import logging
from typing import Protocol

from ayin.config import Settings

log = logging.getLogger("ayin.sms")


class SmsSender(Protocol):
    def send_otp(self, *, to: str, code: str) -> None: ...


class ConsoleSmsSender:
    """Logs the OTP (development only).

    The production guard lives in ``send_otp`` (the actual send), NOT in
    ``__init__``: this sender is wired as a FastAPI dependency on the identifier
    routes, so it is constructed for *every* request (e.g. adding an email or
    username) even when no SMS is sent. Raising at construction therefore 500'd
    every identifier add in production; the guard belongs at the send instead, so
    it still refuses to actually log an OTP in prod without breaking unrelated
    operations.
    """

    def __init__(self, settings: Settings):
        self._settings = settings

    def send_otp(self, *, to: str, code: str) -> None:
        if self._settings.is_production:
            raise RuntimeError("ConsoleSmsSender must never send in production.")
        log.warning("DEV SMS to %s: your Ayin verification code is %s", to, code)


def get_sms_sender_factory(settings: Settings) -> SmsSender:
    return ConsoleSmsSender(settings)
