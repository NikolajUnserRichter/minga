"""Dateinamen der Belege (B7, Gernot 08.10.2026; Kundenname: Paket 4, C).

Ein Beleg heißt wie seine Nummer, dahinter der bereinigte Kundenname:
``RE-2026-00002_Oekoring-Handels-GmbH.pdf``,
``LS-20261008-0001_Fruchthof-Nagel-GmbH.pdf`` (AB und PL ebenso). Ohne
brauchbaren Kundennamen nur die Nummer. Download (Content-Disposition),
Mailanhang und Versandprotokoll nehmen dieselbe Funktion. Der Name trägt nur
A–Z, a–z, 0–9, "-", "_" und ".": filename= und filename* sind gleich, und
Windows, macOS, ZIP-Archive und Mailprogramme nehmen ihn unverändert.

Ein Rechnungsentwurf heißt ``Entwurf-<…>.pdf``: Der Platzhalter
``ENTWURF-<12 Zeichen>`` (Q1) wird dabei zu ``Entwurf-<12 Zeichen>``, ein
Alt-Entwurf mit RE-Nummer zu ``Entwurf-RE-….pdf``. So liegt ein geprüfter
Entwurf im Download-Ordner nie unter dem Namen der ausgestellten Rechnung.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional
from urllib.parse import quote

# Das Präfix hat eine Quelle: das Modell (auch für die Nummernvergabe aus Q1).
from app.models.invoice import ENTWURF_PRAEFIX, InvoiceStatus

# Steuerzeichen, Pfadtrenner und Anführungszeichen haben in einem Dateinamen
# bzw. im Kopf nichts zu suchen.
_VERBOTEN = re.compile(r'[\x00-\x1f\x7f/\\"]')
# ASCII-Ersatz für filename=: alles außer Buchstaben, Ziffern, . _ - und Leerzeichen
_NICHT_ASCII_SICHER = re.compile(r"[^A-Za-z0-9._ -]")


#: Höchstlänge des Kundenteils nach der Bereinigung. Alle 46 Kunden von
#: MingaGreens passen ungekürzt (längster bereinigt 48 Zeichen, 09.10.2026);
#: der ganze Name bleibt unter 100 Zeichen (document_dispatches.attachment_filename).
KUNDE_MAX_ZEICHEN = 50
# Umlaute wie im Deutschen umschreiben (Müller → Mueller, nicht Muller); dazu
# die Buchstaben, die NFKD nicht zerlegt (ø, æ, œ, ł, đ) — sie fielen sonst weg
_UMLAUTE = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss", "ẞ": "SS",
    "ø": "oe", "Ø": "Oe", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe",
    "ł": "l", "Ł": "L", "đ": "d", "Đ": "D",
})
# Apostrophe fallen weg (SIMPE'L → SIMPEL), statt ein Wort zu teilen — vor
# NFKD, denn NFKD macht aus dem Akut "´" ein Leerzeichen
_APOSTROPHE = re.compile(r"['’‘`´ʼ]")
_TRENNER = re.compile(r"[^A-Za-z0-9]+")


def kundenteil(name: Optional[str]) -> str:
    """Kundenname als Teil eines Dateinamens (Gernot 08.10.2026, B7).

    Umlaute und ß werden umgeschrieben (ä → ae), ebenso ø/æ/œ (→ oe/ae/oe)
    und ł/đ (→ l/d); andere Akzente entfallen (é → e), Apostrophe ebenso
    (auch "´"); jede Folge anderer Zeichen (Leerzeichen, &, Punkt, Klammer, /)
    wird ein "-". Rechtsformzusätze bleiben:
    "Ferdinand Bierbichler GmbH & Co. KG" → "Ferdinand-Bierbichler-GmbH-Co-KG".
    Höchstens KUNDE_MAX_ZEICHEN Zeichen, gekürzt an einer Wortgrenze; bliebe
    dabei weniger als die Hälfte, wird hart geschnitten (ebenso ein einzelnes
    überlanges Wort). Leer, wenn nichts übrig bleibt.
    """
    text = _APOSTROPHE.sub("", unicodedata.normalize("NFC", name or "").translate(_UMLAUTE))
    text = "".join(z for z in unicodedata.normalize("NFKD", text) if not unicodedata.combining(z))
    teil = _TRENNER.sub("-", text).strip("-")
    if len(teil) > KUNDE_MAX_ZEICHEN:
        kopf = teil[:KUNDE_MAX_ZEICHEN + 1]  # endet ein Wort genau an der Grenze, bleibt es ganz
        schnitt = kopf.rfind("-")
        # Wortgrenze nur, wenn mindestens die Hälfte bleibt ("A-BBB…" nicht zu "A")
        teil = kopf[:schnitt] if schnitt >= KUNDE_MAX_ZEICHEN // 2 else teil[:KUNDE_MAX_ZEICHEN]
    return teil.strip("-")


def beleg_dateiname(nummer: Optional[str], *, entwurf: bool = False, kunde: Optional[str] = None) -> str:
    """``{Nummer}_{Kunde}.pdf`` (Kunde über ``kundenteil``), ohne brauchbaren
    Kundennamen ``{Nummer}.pdf``. Platzhalter ``ENTWURF-…`` oder
    ``entwurf=True`` → ``Entwurf-…``."""
    name = _VERBOTEN.sub("_", (nummer or "").strip())
    if name.startswith(ENTWURF_PRAEFIX):
        name = name[len(ENTWURF_PRAEFIX):]
        entwurf = True
    name = name or "Beleg"
    if entwurf:
        name = f"Entwurf-{name}"
    teil = kundenteil(kunde)
    return f"{name}_{teil}.pdf" if teil else f"{name}.pdf"


def bestellkunde(order) -> Optional[str]:
    """Kundenname für AB, Lieferschein und Packliste: der Name, den ihr PDF
    druckt (order.customer.name)."""
    return getattr(getattr(order, "customer", None), "name", None)


def rechnung_kunde(invoice) -> Optional[str]:
    """Kundenname für Download und Mailanhang einer Rechnung: der Empfänger
    im PDF (pdf_service.rechnungsempfaenger) — bei ausgestellten Rechnungen
    der beim Festschreiben eingefrorene Name, beim Entwurf der aktuelle."""
    from app.services.pdf_service import rechnungsempfaenger
    return rechnungsempfaenger(invoice, invoice.status == InvoiceStatus.ENTWURF).get("name")


def rechnung_dateiname(invoice) -> str:
    """Dateiname für den Download einer Rechnung: Entwürfe heißen ``Entwurf-…``.

    Nicht für den Mailanhang: ``POST /invoices/{id}/send`` stellt einen
    Entwurf mit dem Versand aus, der Anhang heißt wie die Rechnung
    (``beleg_dateiname(invoice.invoice_number, kunde=rechnung_kunde(invoice))``).
    """
    return beleg_dateiname(
        invoice.invoice_number, entwurf=invoice.status == InvoiceStatus.ENTWURF, kunde=rechnung_kunde(invoice),
    )


def content_disposition(dateiname: str, art: str = "attachment") -> str:
    """Kopf nach RFC 6266 mit ASCII-Ersatz ``filename`` und UTF-8 ``filename*`` (RFC 5987).

    Der Kopf ist reines ASCII. Starlette kodiert Köpfe als latin-1; ein
    Zeichen wie „€" im Kopf endete sonst mit 500 (UnicodeEncodeError).
    """
    name = _VERBOTEN.sub("_", dateiname)
    # Umlaute verlieren ihre Punkte (ä → a), alles andere Nicht-ASCII wird "_"
    zerlegt = unicodedata.normalize("NFKD", name)
    ersatz = "".join(z for z in zerlegt if not unicodedata.combining(z))
    ersatz = _NICHT_ASCII_SICHER.sub("_", ersatz)
    return f"{art}; filename=\"{ersatz}\"; filename*=UTF-8''{quote(name, safe='')}"
