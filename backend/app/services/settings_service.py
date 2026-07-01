"""Settings-Service: liest Runtime-Settings aus DB mit env-var Fallback.

Verwendung:
    from app.services.settings_service import get_setting
    host = get_setting(db, "SMTP_HOST", env_fallback=True)

DB-Werte überschreiben env-Vars. Wenn weder DB noch env: None.
"""
from __future__ import annotations

import os
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
    # Firmendaten — landen auf allen Belegen (§ 14 UStG)
    "COMPANY_NAME":         {"is_secret": False, "label": "Firmenname (Briefkopf)"},
    "COMPANY_ADDRESS_LINE1": {"is_secret": False, "label": "Adresse Zeile 1 (Straße)"},
    "COMPANY_ADDRESS_LINE2": {"is_secret": False, "label": "Adresse Zeile 2 (PLZ Ort)"},
    "COMPANY_USTID":        {"is_secret": False, "label": "USt-IdNr. (DEXXXXXXXX)"},
    "COMPANY_STEUERNR":     {"is_secret": False, "label": "Steuernummer (alternativ zur USt-IdNr.)"},
    "COMPANY_PHONE":        {"is_secret": False, "label": "Telefon"},
    "COMPANY_EMAIL":        {"is_secret": False, "label": "E-Mail"},
    "COMPANY_WEBSITE":      {"is_secret": False, "label": "Website"},
    # Bankverbindung (für Rechnung + Mahnung)
    "COMPANY_BANK_NAME":  {"is_secret": False, "label": "Bank"},
    "COMPANY_IBAN":       {"is_secret": False, "label": "IBAN"},
    "COMPANY_BIC":        {"is_secret": False, "label": "BIC"},
    # Integration: Lexware Office (lexoffice) — Kunde hinterlegt eigenen API-Key
    "LEXOFFICE_ENABLED":  {"is_secret": False, "label": "Lexware Office aktiv"},
    "LEXOFFICE_API_KEY":  {"is_secret": True,  "label": "lexoffice API-Key"},
    # Integration: Shopify — Kunde hinterlegt eigenen Shop + Access-Token
    "SHOPIFY_ENABLED":       {"is_secret": False, "label": "Shopify aktiv"},
    "SHOPIFY_SHOP_DOMAIN":   {"is_secret": False, "label": "Shopify Shop-Domain"},
    "SHOPIFY_ACCESS_TOKEN":  {"is_secret": True,  "label": "Shopify Access-Token"},
}


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
