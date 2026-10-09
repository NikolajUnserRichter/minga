"""SEPA-Lastschrift (B10): Prüfungen, Einzugsdatum, Vorabankündigung, Einzug.

Nur Standardbibliothek plus python-dateutil (requirements.txt). Kein
SEPA-XML in diesem Schritt.

Regeln:
- Die Gläubiger-ID steht einmal in den Firmeneinstellungen und wird OHNE
  Umgebungs-Rückfall gelesen: eine Umgebungsvariable gälte für alle
  Mandanten im Container.
- Zahlungsart, Mandat und Hinweis bestimmt erst das Festschreiben
  (ENTWURF → OFFEN), nie das Anlegen: ein Entwurf kann noch den Kunden
  wechseln. Der Hinweis wird an der Rechnung eingefroren (GoBD).
- Die volle IBAN steht nie in Mail, PDF oder Rechnungsantwort.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from dateutil.easter import easter
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.models.sepa_mandate import LastschriftStatus, SepaMandat, Zahlungsart

GLAEUBIGER_ID_KEY = "COMPANY_SEPA_GLAEUBIGER_ID"
FRIST_KEY = "SEPA_VORABANKUENDIGUNG_TAGE"
#: Vorabankündigungsfrist ohne abweichende Vereinbarung im Mandat.
STANDARD_FRIST_TAGE = 14


class LastschriftNichtMoeglich(ValueError):
    """Lastschriftkunde, aber Festschreiben als Lastschrift unmöglich (kein
    aktives Mandat, keine Gläubiger-ID). Kein stiller Rückfall auf
    Überweisung: die Rechnung bleibt Entwurf. ValueError, damit die
    vorhandenen Endpunkte (finalize: except ValueError → 400) greifen."""


# --------------------------------------------------------------------------
# Prüfungen (ISO 13616 Modulo 97)
# --------------------------------------------------------------------------

def _als_zahl(zeichen: str) -> int:
    """Buchstaben → Zahlen (A=10 … Z=35), Ziffern bleiben."""
    return int("".join(str(int(c, 36)) for c in zeichen))


def iban_normalisieren(wert: str) -> str:
    return re.sub(r"\s+", "", wert or "").upper()


#: IBAN-Länge je Land im SEPA-Raum (EPC-Länderliste, Stand 2024). Nur diese
#: Länder kennen die SEPA-Lastschrift; ein neues SEPA-Land hier ergänzen.
SEPA_IBAN_LAENGEN = {
    "AD": 24, "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24, "DE": 22,
    "DK": 18, "EE": 20, "ES": 24, "FI": 18, "FR": 27, "GB": 22, "GI": 23, "GR": 27,
    "HR": 21, "HU": 28, "IE": 22, "IS": 26, "IT": 27, "LI": 21, "LT": 20, "LU": 20,
    "LV": 21, "MC": 27, "MT": 31, "NL": 18, "NO": 15, "PL": 28, "PT": 25, "RO": 24,
    "SE": 24, "SI": 19, "SK": 24, "SM": 27, "VA": 22,
}


def iban_pruefen(wert: str) -> str:
    """Normalisierte IBAN oder ValueError mit Klartext: Format, SEPA-Land,
    Länge des Landes, Prüfziffer (Modulo 97)."""
    iban = iban_normalisieren(wert)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", iban):
        raise ValueError("IBAN hat kein gültiges Format")
    land = iban[:2]
    if land not in SEPA_IBAN_LAENGEN:
        raise ValueError(f"{land} ist kein SEPA-Land — von dort gibt es keine SEPA-Lastschrift")
    if len(iban) != SEPA_IBAN_LAENGEN[land]:
        raise ValueError(f"IBAN aus {land} hat {SEPA_IBAN_LAENGEN[land]} Zeichen, nicht {len(iban)}")
    if _als_zahl(iban[4:] + iban[:4]) % 97 != 1:
        raise ValueError("IBAN-Prüfziffer stimmt nicht")
    return iban


def iban_maskiert(wert: str) -> str:
    """Land, Prüfziffer und die letzten zwei Stellen, Rest 'x', in Vierergruppen:
    DE89370400440532013000 → 'DE89 xxxx xxxx xxxx xxxx 00' (Gernots Schreibweise)."""
    iban = iban_normalisieren(wert)
    if len(iban) < 8:
        return "x" * len(iban)
    maskiert = iban[:4] + "x" * (len(iban) - 6) + iban[-2:]
    return " ".join(maskiert[i:i + 4] for i in range(0, len(maskiert), 4))


def bic_pruefen(wert: Optional[str]) -> Optional[str]:
    if wert is None or not wert.strip():
        return None
    bic = re.sub(r"\s+", "", wert).upper()
    if not re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?", bic):
        raise ValueError("BIC hat kein gültiges Format (8 oder 11 Zeichen)")
    return bic


def glaeubiger_id_pruefen(wert: str) -> str:
    """Normalisierte Gläubiger-ID oder ValueError.

    Deutschland: DE + 2 Prüfziffern + 3 Zeichen Geschäftsbereich + 11 Ziffern
    = 18 Zeichen. Die Prüfziffer läuft über nationale Kennung + Land +
    Prüfziffer, OHNE den Geschäftsbereich (Modulo 97 wie bei der IBAN).
    """
    gid = re.sub(r"\s+", "", wert or "").upper()
    if not gid.startswith("DE"):
        raise ValueError("Gläubiger-ID muss mit DE beginnen")
    if len(gid) != 18:
        raise ValueError(f"Gläubiger-ID hat 18 Zeichen, nicht {len(gid)}")
    if not re.fullmatch(r"DE\d{2}[A-Z0-9]{3}\d{11}", gid):
        raise ValueError("Gläubiger-ID hat kein gültiges Format (DE, 2 Prüfziffern, 3 Zeichen, 11 Ziffern)")
    if _als_zahl(gid[7:] + gid[:4]) % 97 != 1:
        raise ValueError("Gläubiger-ID-Prüfziffer stimmt nicht")
    return gid


def mandatsreferenz_pruefen(wert: str) -> str:
    """1–35 Zeichen aus A-Z a-z 0-9 + ? / - : ( ) . , ' — ohne Leerzeichen,
    nicht mit '/' beginnend oder endend, kein '//'. Zusätzlich nicht mit '+'
    oder '-' beginnend: Excel läse die Zelle der Einreichungs-CSV als Formel,
    und ein entschärfendes ' würde mit der Referenz ins Online-Banking kopiert."""
    ref = (wert or "").strip()
    if not 1 <= len(ref) <= 35:
        raise ValueError("Mandatsreferenz hat 1 bis 35 Zeichen")
    if not re.fullmatch(r"[A-Za-z0-9+?/\-:().,']+", ref):
        raise ValueError("Mandatsreferenz enthält unzulässige Zeichen (erlaubt: A-Z a-z 0-9 + ? / - : ( ) . , ')")
    if ref.startswith("/") or ref.endswith("/") or "//" in ref:
        raise ValueError("Mandatsreferenz darf nicht mit / beginnen oder enden und kein // enthalten")
    if ref.startswith(("+", "-")):
        raise ValueError("Mandatsreferenz darf nicht mit + oder - beginnen")
    return ref


def einstellung_pruefen(key: str, wert: str) -> str:
    """Prüfer für PATCH /admin/settings. Andere Schlüssel unverändert."""
    if key == GLAEUBIGER_ID_KEY:
        return glaeubiger_id_pruefen(wert)
    if key == FRIST_KEY:
        if not wert.strip().isdigit() or not 1 <= int(wert) <= 30:
            raise ValueError("ganze Zahl von 1 bis 30 erwartet")
        return str(int(wert))
    return wert


# --------------------------------------------------------------------------
# Einzugsdatum
# --------------------------------------------------------------------------

def heute_berlin() -> date:
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


def _target2_feiertage(jahr: int) -> set[date]:
    ostern = easter(jahr)
    return {
        date(jahr, 1, 1),
        ostern - timedelta(days=2),   # Karfreitag
        ostern + timedelta(days=1),   # Ostermontag
        date(jahr, 5, 1),
        date(jahr, 12, 25),
        date(jahr, 12, 26),
    }


def naechster_bankarbeitstag(tag: date) -> date:
    """tag selbst, wenn Bankarbeitstag (TARGET2), sonst der nächste."""
    while tag.weekday() >= 5 or tag in _target2_feiertage(tag.year):
        tag += timedelta(days=1)
    return tag


def einzugsdatum(rechnungsdatum: date, zahlungsziel_tage: int, frist_tage: int, heute: date) -> date:
    """Nächster Bankarbeitstag ab dem späteren von Fälligkeit nach
    Zahlungsziel und heute + Vorabankündigungsfrist."""
    return naechster_bankarbeitstag(max(
        rechnungsdatum + timedelta(days=zahlungsziel_tage),
        heute + timedelta(days=frist_tage),
    ))


# --------------------------------------------------------------------------
# Datenbank
# --------------------------------------------------------------------------

def glaeubiger_id(db: Session) -> Optional[str]:
    from app.services.settings_service import get_setting
    return get_setting(db, GLAEUBIGER_ID_KEY, env_fallback=False)


def vorabankuendigung_tage(db: Session) -> int:
    from app.services.settings_service import get_setting
    wert = get_setting(db, FRIST_KEY, env_fallback=False)
    return int(wert) if wert and wert.isdigit() else STANDARD_FRIST_TAGE


def aktives_mandat(db: Session, customer_id) -> Optional[SepaMandat]:
    return db.execute(
        select(SepaMandat).where(SepaMandat.customer_id == customer_id, SepaMandat.aktiv.is_(True))
    ).scalar_one_or_none()
