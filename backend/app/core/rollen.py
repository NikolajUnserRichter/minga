"""Rollen und Feldschutz für Kundenfelder.

Die Rollen-Konstanten standen bis Paket 3 in ``app/main.py``. Sie liegen hier,
damit auch Router sie nutzen können: ``app.main`` importiert die Router, ein
Import in die Gegenrichtung wäre zirkulär.

Die Rechte-Matrix je Router (``_rollen`` und die ``_deps_*``-Gruppen) bleibt in
``app/main.py``. Hier steht nur, was einzelne Endpunkte zusätzlich prüfen.
"""
from decimal import Decimal
from enum import Enum
from typing import Any, Iterable

from fastapi import HTTPException, status
from pydantic import BaseModel

ADMIN = "admin"
SALES = "sales"
PLANER = "production_planner"
PRODUKTION = "production_staff"
BUCHHALTUNG = "accounting"

ALLE_ROLLEN = [ADMIN, SALES, PLANER, PRODUKTION, BUCHHALTUNG]

# Kaufmännisch: Verwaltung, Vertrieb, Buchhaltung — dieselben Rollen wie
# _deps_geld (Rechnungen) in app/main.py. Nur sie ändern Konditionen und ziehen
# den DATEV-Debitorenexport: T3 R4 ("nur Admin, Vertrieb, Buchhaltung"), T5 R2
# (DATEV "nur noch admin, sales und accounting"), Spec 08.10.2026, Abnahme
# Paket 1 ("production_planner/production_staff können pfand_abrechnung setzen").
KAUFMAENNISCHE_ROLLEN = [ADMIN, SALES, BUCHHALTUNG]

# Alle außer der Halle: pflegen zusätzlich Sonderpreise (T5 R2) und die
# Empfänger des Kunden (T5 3.3) — wie die Schreibrollen von _deps_vertrieb
# (Produkte, Basispreise). Gernot, 08.10.2026: Mitarbeiter legen Bestellungen
# und Belege an, "Rechnungen bleiben beim Admin".
ROLLEN_OHNE_HALLE = [ADMIN, SALES, BUCHHALTUNG, PLANER]

# Abrechnungsrelevante Kundenfelder (Spec 08.10.2026, Entscheidung 6; T5 R2
# "Konditionen"); ändern nur KAUFMAENNISCHE_ROLLEN. Wo sie wirken:
# - discount_percent, payment_terms: InvoiceService.create_invoice (Rabatt, Fälligkeit)
# - skonto_percent, skonto_days: Skonto-Hinweis im Rechnungs-PDF
# - price_list_id: Preisfindung (ProductService.get_product_price, Abo-Lauf)
# - credit_limit: Kreditlimit-Prüfung in create_order
# - datev_account: DATEV-Export
# - pfand_abrechnung: Pfand auf der Rechnung (Paket 1)
# - packaging_fee_*: Konditionen ohne heutige Wirkung, gehören aber dazu
# Neue Kundenfelder ordnet tests/test_gernot_261008_paket3.py
# (TestQ4KundenfelderEingeordnet) zwangsweise hier, unten oder als frei ein.
# Feld → Bezeichnung in der Fehlermeldung (wie im Kundenformular Customers.tsx).
KUNDENFELDER_KAUFMAENNISCH = {
    "payment_terms": "Zahlungsziel",
    "credit_limit": "Kreditlimit",
    "price_list_id": "Preisliste",
    "discount_percent": "Jahresrabatt %",
    "skonto_percent": "Skonto %",
    "skonto_days": "Skontofrist (Tage)",
    "packaging_fee_amount": "Verpackungsgebühr (€)",
    "packaging_fee_percent": "Verpackungsrabatt %",
    "datev_account": "DATEV-Konto",
    "pfand_abrechnung": "Pfandabrechnung",
}

# Empfänger des Kunden; ändern nur ROLLEN_OHNE_HALLE, bei der Neuanlage frei
# (der Kunde hat noch keinen Beleg). Die Haupt-E-Mail ist der Rückfall jeder
# Empfängerliste (Versand-Abschnitt Q2: belegversand.hinterlegte_empfaenger),
# die Vorbelegung des Versanddialogs und die einzige Adresse des Mahnlaufs
# (tasks/invoice_tasks.send_payment_reminders). Die drei Listen führt Q2.3 ein;
# sie stehen schon vorher hier, ein fehlendes Feld prüft niemand.
KUNDENFELDER_EMPFAENGER = {
    "email": "E-Mail (Hauptkontakt)",
    "confirmation_emails": "Empfänger Auftragsbestätigung",
    "delivery_note_emails": "Empfänger Lieferschein",
    "invoice_emails": "Empfänger Rechnung",
}

_HINWEIS_VERALTET = " Nicht selbst geändert? Dann ist das Formular veraltet – bitte neu laden."


def hat_rolle(user: dict, rollen: Iterable[str]) -> bool:
    """True, wenn das Login mindestens eine der Rollen hat."""
    return bool(set(user.get("roles", [])) & set(rollen))


def _vergleichswert(wert: Any, *, klein: bool = False) -> Any:
    """Vergleich unabhängig von der Schreibweise.

    Das Kundenformular schickt Prozente als Zahl (5), die Datenbank liefert
    Decimal('5.00'); Enums kommen als Member oder als Text; eine leere Liste
    und NULL sind gleich. klein=True: Text ohne Groß-/Kleinschreibung
    (E-Mail-Adressen).
    """
    if wert is None or isinstance(wert, bool):
        return wert
    if isinstance(wert, (list, tuple)):
        # Listen (z. B. Empfängerlisten): leer und NULL bedeuten dasselbe
        return tuple(_vergleichswert(w, klein=klein) for w in wert) or None
    if isinstance(wert, Enum):
        wert = wert.value
    if isinstance(wert, (int, float, Decimal)):
        return Decimal(str(wert))
    text = str(wert)
    return text.strip().lower() if klein else text


def geaenderte_felder(felder: dict, neu: dict, vorher: dict, *, klein: bool = False) -> list[str]:
    """Felder aus ``felder``, die in ``neu`` stehen und von ``vorher`` abweichen."""
    return [
        feld for feld in felder
        if feld in neu
        and _vergleichswert(neu[feld], klein=klein) != _vergleichswert(vorher.get(feld), klein=klein)
    ]


def standardwerte(schema: type[BaseModel]) -> dict:
    """Standardwerte eines Pydantic-Schemas — 'vorher' bei einer Neuanlage."""
    return {
        name: feld.get_default(call_default_factory=True)
        for name, feld in schema.model_fields.items()
        if not feld.is_required()
    }


def _ablehnen(text: str, felder: dict, geaendert: list[str], *, neuanlage: bool) -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"{text}: " + ", ".join(felder[feld] for feld in geaendert) + "."
            + ("" if neuanlage else _HINWEIS_VERALTET)
        ),
    )


def kundenfeldschutz(user: dict, neu: dict, vorher: dict, *, neuanlage: bool = False) -> None:
    """403, wenn ein Login ein Kundenfeld ändert, das seiner Rolle nicht zusteht.

    - Konditionen (KUNDENFELDER_KAUFMAENNISCH): nur KAUFMAENNISCHE_ROLLEN, auch
      bei der Neuanlage (Standardwert des Schemas als 'vorher').
    - Empfänger (KUNDENFELDER_EMPFAENGER): nur ROLLEN_OHNE_HALLE; bei der
      Neuanlage frei.

    Greift nur bei einer echten Änderung: Das Kundenformular (Customers.tsx)
    schickt immer alle Felder mit; ein unveränderter Wert ist keine Änderung.
    """
    if not hat_rolle(user, KAUFMAENNISCHE_ROLLEN):
        geaendert = geaenderte_felder(KUNDENFELDER_KAUFMAENNISCH, neu, vorher)
        if geaendert:
            _ablehnen(
                "Abrechnungsrelevante Kundenfelder ändern nur Verwaltung, Vertrieb und Buchhaltung",
                KUNDENFELDER_KAUFMAENNISCH, geaendert, neuanlage=neuanlage,
            )
    if neuanlage or hat_rolle(user, ROLLEN_OHNE_HALLE):
        return
    geaendert = geaenderte_felder(KUNDENFELDER_EMPFAENGER, neu, vorher, klein=True)
    if geaendert:
        _ablehnen(
            "Empfänger des Kunden ändern nur Verwaltung, Vertrieb, Buchhaltung und Planung",
            KUNDENFELDER_EMPFAENGER, geaendert, neuanlage=False,
        )
