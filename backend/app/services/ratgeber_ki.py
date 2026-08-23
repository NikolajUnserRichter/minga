"""KI-Redaktionstool: Gemini schreibt Ratgeber-Entwürfe.

Erzeugt ausschließlich Entwürfe — veröffentlicht wird von Hand, nachdem
die Redaktion Vorschau und Fakten geprüft hat. Generiert wird OHNE
Google-Search-Grounding: das Grounding-Kontingent gehört der GEO-Messung,
und ein Redaktionstext braucht keine Suche, sondern klare Regeln gegen
erfundene Fakten (siehe Prompt).
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable, Optional

from app.core import ratgeber
from app.services.seo_geo import _post_json

_GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/"
               "models/gemini-flash-latest:generateContent")

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


class KeinSchluessel(RuntimeError):
    """GEMINI_API_KEY ist nicht konfiguriert."""


class GenerierungFehlgeschlagen(RuntimeError):
    """Die Modellantwort war kein brauchbarer Beitrag."""


def _slugify(thema: str) -> str:
    """Deutsches Thema in einen gültigen Slug übersetzen."""
    slug = thema.strip().lower().translate(_UMLAUTE)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)[:80].strip("-")
    return ratgeber.pruefe_slug(slug)


_PROMPT = """Du bist Fachredakteur für den Ratgeber von NovaERP (novaerp.de), \
einem ERP-System für kleine und mittlere Unternehmen in Deutschland.

Schreibe einen Ratgeber-Beitrag zum Thema: {thema}
{cluster_zeile}
Zielgruppe: Inhaber und Verantwortliche kleiner Betriebe (5–50 Mitarbeitende), \
kein IT-Vorwissen. Ton: sachlich, konkret, auf Augenhöhe — kein Marketing-Jargon.

Harte Regeln:
- KEINE erfundenen Zahlen, Statistiken oder Studien. Wenn du eine Zahl nicht \
sicher belegen kannst, formuliere ohne Zahl oder als Erfahrungswert \
("typischerweise", "in der Praxis").
- Quellen nur, wenn sie sicher existieren: EU-Verordnungen, deutsche Gesetze, \
Behörden-Seiten (EUR-Lex, BMF, BSI). Im Zweifel: leere Quellenliste.
- NovaERP höchstens zweimal natürlich erwähnen, der Text muss auch ohne \
Produktnennung nützlich sein.
- Markdown NUR mit: ## Überschrift, ### Unterüberschrift, - Listenpunkt, \
**fett**, [Text](URL). Keine Tabellen, keine nummerierten Listen, kein H1.
- Umfang des body: 600 bis 900 Wörter, klar gegliederte Abschnitte.
- FAQ: genau 3 Fragen, formuliert wie echte Suchanfragen, mit eigenständig \
nützlichen Antworten (2–4 Sätze).

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt in exakt dieser Form:
{{"title": "...", "description": "Meta-Description, max. 160 Zeichen", \
"summary": "Kurzfassung in 1-3 Sätzen", "body": "Markdown-Text", \
"faq": [{{"frage": "...", "antwort": "..."}}], \
"sources": [{{"title": "...", "url": "https://..."}}], \
"cluster": "...", "reading_minutes": 5}}"""


def _json_aus_text(text: str) -> dict:
    """Das JSON aus der Modellantwort lösen — auch aus einem Markdown-Zaun."""
    text = text.strip()
    zaun = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if zaun:
        text = zaun.group(1)
    try:
        daten = json.loads(text)
    except json.JSONDecodeError as fehler:
        raise GenerierungFehlgeschlagen(f"Modellantwort ist kein JSON: {fehler}")
    if not isinstance(daten, dict) or not daten.get("title") or not daten.get("body"):
        raise GenerierungFehlgeschlagen("Modellantwort ohne title/body")
    return daten


def generate_article(thema: str, cluster: str = "",
                     post: Optional[Callable] = None) -> ratgeber.Article:
    """Einen Entwurf zum Thema erzeugen und speichern."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise KeinSchluessel("GEMINI_API_KEY ist nicht konfiguriert")
    post = post or _post_json

    cluster_zeile = f"Rubrik (cluster): {cluster}\n" if cluster else ""
    prompt = _PROMPT.format(thema=thema.strip(), cluster_zeile=cluster_zeile)
    antwort = post(
        f"{_GEMINI_URL}?key={key}",
        json_body={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        timeout=90.0,
    )
    try:
        text = antwort["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise GenerierungFehlgeschlagen("Modellantwort ohne Textteil")
    daten = _json_aus_text(text)

    faq = [f for f in (daten.get("faq") or [])
           if isinstance(f, dict) and f.get("frage") and f.get("antwort")]
    quellen = [q for q in (daten.get("sources") or [])
               if isinstance(q, dict) and str(q.get("url", "")).startswith("http")]

    beitrag = ratgeber.Article(
        slug=_slugify(thema),
        title=str(daten["title"]).strip(),
        cluster=str(daten.get("cluster") or cluster or "").strip(),
        description=str(daten.get("description") or "").strip()[:200],
        author="NovaERP Redaktion",
        reading_minutes=int(daten.get("reading_minutes") or 5),
        summary=str(daten.get("summary") or "").strip(),
        body=str(daten["body"]),
        faq=faq,
        sources=quellen,
        status=ratgeber.STATUS_ENTWURF,
    )
    return ratgeber.save(beitrag)
