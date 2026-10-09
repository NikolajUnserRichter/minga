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
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Optional, Union

from sqlalchemy.orm import Session

from app.services.settings_service import get_setting


logger = logging.getLogger(__name__)


class EmailNotConfiguredError(RuntimeError):
    """SMTP-Settings unvollständig — wird vom Endpoint zu 503 gemappt."""


def _truthy(s: Optional[str]) -> bool:
    return (s or "").strip().lower() in ("true", "1", "yes", "ja")


@dataclass
class VersandErgebnis:
    """Antwort des Mailservers auf eine verschickte Mail.

    message_id: Message-ID der Mail (steht im Versandprotokoll).
    abgelehnt:  Adressen, die der Server einzeln abgelehnt hat, mit seiner
                Antwort ("550 …"). Leer = alle Empfänger angenommen. Lehnt
                der Server ALLE ab, wirft smtplib SMTPRecipientsRefused.
    """
    message_id: str
    abgelehnt: dict[str, str] = field(default_factory=dict)


def pruefe_smtp_konfiguration(db: Session) -> None:
    """Wirft EmailNotConfiguredError, wenn SMTP nicht konfiguriert ist.

    Dieselbe Prüfung wie in send_email, als eigene Funktion: "Mailen" eines
    Rechnungsentwurfs prüft VOR dem Festschreiben (Paket 3, Q1). Sonst
    hinterließe ein Mandant ohne SMTP eine ausgestellte, unversendete
    Rechnung — bei jedem Klick, nicht nur bei einer Störung.
    """
    host = get_setting(db, "SMTP_HOST")
    if not host or host == "localhost" or not get_setting(db, "SMTP_USER"):
        raise EmailNotConfiguredError(
            "SMTP-Versand nicht konfiguriert — bitte im Admin-Center unter Einstellungen die SMTP-Daten hinterlegen."
        )


def send_email(
    db: Session,
    to: Union[str, list[str]],
    subject: str,
    body: str,
    attachment_bytes: Optional[bytes] = None,
    attachment_filename: Optional[str] = None,
    attachment_mimetype: str = "application/pdf",
    cc: Optional[list[str]] = None,
) -> VersandErgebnis:
    """Verschickt EINE E-Mail mit optionalem Anhang an alle Empfänger.

    `to` ist eine Adresse oder eine Liste; alle stehen gemeinsam im An-Feld
    (Gernot, 08.10.2026: eine Mail, alle Adressen sichtbar). `cc` optional.
    Die Adressen prüft der Aufrufer (app.core.email_adressen.pruefe_empfaenger).
    Rückgabe: Message-ID und die vom Server einzeln abgelehnten Adressen.

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

    pruefe_smtp_konfiguration(db)

    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        port = 587

    an = [to] if isinstance(to, str) else list(to)
    kopie = list(cc or [])
    if not an:
        raise ValueError("Kein Empfänger angegeben")

    msg = EmailMessage()
    msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
    msg["To"] = ", ".join(an)
    if kopie:
        msg["Cc"] = ", ".join(kopie)
    msg["Subject"] = subject
    absender_domain = from_email.rsplit("@", 1)[-1] if from_email and "@" in from_email else "localhost"
    msg["Message-ID"] = make_msgid(domain=absender_domain)
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
    umschlag = an + kopie
    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as smtp:
            smtp.login(user, password)
            abgelehnt_roh = smtp.send_message(msg, to_addrs=umschlag)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            smtp.ehlo()
            if use_tls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if user:
                smtp.login(user, password)
            abgelehnt_roh = smtp.send_message(msg, to_addrs=umschlag)

    abgelehnt: dict[str, str] = {}
    for adresse, antwort in (abgelehnt_roh or {}).items():
        code, text = antwort if isinstance(antwort, tuple) else ("", antwort)
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        abgelehnt[adresse] = f"{code} {text}".strip()

    logger.info("Email '%s' an %s verschickt (abgelehnt: %s)", subject, umschlag, list(abgelehnt))
    return VersandErgebnis(message_id=msg["Message-ID"], abgelehnt=abgelehnt)
