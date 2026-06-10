"""Outbound SMS (phone OTP). MVP ships no real SMS provider — dev/console only,
behind the same provider interface a Twilio-class connector will implement."""

import logging
from typing import Protocol

from ayin.config import Settings

log = logging.getLogger("ayin.sms")


class SmsSender(Protocol):
    def send_otp(self, *, to: str, code: str) -> None: ...


class ConsoleSmsSender:
    """Logs the OTP (development only)."""

    def __init__(self, settings: Settings):
        if settings.is_production:
            raise RuntimeError("ConsoleSmsSender must never run in production.")

    def send_otp(self, *, to: str, code: str) -> None:
        log.warning("DEV SMS to %s: your Ayin verification code is %s", to, code)


def get_sms_sender_factory(settings: Settings) -> SmsSender:
    return ConsoleSmsSender(settings)
