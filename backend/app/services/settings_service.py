"""Settings-Service: liest Runtime-Settings aus DB mit env-var Fallback.

Verwendung:
    from app.services.settings_service import get_setting
    host = get_setting(db, "SMTP_HOST", env_fallback=True)

DB-Werte überschreiben env-Vars. Wenn weder DB noch env: None.
"""
from __future__ import annotations

import os
import unicodedata
from typing import Optional

from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting


# Bekannte Setting-Keys + ob als Secret markiert
KNOWN_SETTINGS: dict[str, dict] = {
    # SMTP / E-Mail
    "SMTP_HOST":         {"is_secret": False, "label": "SMTP-Server"},
    "SMTP_PORT":         {"is_secret": False, "label": "Port"},
    "SMTP_USER":         {"is_secret": False, "label": "Benutzername"},
    "SMTP_PASSWORD":     {"is_secret": True,  "label": "Passwort"},
    "SMTP_USE_TLS":      {"is_secret": False, "label": "STARTTLS verwenden"},
    "SMTP_USE_SSL":      {"is_secret": False, "label": "Direct SSL verwenden"},
    "EMAILS_FROM_EMAIL": {"is_secret": False, "label": "Absender-Adresse"},
    "EMAILS_FROM_NAME":  {"is_secret": False, "label": "Absender-Name"},
    # Firmendaten (Karte "Firmendaten", Abschnitt F). Auf Belegen (§ 14 UStG)
    # nur, wo die Belegvorlage keinen eigenen Briefkopf bzw. keine eigene
    # Fußzeile hat. Labels wie in der Karte: sie stehen in den 422-Meldungen.
    "COMPANY_NAME":         {"is_secret": False, "label": "Firmenname"},
    "COMPANY_ADDRESS_LINE1": {"is_secret": False, "label": "Straße und Hausnummer"},
    "COMPANY_ADDRESS_LINE2": {"is_secret": False, "label": "PLZ und Ort"},
    "COMPANY_USTID":        {"is_secret": False, "label": "USt-IdNr."},
    "COMPANY_STEUERNR":     {"is_secret": False, "label": "Steuernummer"},
    "COMPANY_PHONE":        {"is_secret": False, "label": "Telefon"},
    "COMPANY_EMAIL":        {"is_secret": False, "label": "E-Mail"},
    "COMPANY_WEBSITE":      {"is_secret": False, "label": "Website"},
    # Bankverbindung (für Rechnung + Mahnung)
    "COMPANY_BANK_NAME":  {"is_secret": False, "label": "Bank"},
    "COMPANY_IBAN":       {"is_secret": False, "label": "IBAN"},
    "COMPANY_BIC":        {"is_secret": False, "label": "BIC"},
    # SEPA-Lastschrift (B10): Gläubiger-ID gehört der Firma, nicht dem Kunden.
    # Gelesen OHNE Umgebungs-Rückfall (gälte sonst für alle Mandanten im Container).
    "COMPANY_SEPA_GLAEUBIGER_ID": {"is_secret": False, "label": "Gläubiger-Identifikationsnummer (SEPA)"},
    "SEPA_VORABANKUENDIGUNG_TAGE": {"is_secret": False, "label": "SEPA: Vorabankündigung, Tage vor Einzug (leer = 14)"},
    # Integration: Lexware Office (lexoffice) — Kunde hinterlegt eigenen API-Key
    "LEXOFFICE_ENABLED":  {"is_secret": False, "label": "Lexware Office aktiv"},
    "LEXOFFICE_API_KEY":  {"is_secret": True,  "label": "lexoffice API-Key"},
    # Integration: Shopify — Kunde hinterlegt eigenen Shop + Access-Token
    "SHOPIFY_ENABLED":       {"is_secret": False, "label": "Shopify aktiv"},
    "SHOPIFY_SHOP_DOMAIN":   {"is_secret": False, "label": "Shopify Shop-Domain"},
    "SHOPIFY_ACCESS_TOKEN":  {"is_secret": True,  "label": "Shopify Access-Token"},
    # Produktion: Saisonzyklus — WINTER addiert Seed.winter_extra_tage aufs Erntefenster
    "SEASON_MODE":           {"is_secret": False, "label": "Saisonzyklus (SOMMER | WINTER)"},
    # Monatsrechnungen (B5): am 1. des Folgemonats 06:30 Entwürfe anlegen
    "MONATSRECHNUNG_AUTO":   {"is_secret": False, "label": "Monatsrechnungen automatisch als Entwurf (true | false)"},
    # DATEV-Export (Nachtrag 09.10., D): Kontenrahmen je Mandant, ohne Eintrag
    # SKR03. Gelesen OHNE Umgebungs-Rückfall (app.services.kontenrahmen).
    "DATEV_KONTENRAHMEN":    {"is_secret": False, "label": "DATEV-Kontenrahmen (SKR03 | SKR04)"},
    "DATEV_EXPORT_SPERRE":   {"is_secret": False, "label": "DATEV-Export gesperrt — Grund (leer = Export frei)"},
}


#: Felder der Karte "Firmendaten" in den Einstellungen (Abschnitt F). Die
#: Gläubiger-ID gehört zur Karte "SEPA-Lastschrift" und hat ihre eigene
#: Prüfung (sepa_service.einstellung_pruefen).
FIRMENDATEN_KEYS = (
    "COMPANY_NAME", "COMPANY_ADDRESS_LINE1", "COMPANY_ADDRESS_LINE2",
    "COMPANY_USTID", "COMPANY_STEUERNR", "COMPANY_PHONE", "COMPANY_EMAIL",
    "COMPANY_WEBSITE", "COMPANY_BANK_NAME", "COMPANY_IBAN", "COMPANY_BIC",
)
FIRMENDATEN_MAX_LAENGE = 200


def firmendaten_zeile_pruefen(key: str, wert: str) -> None:
    if key in (*FIRMENDATEN_KEYS, "EMAILS_FROM_NAME") and any(
        unicodedata.category(zeichen) in {"Cc", "Cf", "Zl", "Zp", "Cs", "Co", "Cn"}
        for zeichen in wert
    ):
        raise ValueError("nur eine Zeile ohne Steuerzeichen")


def firmendaten_normalisieren(key: str, wert: str) -> str:
    wert = wert.strip()
    if key in ("COMPANY_IBAN", "COMPANY_BIC"):
        return "".join(wert.split()).upper()
    return wert


def firmendaten_pruefen(key: str, wert: str) -> str:
    """Prüfer für PATCH /admin/settings (nicht leerer Wert), läuft vor
    sepa_service.einstellung_pruefen: gibt den zu speichernden Wert zurück
    oder wirft ValueError mit Klartext. Andere Schlüssel unverändert.

    Firmendaten: eine Zeile (der Firmenname steht im Betreff der Beleg-Mails;
    ein Zeilenumbruch im Betreff bricht den Versand ab), ohne Rand-Leerzeichen,
    höchstens FIRMENDATEN_MAX_LAENGE Zeichen; IBAN und BIC wie im SEPA-Mandat
    geprüft und normalisiert.
    """
    firmendaten_zeile_pruefen(key, wert)
    if key not in FIRMENDATEN_KEYS:
        return wert
    from app.services.sepa_service import bic_pruefen, iban_pruefen

    wert = wert.strip()
    if not wert:
        raise ValueError("nur Leerzeichen — zum Löschen das Feld leer lassen")
    if len(wert) > FIRMENDATEN_MAX_LAENGE:
        raise ValueError(f"höchstens {FIRMENDATEN_MAX_LAENGE} Zeichen")
    if key == "COMPANY_IBAN":
        return iban_pruefen(wert)
    if key == "COMPANY_BIC":
        return bic_pruefen(wert)
    return wert


def get_setting(db: Session, key: str, env_fallback: bool = True) -> Optional[str]:
    """Liest Setting-Wert aus DB. Wenn None und env_fallback=True: aus env."""
    row = db.get(AppSetting, key)
    if row and row.value not in (None, ""):
        return row.value
    if env_fallback:
        return os.getenv(key)
    return None


def get_settings_bulk(db: Session, keys: list[str]) -> dict[str, Optional[str]]:
    """Mehrere Settings auf einmal."""
    return {k: get_setting(db, k) for k in keys}


def set_setting(db: Session, key: str, value: Optional[str], is_secret: Optional[bool] = None) -> AppSetting:
    """Setzt oder aktualisiert ein Setting. Keine Validierung — der Endpoint
    macht das."""
    row = db.get(AppSetting, key)
    if not row:
        row = AppSetting(key=key, value=value)
        if is_secret is not None:
            row.is_secret = is_secret
        elif key in KNOWN_SETTINGS:
            row.is_secret = KNOWN_SETTINGS[key]["is_secret"]
        db.add(row)
    else:
        row.value = value
        if is_secret is not None:
            row.is_secret = is_secret
    return row
