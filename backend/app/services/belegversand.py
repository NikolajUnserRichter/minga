"""Belegversand (Paket 3, Q2): Empfänger ermitteln, Mail schicken, protokollieren.

Gemeinsam für Auftragsbestätigung, Lieferschein und Rechnung. Die Endpunkte
(api/v1/documents.py, api/v1/invoices.py) prüfen Status und Rechte, erzeugen
das PDF und rufen dann `versende_beleg` bzw. `markiere_ohne_mail`.

Regeln:
- EINE Mail, alle Empfänger im An-Feld (Gernot, 08.10.2026), Cc optional.
- Empfänger: ausdrücklich übergebene Adressen vor der Liste im Kundenstamm;
  die Liste nur auf ausdrücklichen Wunsch (`use_customer_recipients`).
- An und Cc zusammen höchstens MAX_EMPFAENGER — geprüft, nachdem die
  Kundenliste aufgelöst ist (`empfaenger_fuer_versand`).
- Anhang heißt wie der Beleg: Nummer und Kundenname (`beleg_dateiname`, Q3;
  Kundenname Paket 4, C — Parameter `kunde`).
- Protokolliert wird nur Erfolg (auch Teilerfolg); scheitert der Versand,
  wirft send_email und es entsteht keine Zeile. Nichts hier committet.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.email_adressen import MAX_EMPFAENGER, pruefe_empfaenger
from app.models.documents import DocumentDispatch
from app.models.enums import DispatchDocType, DispatchStatus
from app.services.beleg_dateiname import beleg_dateiname
from app.services.email_service import send_email
from app.services.pdf_service import load_company_settings

#: Kundenfeld mit der Empfängerliste je Belegart
LISTE_JE_BELEGART = {
    DispatchDocType.AB: "confirmation_emails",
    DispatchDocType.LS: "delivery_note_emails",
    DispatchDocType.RE: "invoice_emails",
}


class KeinEmpfaenger(ValueError):
    """Weder Adressen übergeben noch beim Kunden hinterlegt — wird zu 400."""


def hinterlegte_empfaenger(customer, doc_type: DispatchDocType) -> list[str]:
    """Liste der Belegart aus dem Kundenstamm, ersatzweise die Haupt-E-Mail."""
    if customer is None:
        return []
    liste = getattr(customer, LISTE_JE_BELEGART[doc_type], None) or []
    if liste:
        return pruefe_empfaenger(liste, feld="Hinterlegte Empfänger")
    if customer.email:
        return pruefe_empfaenger([customer.email], feld="Haupt-E-Mail des Kunden")
    return []


def ermittle_empfaenger(
    customer,
    doc_type: DispatchDocType,
    *,
    to: Optional[list[str]],
    use_customer_recipients: bool,
) -> list[str]:
    """An-Empfänger eines Versands. [] heißt: keine Mail.

    Wirft KeinEmpfaenger, wenn die Kundenliste verlangt, aber leer ist, und
    ValueError, wenn die hinterlegte Haupt-E-Mail ungültig ist.
    """
    if to:
        return list(to)
    if use_customer_recipients:
        liste = hinterlegte_empfaenger(customer, doc_type)
        if not liste:
            raise KeinEmpfaenger(
                "Beim Kunden ist für diese Belegart keine E-Mail-Adresse hinterlegt "
                "(auch keine Haupt-E-Mail). Bitte Empfänger angeben."
            )
        return liste
    return []


def empfaenger_fuer_versand(
    customer,
    doc_type: DispatchDocType,
    *,
    to: Optional[list[str]],
    cc: Optional[list[str]],
    use_customer_recipients: bool,
) -> tuple[list[str], list[str]]:
    """An und Cc eines Versands; ([], []) heißt: keine Mail.

    Die Schema-Prüfung (BelegVersandRequest) sieht nur die übergebenen
    Adressen. Erst hier steht das An-Feld fest, auch wenn es aus dem
    Kundenstamm kommt: Cc verliert jede Adresse, die schon im An-Feld steht,
    und An + Cc dürfen zusammen höchstens MAX_EMPFAENGER sein. Wirft
    ValueError (auch KeinEmpfaenger) — die Endpunkte machen daraus 400.
    """
    an = ermittle_empfaenger(
        customer, doc_type, to=to, use_customer_recipients=use_customer_recipients,
    )
    if not an:
        return [], []
    kopie = [a for a in pruefe_empfaenger(cc, feld="Cc") if a not in an]
    if len(an) + len(kopie) > MAX_EMPFAENGER:
        raise ValueError(
            f"Höchstens {MAX_EMPFAENGER} Adressen je Mail (An und Cc zusammen; "
            f"An: {len(an)}, Cc: {len(kopie)})"
        )
    return an, kopie


def pdf_pruefsumme(pdf: bytes) -> str:
    return hashlib.sha256(pdf).hexdigest()


def erster_nachweis(dispatches: Iterable[DocumentDispatch]) -> Optional[DocumentDispatch]:
    """Erste Protokollzeile mit Prüfsumme — der Inhalt, unter dem der Beleg
    zum ersten Mal hinausging (Mail oder Markierung)."""
    for eintrag in dispatches:
        if eintrag.attachment_sha256:
            return eintrag
    return None


def firmenname(db: Session) -> str:
    """Firmenname aus den Einstellungen (COMPANY_NAME), sonst leer."""
    return (load_company_settings(db).get("COMPANY_NAME") or "").strip()


def firmenzusatz(db: Session) -> str:
    """„ — Firmenname" für den Betreff; ohne Einstellung leer."""
    name = firmenname(db)
    return f" — {name}" if name else ""


def absendername(db: Session) -> str:
    """Name unter der Grußformel: der Firmenname, sonst der Absender-Name
    der Mails (EMAILS_FROM_NAME — derselbe Wert wie im Von-Feld, auch aus der
    Umgebung), sonst leer (Abschnitt F)."""
    from app.services.settings_service import get_setting
    return firmenname(db) or (get_setting(db, "EMAILS_FROM_NAME") or "").strip()


def gruss(db: Session) -> str:
    name = absendername(db)
    return f"Mit freundlichen Grüßen\n{name}" if name else "Mit freundlichen Grüßen\nIhr Team"


def _absender(user: Optional[dict]) -> tuple[Optional[str], Optional[str]]:
    user = user or {}
    benutzer_id = user.get("id")
    return (str(benutzer_id) if benutzer_id else None, user.get("username") or user.get("email"))


def versende_beleg(
    db: Session,
    *,
    doc_type: DispatchDocType,
    document_number: str,
    an: list[str],
    cc: Optional[list[str]],
    betreff: str,
    text: str,
    pdf: bytes,
    user: Optional[dict],
    customer_id: Optional[UUID] = None,
    order_id: Optional[UUID] = None,
    confirmation_id: Optional[UUID] = None,
    delivery_note_id: Optional[UUID] = None,
    invoice_id: Optional[UUID] = None,
    kunde: Optional[str] = None,
) -> DocumentDispatch:
    """Schickt EINE Mail mit dem PDF an alle Empfänger und legt die
    Protokollzeile an (flush, kein commit). Fehler beim Versand
    (EmailNotConfiguredError, SMTP-Fehler) gehen unverändert an den Aufrufer."""
    dateiname = beleg_dateiname(document_number, kunde=kunde)
    ergebnis = send_email(
        db=db,
        to=list(an),
        cc=list(cc or []) or None,
        subject=betreff,
        body=text,
        attachment_bytes=pdf,
        attachment_filename=dateiname,
    )
    benutzer_id, benutzer_name = _absender(user)
    eintrag = DocumentDispatch(
        doc_type=doc_type,
        document_number=document_number,
        confirmation_id=confirmation_id,
        delivery_note_id=delivery_note_id,
        invoice_id=invoice_id,
        order_id=order_id,
        customer_id=customer_id,
        status=DispatchStatus.TEILWEISE if ergebnis.abgelehnt else DispatchStatus.GESENDET,
        to_addrs=list(an),
        cc_addrs=list(cc or []),
        refused=dict(ergebnis.abgelehnt) or None,
        subject=betreff[:300],
        attachment_filename=dateiname,
        attachment_sha256=pdf_pruefsumme(pdf),
        message_id=ergebnis.message_id,
        sent_at=datetime.now(timezone.utc),
        sent_by_id=benutzer_id,
        sent_by_name=benutzer_name,
    )
    db.add(eintrag)
    db.flush()
    return eintrag


def markiere_ohne_mail(
    db: Session,
    *,
    doc_type: DispatchDocType,
    document_number: str,
    pdf: bytes,
    user: Optional[dict],
    customer_id: Optional[UUID] = None,
    order_id: Optional[UUID] = None,
    confirmation_id: Optional[UUID] = None,
    delivery_note_id: Optional[UUID] = None,
    kunde: Optional[str] = None,
) -> DocumentDispatch:
    """Protokollzeile für „ohne Mail als versendet/ausgestellt markiert".
    Die Prüfsumme hält fest, mit welchem Inhalt der Beleg herausging."""
    benutzer_id, benutzer_name = _absender(user)
    eintrag = DocumentDispatch(
        doc_type=doc_type,
        document_number=document_number,
        confirmation_id=confirmation_id,
        delivery_note_id=delivery_note_id,
        order_id=order_id,
        customer_id=customer_id,
        status=DispatchStatus.NUR_MARKIERT,
        to_addrs=[],
        cc_addrs=[],
        attachment_filename=beleg_dateiname(document_number, kunde=kunde),
        attachment_sha256=pdf_pruefsumme(pdf),
        sent_at=datetime.now(timezone.utc),
        sent_by_id=benutzer_id,
        sent_by_name=benutzer_name,
    )
    db.add(eintrag)
    db.flush()
    return eintrag
