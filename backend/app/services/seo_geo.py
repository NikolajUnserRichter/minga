"""Nächtliche SEO/GEO-Sammler.

Drei Sammler, jeder einzeln abschaltbar und ohne Zugangsdaten inaktiv:
Search Console (Service-Account), GEO-Messung (Gemini mit
Google-Search-Grounding) und die vorhandene First-Party-Zählung als
Nutzensignal. Kein Sammler wirft nach außen — ein Ausfall darf die
anderen nicht mitreißen.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import quote, urlparse

import httpx

from app.core import seo_store
from app.core.site import root_domain
from app.services.geo_prompts import PROMPTS

logger = logging.getLogger(__name__)

_GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/"
               "models/gemini-flash-latest:generateContent")


def _budget_tag() -> int:
    return int(os.environ.get("GEO_BUDGET_DAY", "50"))


def _budget_monat() -> int:
    # Bewusst unter dem Gemini-Freikontingent von 5.000 Grounding-Requests
    # pro Monat — der Riegel greift, bevor irgendetwas kostenpflichtig wird.
    return int(os.environ.get("GEO_BUDGET_MONTH", "4500"))


def _post_json(url: str, *, json_body: Optional[dict] = None,
               data: Optional[dict] = None, headers: Optional[dict] = None,
               timeout: float = 30.0) -> dict:
    """Der einzige HTTP-Ausgang der Sammler — Tests ersetzen genau ihn."""
    antwort = httpx.post(url, json=json_body, data=data,
                         headers=headers, timeout=timeout)
    antwort.raise_for_status()
    return antwort.json()


def budget_status(heute: Optional[date] = None) -> dict:
    """Grounding-Verbrauch gegen die Budgets, fürs Dashboard."""
    tag = (heute or date.today()).isoformat()
    heute_zahl, monat_zahl = seo_store.grounding_spent(tag)
    return {"heute": heute_zahl, "monat": monat_zahl,
            "budget_tag": _budget_tag(), "budget_monat": _budget_monat()}


def _grounding_domains(antwort: dict) -> list[str]:
    """Domains der Belege aus den groundingChunks ziehen."""
    domains: list[str] = []
    for kandidat in antwort.get("candidates") or []:
        meta = kandidat.get("groundingMetadata") or {}
        for chunk in meta.get("groundingChunks") or []:
            web = chunk.get("web") or {}
            wert = (web.get("domain")
                    or urlparse(web.get("uri", "")).netloc
                    or web.get("title") or "").lower()
            if wert:
                domains.append(wert)
    return domains


def measure_geo(tag: date, post: Callable = _post_json) -> dict:
    """Alle 28 Prompts gegen Gemini mit Google-Search-Grounding messen.

    Der Riegel steht VOR jedem Request. Gezählt wird der Versuch, nicht der
    Erfolg: ein fehlgeschlagener Request kann das Kontingent trotzdem
    belastet haben — im Zweifel lieber zu viel gezählt als bezahlt.
    """
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return {"status": "inaktiv", "grund": "kein GEMINI_API_KEY"}

    eigene = root_domain()
    tag_s = tag.isoformat()
    gemessen = uebersprungen = 0
    for prompt in PROMPTS:
        heute_zahl, monat_zahl = seo_store.grounding_spent(tag_s)
        if heute_zahl >= _budget_tag() or monat_zahl >= _budget_monat():
            uebersprungen += 1
            continue
        seo_store.grounding_increment(tag_s)
        try:
            antwort = post(
                f"{_GEMINI_URL}?key={key}",
                json_body={
                    "contents": [{"parts": [{"text": prompt["text"]}]}],
                    "tools": [{"google_search": {}}],
                },
            )
        except httpx.HTTPError as fehler:
            logger.warning(f"[seo-geo] Gemini-Request fehlgeschlagen: {fehler}")
            continue
        domains = _grounding_domains(antwort)
        seo_store.record_geo_run(
            tag_s, prompt["id"], prompt["art"],
            zitiert=any(eigene in d for d in domains), domains=domains,
        )
        gemessen += 1
    if uebersprungen:
        seo_store.log_change(
            "geo", f"Kostenriegel: {uebersprungen} Prompts übersprungen")
    return {"status": "ok", "gemessen": gemessen, "uebersprungen": uebersprungen}
