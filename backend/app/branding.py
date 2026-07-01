"""Per-Tenant-Branding: Editionen (Branchen-Varianten) der ERP-Oberfläche.

Ein Tenant speichert in seinen app_settings nur ``BRAND_EDITION`` (z.B.
"sprouddesk"). Das zugehörige Preset (Name, Farben, Icon, ausgeblendete Module)
kommt aus diesem Modul — so muss nicht jede Farbe pro Tenant gespeichert werden.

Editionen:
    sprouddesk  — Farming/Manufaktur (grün, Sprossen-Icon) — Default
    tradesk     — Handel/Distribution (blau, Handels-Icon), Farming-Module aus
    novaerp     — Generisch (kupfer, Kompass-Stern), alle Module

Optionale Overrides pro Tenant (falls gesetzt, überschreiben Preset):
    BRAND_NAME, BRAND_PRIMARY
"""
from __future__ import annotations

from typing import Optional

# Module (Nav-hrefs), die eine Edition ausblendet.
_FARMING_MODULES = [
    "/seeds", "/production", "/harvests", "/capacities",
    "/forecasting", "/suggestions", "/accuracy",
]

EDITIONS: dict[str, dict] = {
    "sprouddesk": {
        "edition": "sprouddesk",
        "name": "Sprouddesk",
        "wordmark": ["Sproud", "desk"],
        "colors": {"a": "#1F7A3D", "b": "#86CB3C", "mid": "#3FA52A", "primary": "#2E9A4B"},
        "icon": "sprout",
        "hidden_modules": [],
        "tagline": "Grow smart. Run your farm.",
    },
    "tradesk": {
        "edition": "tradesk",
        "name": "Tradesk",
        "wordmark": ["Trade", "sk"],
        "colors": {"a": "#2563EB", "b": "#60A5FA", "mid": "#3B82F6", "primary": "#2563EB"},
        "icon": "trade",
        "hidden_modules": _FARMING_MODULES,
        "tagline": "Sell smart. Run your trade.",
    },
    "novaerp": {
        "edition": "novaerp",
        "name": "NovaERP",
        "wordmark": ["Nova", "ERP"],
        "colors": {"a": "#0a0a0a", "b": "#C57A3B", "mid": "#C57A3B", "primary": "#C57A3B"},
        "icon": "nova",
        "hidden_modules": [],
        "tagline": "Ein System für alles.",
    },
}

DEFAULT_EDITION = "sprouddesk"


def resolve_branding(edition_key: Optional[str], *, name_override: Optional[str] = None,
                     primary_override: Optional[str] = None) -> dict:
    """Liefert das Branding-Preset für eine Edition inkl. optionaler Overrides."""
    preset = EDITIONS.get((edition_key or "").strip().lower()) or EDITIONS[DEFAULT_EDITION]
    result = {
        "edition": preset["edition"],
        "name": name_override or preset["name"],
        "wordmark": preset["wordmark"],
        "colors": dict(preset["colors"]),
        "icon": preset["icon"],
        "hidden_modules": list(preset["hidden_modules"]),
        "tagline": preset["tagline"],
    }
    if primary_override:
        result["colors"]["primary"] = primary_override
    return result
