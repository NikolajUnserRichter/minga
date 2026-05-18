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

from sqlalchemy.orm import Session

from app.services.settings_service import get_setting


logger = logging.getLogger(__name__)


class EmailNotConfiguredError(RuntimeError):
    """SMTP-Settings unvollständig — wird vom Endpoint zu 503 gemappt."""


def _truthy(s: Optional[str]) -> bool:
    return (s or "").strip().lower() in ("true", "1", "yes", "ja")


def send_email(
    db: Session,
    to: str,
    subject: str,
    body: str,
    attachment_bytes: Optional[bytes] = None,
    attachment_filename: Optional[str] = None,
    attachment_mimetype: str = "application/pdf",
) -> None:
    """Verschickt eine E-Mail mit optionalem Anhang.

    Settings werden aus DB (Admin-Center) gelesen — Fallback auf env-Vars.
    Wirft `EmailNotConfiguredError` wenn SMTP nicht konfiguriert ist.
    Andere Fehler (Verbindungsabbruch, Auth-Fehler) bubblen als Exception hoch
    und werden vom Endpoint zu 502 gemappt.
    """
    host = get_setting(db, "SMTP_HOST")
    port_raw = get_setting(db, "SMTP_PORT") or "587"
    user = get_setting(db, "SMTP_USER")
    password = get_setting(db, "SMTP_PASSWORD") or ""
    use_tls = _truthy(get_setting(db, "SMTP_USE_TLS"))
    use_ssl = _truthy(get_setting(db, "SMTP_USE_SSL"))
    from_email = get_setting(db, "EMAILS_FROM_EMAIL") or user
    from_name = get_setting(db, "EMAILS_FROM_NAME") or ""

    if not host or host == "localhost" or not user:
        raise EmailNotConfiguredError(
            "SMTP-Versand nicht konfiguriert — bitte im Admin-Center unter Einstellungen die SMTP-Daten hinterlegen."
        )

    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        port = 587

    msg = EmailMessage()
    msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
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

    timeout = 10
    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            smtp.ehlo()
            if use_tls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)

    logger.info("Email '%s' an %s verschickt", subject, to)
