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


_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def _gsc_zugang() -> Optional[dict]:
    """Service-Account-JSON aus der Umgebung — Inhalt oder Dateipfad."""
    raw = os.environ.get("GSC_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        return None
    try:
        if raw.startswith("{"):
            return json.loads(raw)
        return json.loads(Path(raw).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("[seo-geo] GSC_SERVICE_ACCOUNT_JSON ist nicht lesbar")
        return None


def _signierte_assertion(zugang: dict) -> str:
    """RS256-JWT für den OAuth-Token-Tausch — python-jose statt Google-SDK."""
    from jose import jwt  # bereits installiert (python-jose)
    jetzt = int(datetime.utcnow().timestamp())
    return jwt.encode(
        {"iss": zugang["client_email"], "scope": _GSC_SCOPE,
         "aud": _TOKEN_URL, "iat": jetzt, "exp": jetzt + 3600},
        zugang["private_key"], algorithm="RS256",
    )


def collect_gsc(tag: date, post: Callable = _post_json) -> dict:
    """Search-Console-Zeilen genau eines Tages holen.

    Die GSC liefert mit zwei bis drei Tagen Verzug — der Aufrufer reicht
    bereits einen fertigen Tag herein (nightly: heute minus drei).
    """
    zugang = _gsc_zugang()
    site = os.environ.get("GSC_SITE_URL", "").strip()
    if zugang is None or not site:
        return {"status": "inaktiv",
                "grund": "kein Service-Account oder keine GSC_SITE_URL"}

    token = post(_TOKEN_URL, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": _signierte_assertion(zugang),
    })["access_token"]

    antwort = post(
        "https://searchconsole.googleapis.com/webmasters/v3/sites/"
        f"{quote(site, safe='')}/searchAnalytics/query",
        json_body={"startDate": tag.isoformat(), "endDate": tag.isoformat(),
                   "dimensions": ["page", "query"], "rowLimit": 5000},
        headers={"Authorization": f"Bearer {token}"},
    )
    zeilen = [{"page": r["keys"][0], "query": r["keys"][1],
               "clicks": r.get("clicks", 0),
               "impressions": r.get("impressions", 0),
               "position": r.get("position", 0.0)}
              for r in antwort.get("rows", [])]
    seo_store.record_gsc_rows(tag.isoformat(), zeilen)
    return {"status": "ok", "zeilen": len(zeilen)}


# Verweise, hinter denen eine generative Engine steht. Zitiert werden ist
# Mittel, nicht Zweck — dieses Signal zeigt, ob aus KI-Antworten Besucher werden.
_AI_REFERRER = ("chatgpt.com", "chat.openai.com", "perplexity.ai",
                "gemini.google.com", "copilot.microsoft.com", "claude.ai",
                "you.com", "phind.com")


def collect_firstparty(tag: date, stats_fn: Optional[Callable] = None) -> dict:
    """KI-Verweise aus der eigenen cookielosen Zählung festhalten."""
    if stats_fn is None:
        from app.core.webstats import stats as stats_fn  # type: ignore[no-redef]
    daten = stats_fn(days=1)
    besuche = 0
    gefunden: list[str] = []
    for eintrag in daten.get("top_referrers", []):
        ref = (eintrag.get("ref") or "").lower()
        if any(dom in ref for dom in _AI_REFERRER):
            besuche += int(eintrag.get("views", 0))
            gefunden.append(ref)
    seo_store.record_ai_referrals(tag.isoformat(), besuche, gefunden)
    return {"status": "ok", "ki_besuche": besuche}


def sammler_status() -> dict:
    """Welche Sammler haben Zugangsdaten? Fürs Dashboard."""
    return {
        "gsc": bool(_gsc_zugang()
                    and os.environ.get("GSC_SITE_URL", "").strip()),
        "geo": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        "firstparty": True,  # braucht keine Zugangsdaten
    }


def nightly(heute: Optional[date] = None) -> dict:
    """Der nächtliche Lauf. Jeder Sammler fällt einzeln, nie der ganze Job."""
    heute = heute or date.today()
    gsc_tag = heute - timedelta(days=3)  # GSC-Daten sind erst dann vollständig
    ergebnis: dict[str, Any] = {}
    for name, aufruf in (
        ("gsc", lambda: collect_gsc(gsc_tag)),
        ("geo", lambda: measure_geo(heute)),
        ("firstparty", lambda: collect_firstparty(heute)),
    ):
        try:
            ergebnis[name] = aufruf()
        except Exception as fehler:  # noqa: BLE001 — Sammler isolieren
            logger.exception(f"[seo-geo] Sammler '{name}' fehlgeschlagen")
            ergebnis[name] = {"status": "fehler", "grund": str(fehler)}
    seo_store.log_change("nightly", json.dumps(ergebnis, ensure_ascii=False))
    return ergebnis
