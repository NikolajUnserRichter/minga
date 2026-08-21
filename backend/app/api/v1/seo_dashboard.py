"""SEO/GEO-Auswertung für das Platform-Admin-Dashboard.

Nur Lesen plus ein manueller Auslöser für den Nachtlauf. Geschützt durch
denselben ``X-Platform-Admin-Key`` wie die übrige Platform-Administration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.platform import _require_admin as require_platform_admin
from app.core import seo_store
from app.services import seo_geo

router = APIRouter(prefix="/platform/seo", tags=["SEO"])


@router.get("/overview")
def overview(_: None = Depends(require_platform_admin)):
    """Alle Kennzahlen für das Dashboard-Panel in einem Aufruf."""
    return {
        "sammler": seo_geo.sammler_status(),
        "gsc": seo_store.gsc_summary(28),
        "geo": seo_store.geo_summary(28),
        "grounding": seo_geo.budget_status(),
        "ai_referrals": seo_store.ai_referrals_summary(28),
        "vorschlaege": seo_geo.suggestions(),
        "protokoll": seo_store.changelog_entries(20),
    }


@router.post("/run")
def run_now(_: None = Depends(require_platform_admin)):
    """Nachtlauf sofort ausführen — für Erstlauf und Fehlersuche."""
    return seo_geo.nightly()
