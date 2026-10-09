"""Kontenrahmen des DATEV-Exports je Mandant: SKR03 oder SKR04.

Nachtrag 09.10.2026, Abschnitt D: MingaGreens bucht mit DATEV Mittelstand
Faktura mit Rechnungswesen und DATEV Unternehmen online im SKR04; der Export
kannte nur SKR03. Einstellung DATEV_KONTENRAHMEN (Admin-Einstellungen), ohne
Eintrag SKR03 wie bisher.

VOR PRODUKTIVNUTZUNG VOM STEUERBERATER ZU BESTÄTIGEN: die Konten beider
Rahmen, insbesondere "steuerfrei" (der Code kennt nur einen steuerfreien Fall)
und dass Karte/PayPal/Lastschrift wie bisher über die Bank laufen.

Hier steht jedes Sachkonto, das der Export bebucht, für beide Rahmen — an
keiner anderen Stelle ein Kontoliteral. Debitoren (10000 ff.) hängen nicht am
Rahmen.

Grundsatz (GoBD): Eine festgeschriebene Rechnung wird nie umgeschrieben. Die
Standard-Erlöskonten beider Rahmen gelten als "Konto folgt dem Steuersatz":
der Export bildet sie beim Export aus Steuersatz und aktuellem Rahmen ab. Ein
Sonderkonto an der Position bleibt, wie es ist. Damit ein Rahmenwechsel keine
schon exportierten Belege umkontiert, ist er nach dem ersten Export gesperrt.
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TaxRate
from app.models.invoice import STANDARD_ACCOUNTS, Invoice, Payment
from app.services.settings_service import get_setting

#: Einstellung (app_settings) — gelesen ohne Rückfall auf Umgebungsvariablen:
#: eine Container-Variable gälte für alle Mandanten (wie die Gläubiger-ID).
EINSTELLUNG = "DATEV_KONTENRAHMEN"
#: Sperrgrund für den DATEV-Export; leer = Export frei.
SPERRE = "DATEV_EXPORT_SPERRE"
#: Ohne Eintrag: Bestand (alle Mandanten exportierten bisher SKR03).
STANDARD_RAHMEN = "SKR03"

SACHKONTEN: dict[str, dict[str, str]] = {
    # SKR03 = die bisherigen STANDARD_ACCOUNTS, unverändert.
    "SKR03": dict(STANDARD_ACCOUNTS),
    "SKR04": {
        "erloes_7": "4300",           # Erlöse 7 % USt
        "erloes_19": "4400",          # Erlöse 19 % USt
        "erloes_steuerfrei": "4100",  # Steuerfreie Umsätze (Gegenstück zu SKR03 8100)
        "forderungen": "1200",        # Forderungen aus L+L — vom Export nicht bebucht
        "bank": "1800",               # Bank
        "kasse": "1600",              # Kasse
    },
}

_SCHLUESSEL_JE_SATZ = {
    TaxRate.REDUZIERT: "erloes_7",
    TaxRate.STANDARD: "erloes_19",
    TaxRate.STEUERFREI: "erloes_steuerfrei",
}

#: Die Standard-Erlöskonten ALLER Rahmen: ein solches Konto an einer Position
#: heißt "folgt dem Steuersatz" — auch eine 8300 aus der SKR03-Zeit.
STANDARD_ERLOESKONTEN = frozenset(
    konten[schluessel]
    for konten in SACHKONTEN.values()
    for schluessel in _SCHLUESSEL_JE_SATZ.values()
)

#: Kontenklasse der Erlöse im jeweils ANDEREN Rahmen. Ein Sonderkonto daraus
#: ist im eigenen Rahmen nie ein Erlöskonto: SKR03-Klasse 4 sind betriebliche
#: Aufwendungen, SKR04-Klasse 8 ist nicht belegt.
_FREMDE_ERLOESKLASSE = {"SKR03": "4", "SKR04": "8"}

#: Was der Export bebucht, in Anzeigereihenfolge (Dialog, Einstellungen).
BEBUCHTE_KONTEN = (
    ("erloes_7", "Erlöse 7 %"),
    ("erloes_19", "Erlöse 19 %"),
    ("erloes_steuerfrei", "Erlöse steuerfrei"),
    ("bank", "Bank (Zahlungen außer bar)"),
    ("kasse", "Kasse (Barzahlungen)"),
)


def rahmen_pruefen(wert: Optional[str]) -> str:
    """'skr04 ' -> 'SKR04'; alles andere als SKR03/SKR04 ist ein ValueError."""
    rahmen = (wert or "").strip().upper()
    if rahmen not in SACHKONTEN:
        raise ValueError("SKR03 oder SKR04 erwartet")
    return rahmen


def kontenrahmen(db: Session) -> str:
    """Rahmen des Mandanten; ohne Eintrag SKR03."""
    wert = get_setting(db, EINSTELLUNG, env_fallback=False)
    return rahmen_pruefen(wert) if wert else STANDARD_RAHMEN


def sachkonto(rahmen: str, schluessel: str) -> str:
    return SACHKONTEN[rahmen][schluessel]


def erloeskonto_fuer(tax_rate: TaxRate, rahmen: str) -> str:
    """Standard-Erlöskonto zum Steuersatz im Rahmen; unbekannter Satz wie 7 %."""
    return SACHKONTEN[rahmen][_SCHLUESSEL_JE_SATZ.get(tax_rate, "erloes_7")]


def erloeskonto_normalisieren(konto: Optional[str]) -> Optional[str]:
    if konto is None:
        return None
    konto = konto.strip()
    if not re.fullmatch(r"[1-9][0-9]{3,7}", konto):
        raise ValueError(f"Erlöskonto {konto}: nur 4 bis 8 Ziffern")
    return konto


def ist_standard_erloeskonto(konto: Optional[str]) -> bool:
    """Leer oder ein Standard-Erlöskonto irgendeines Rahmens: dann folgt das
    Konto dem Steuersatz. Jedes andere Konto ist ein Sonderkonto und bleibt."""
    return not konto or konto in STANDARD_ERLOESKONTEN


def sonderkonto_pruefen(konto: Optional[str], rahmen: str) -> None:
    """ValueError, wenn ein Sonderkonto zur Erlösklasse des anderen Rahmens
    gehört (z. B. 8338 aus SKR03 in einem SKR04-Mandanten) — DATEV würde es
    nicht als Erlöskonto kennen. Standardkonten folgen dem Satz und passen immer."""
    if ist_standard_erloeskonto(konto):
        return
    if len(konto) == 4 and konto.isdigit() and konto[0] == _FREMDE_ERLOESKLASSE[rahmen]:
        raise ValueError(
            f"Erlöskonto {konto} passt nicht zum Kontenrahmen {rahmen} "
            f"(Kontenklasse {konto[0]} ist dort kein Erlöskonto)"
        )


def export_sperre(db: Session) -> Optional[str]:
    """Sperrgrund für den DATEV-Export oder None (frei)."""
    wert = get_setting(db, SPERRE, env_fallback=False)
    return (wert or "").strip() or None


def schon_exportiert(db: Session) -> bool:
    """Gibt es eine an DATEV exportierte Rechnung oder Zahlung?"""
    rechnung = db.execute(
        select(Invoice.id).where(Invoice.datev_exported == True).limit(1)  # noqa: E712
    ).first()
    if rechnung is not None:
        return True
    zahlung = db.execute(
        select(Payment.id).where(Payment.datev_exported == True).limit(1)  # noqa: E712
    ).first()
    return zahlung is not None


def wechsel_pruefen(db: Session, wert: Optional[str]) -> Optional[str]:
    """Prüfer für PATCH /admin/settings, Schlüssel DATEV_KONTENRAHMEN.

    Leer/None: ohne gespeicherten Rahmen ein No-op (None, nichts zu löschen,
    es bleibt SKR03) — die SMTP-Karte schickt beim Speichern jede bekannte
    Einstellung zurück, ungesetzte als null. Einen gespeicherten Rahmen leeren
    wäre ein stiller Wechsel auf SKR03 und wird abgelehnt.
    Nach dem ersten Export ist nur der bisherige Rahmen zulässig: der Export
    leitet die Standardkonten beim Export ab, ein Wechsel würde einen
    Wiederholungsexport alter Belege umkontieren.
    """
    if not (wert or "").strip():
        if get_setting(db, EINSTELLUNG, env_fallback=False):
            raise ValueError("leeren nicht möglich — SKR03 oder SKR04 angeben")
        return None
    neu = rahmen_pruefen(wert)
    if neu != kontenrahmen(db) and schon_exportiert(db):
        raise ValueError(
            "nach dem ersten DATEV-Export nicht mehr änderbar — "
            "Wechsel des Kontenrahmens mit dem Steuerberater klären"
        )
    return neu
