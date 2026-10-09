"""Dateinamen der Belege (B7, Gernot 08.10.2026).

Ein Beleg heißt wie seine Nummer: ``RE-2026-00002.pdf``,
``AB-20261008-0001.pdf``, ``LS-20261008-0001.pdf``, ``PL-20261008-0001.pdf``.
Download (Content-Disposition) und Mailanhang nehmen dieselbe Funktion.

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


def beleg_dateiname(nummer: Optional[str], *, entwurf: bool = False) -> str:
    """``{Nummer}.pdf``; Platzhalter ``ENTWURF-…`` oder ``entwurf=True`` → ``Entwurf-….pdf``."""
    name = _VERBOTEN.sub("_", (nummer or "").strip())
    if name.startswith(ENTWURF_PRAEFIX):
        name = name[len(ENTWURF_PRAEFIX):]
        entwurf = True
    name = name or "Beleg"
    return f"Entwurf-{name}.pdf" if entwurf else f"{name}.pdf"


def rechnung_dateiname(invoice) -> str:
    """Dateiname für den Download einer Rechnung: Entwürfe heißen ``Entwurf-…``.

    Nicht für den Mailanhang: ``POST /invoices/{id}/send`` stellt einen
    Entwurf mit dem Versand aus, der Anhang heißt wie die Rechnung
    (``beleg_dateiname(invoice.invoice_number)``).
    """
    return beleg_dateiname(invoice.invoice_number, entwurf=invoice.status == InvoiceStatus.ENTWURF)


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
