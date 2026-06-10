"""Outbound email — verification links/OTPs only (no marketing machinery).

Dev: docker-compose ships MailDev (SMTP :1025, UI :1080). If SMTP is
unreachable and ``email_console_fallback`` is on (non-production only),
the message is logged instead so local flows never dead-end.
"""

import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from ayin.config import Settings

log = logging.getLogger("ayin.email")


class EmailSender(Protocol):
    def send(self, *, to: str, subject: str, body: str) -> None: ...


class SmtpEmailSender:
    def __init__(self, settings: Settings):
        self._settings = settings

    def send(self, *, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self._settings.email_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        try:
            with smtplib.SMTP(
                self._settings.smtp_host, self._settings.smtp_port, timeout=5
            ) as smtp:
                smtp.send_message(msg)
        except OSError:
            if self._settings.email_console_fallback and not self._settings.is_production:
                log.warning("SMTP unreachable — console fallback.\nTo: %s\nSubject: %s\n%s",
                            to, subject, body)
            else:
                raise


def get_email_sender_factory(settings: Settings) -> EmailSender:
    return SmtpEmailSender(settings)
