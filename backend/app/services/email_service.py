"""Synchroner SMTP-Versand für Belege (AB, Lieferschein, Rechnung).

Bewusst minimalistisch: stdlib smtplib + email.message, keine zusätzliche
Dependency. Auf IONOS-Webhosting üblicherweise Port 465 (SSL) oder 587 (STARTTLS).

Env-Konfiguration:
    SMTP_HOST=mx.minga-greens.de
    SMTP_PORT=587
    SMTP_USER=hello@minga-greens.de
    SMTP_PASSWORD=…
    SMTP_USE_TLS=true        # STARTTLS (Port 587)
    SMTP_USE_SSL=false       # Direct SSL (Port 465)
    EMAILS_FROM_EMAIL=hello@minga-greens.de
    EMAILS_FROM_NAME="Minga Greens"
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from app.config import get_settings


logger = logging.getLogger(__name__)


class EmailNotConfiguredError(RuntimeError):
    """SMTP-Settings unvollständig — wird vom Endpoint zu 503 gemappt."""


def send_email(
    to: str,
    subject: str,
    body: str,
    attachment_bytes: Optional[bytes] = None,
    attachment_filename: Optional[str] = None,
    attachment_mimetype: str = "application/pdf",
) -> None:
    """Verschickt eine E-Mail mit optionalem Anhang.

    Wirft `EmailNotConfiguredError` wenn SMTP nicht konfiguriert ist.
    Andere Fehler (Verbindungsabbruch, Auth-Fehler) bubblen als Exception hoch
    und werden vom Endpoint zu 502 gemappt.
    """
    s = get_settings()

    if not s.smtp_host or s.smtp_host == "localhost" or not s.smtp_user:
        raise EmailNotConfiguredError(
            "SMTP-Versand nicht konfiguriert — bitte SMTP_HOST/USER/PASSWORD in den env-Vars setzen."
        )

    msg = EmailMessage()
    from_address = s.emails_from_email or s.smtp_user
    msg["From"] = f"{s.emails_from_name} <{from_address}>" if s.emails_from_name else from_address
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    if attachment_bytes and attachment_filename:
        maintype, _, subtype = attachment_mimetype.partition("/")
        msg.add_attachment(
            attachment_bytes,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=attachment_filename,
        )

    if s.smtp_use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout, context=context) as smtp:
            smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout) as smtp:
            smtp.ehlo()
            if s.smtp_use_tls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)

    logger.info("Email '%s' an %s verschickt", subject, to)
