# Ratgeber-Content-Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein Ratgeber-Bereich auf novaerp.de, dessen Beiträge in einer Datenbank liegen, serverseitig als zitierfähiges HTML gerendert werden und über einen Editor im Platform-Admin gepflegt werden.

**Architecture:** SQLite im persistenten `./data`-Volume als Speicher, eine reine Renderfunktion von Datensatz zu HTML, öffentliche Routen nur auf dem Apex und nur für veröffentlichte Beiträge, dazu eine Admin-API hinter `X-Platform-Admin-Key` mit einem Editor in der bestehenden Admin-UI. Sitemap und `llms.txt` aus Teil 1 ziehen die Beiträge über den dort vorbereiteten Rumpf `content_articles()`.

**Tech Stack:** FastAPI, sqlite3 (Standardbibliothek), reines HTML/JS im Admin-UI, pytest.

**Spec:** `docs/superpowers/specs/2026-08-21-seo-geo-novaerp-design.md`, Abschnitt „Teil 2 — Content-Engine"

## Global Constraints

- Kanonischer Ursprung ist immer `https://novaerp.de`, geliefert von `app.core.site.canonical_origin()`. Nie hart verdrahten.
- Öffentliche Ratgeber-Routen antworten nur auf dem Apex (`is_apex_host`). Jeder andere Host bekommt 404.
- **Keine neuen Einträge in `backend/requirements.txt`.** Die Markdown-Teilmenge wird von Hand gerendert, JSON kommt aus der Standardbibliothek.
- Speicherort ist das persistente `./data`-Volume, hergeleitet wie in `app/core/webstats.py` über `Path(settings.tenants_dir).parent`. Nichts wird nach `backend/static_marketing/` geschrieben — das liegt im Docker-Image und ist nach jedem Deploy weg.
- Alle Benutzertexte, Docstrings und Kommentare auf Deutsch.
- Jede Ausgabe in HTML wird escaped. Redaktionstext ist keine vertrauenswürdige Quelle.
- Tests laufen aus `backend/`: `cd backend && python -m pytest …`
- Erfundene Fakten sind verboten. Der Renderer erzeugt kein `sameAs`, kein Bewertungs-Schema und keine Zahlen, die nicht im Datensatz stehen.
- Der Statuswert ist deutsch und dreiwertig: `entwurf`, `warteschlange`, `live`.

## Dateien

| Datei | Verantwortung |
|---|---|
| `backend/app/core/ratgeber.py` | Datenschicht: Schema, Lesen, Schreiben, Statuswechsel |
| `backend/app/services/ratgeber_render.py` | Reine Funktionen Datensatz → HTML und → JSON-LD |
| `backend/app/api/ratgeber_public.py` | Öffentliche Routen `/ratgeber` und `/ratgeber/{slug}` |
| `backend/app/api/v1/ratgeber.py` | Admin-API hinter `X-Platform-Admin-Key` |
| `backend/static_admin/index.html` | Editor-Bereich |
| `backend/app/api/seo_public.py` | `content_articles()` liest ab jetzt aus der DB |
| `backend/app/main.py` | Router-Einbindung vor dem Catch-All |
| `backend/tests/test_ratgeber_store.py` | Datenschicht |
| `backend/tests/test_ratgeber_render.py` | Renderer |
| `backend/tests/test_ratgeber_public.py` | Öffentliche Routen, Sitemap, llms.txt |
| `backend/tests/test_ratgeber_admin.py` | Admin-API |

---

### Task 1: Datenschicht — Schema, Speichern, Lesen

**Files:**
- Create: `backend/app/core/ratgeber.py`
- Test: `backend/tests/test_ratgeber_store.py`

**Interfaces:**
- Consumes: `app.config.get_settings`
- Produces: `Article` (dataclass), `db_path()`, `save(article) -> Article`, `get(slug) -> Optional[Article]`, `list_all(status=None) -> list[Article]`, `delete(slug) -> bool`, `SlugFehler`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_ratgeber_store.py` anlegen:

```python
"""Tests für die Ratgeber-Datenschicht."""
import pytest

from app.core import ratgeber


@pytest.fixture(autouse=True)
def eigene_db(tmp_path, monkeypatch):
    """Jeder Test bekommt eine frische Datei — die Datenschicht ist global."""
    monkeypatch.setenv("RATGEBER_DB_PATH", str(tmp_path / "ratgeber.db"))


def _beitrag(slug="erp-einfuehrung", **felder):
    daten = dict(
        slug=slug,
        title="ERP einführen ohne Chaos",
        cluster="Einführung",
        description="Was ein ERP-Projekt in einem KMU wirklich kostet.",
        author="Nikolaj Unser-Richter",
        reading_minutes=7,
        summary="Ein ERP-Projekt scheitert selten an der Software.",
        body="## Vorbereitung\n\nErst Prozesse, dann Software.",
    )
    daten.update(felder)
    return ratgeber.Article(**daten)


def test_speichern_und_lesen_gibt_die_felder_zurueck():
    ratgeber.save(_beitrag())
    geladen = ratgeber.get("erp-einfuehrung")
    assert geladen is not None
    assert geladen.title == "ERP einführen ohne Chaos"
    assert geladen.cluster == "Einführung"
    assert geladen.reading_minutes == 7


def test_neuer_beitrag_ist_ein_entwurf():
    ratgeber.save(_beitrag())
    assert ratgeber.get("erp-einfuehrung").status == "entwurf"
    assert ratgeber.get("erp-einfuehrung").published_at is None


def test_speichern_desselben_slugs_aktualisiert_statt_zu_doppeln():
    ratgeber.save(_beitrag())
    ratgeber.save(_beitrag(title="Neuer Titel"))
    alle = ratgeber.list_all()
    assert len(alle) == 1
    assert alle[0].title == "Neuer Titel"


def test_faq_und_quellen_ueberleben_den_roundtrip():
    ratgeber.save(_beitrag(
        faq=[{"frage": "Wie lange dauert das?", "antwort": "Vier bis acht Wochen."}],
        sources=[{"title": "Statistisches Bundesamt", "url": "https://www.destatis.de"}],
    ))
    geladen = ratgeber.get("erp-einfuehrung")
    assert geladen.faq[0]["frage"] == "Wie lange dauert das?"
    assert geladen.sources[0]["url"] == "https://www.destatis.de"


def test_unbekannter_slug_gibt_none():
    assert ratgeber.get("gibt-es-nicht") is None


def test_loeschen_meldet_erfolg_und_misserfolg():
    ratgeber.save(_beitrag())
    assert ratgeber.delete("erp-einfuehrung") is True
    assert ratgeber.delete("erp-einfuehrung") is False
    assert ratgeber.get("erp-einfuehrung") is None


@pytest.mark.parametrize("boeser_slug", [
    "", "Gross", "mit leerzeichen", "../../etc/passwd", "trailing-", "a" * 90,
])
def test_ungueltige_slugs_werden_abgewiesen(boeser_slug):
    with pytest.raises(ratgeber.SlugFehler):
        ratgeber.save(_beitrag(slug=boeser_slug))


def test_liste_filtert_nach_status():
    ratgeber.save(_beitrag("a"))
    ratgeber.save(_beitrag("b", status="live"))
    assert [x.slug for x in ratgeber.list_all(status="live")] == ["b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ratgeber_store.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.ratgeber'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/core/ratgeber.py` anlegen:

```python
"""Speicher für die Ratgeber-Beiträge.

Die Beiträge liegen in SQLite im persistenten ``./data``-Volume, nicht im
Docroot: ``backend/static_marketing/`` wird ins Docker-Image gebacken und
verliert beim nächsten Deploy alles, was zur Laufzeit dorthin geschrieben
wurde. Der Ablageort folgt ``app/core/webstats.py``.

Der Preis dieser Entscheidung: die Inhalte liegen nicht im Git und brauchen
ein eigenes Backup des Volumes.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from app.config import get_settings

STATUS_ENTWURF = "entwurf"
STATUS_WARTESCHLANGE = "warteschlange"
STATUS_LIVE = "live"
ERLAUBTE_STATUS = (STATUS_ENTWURF, STATUS_WARTESCHLANGE, STATUS_LIVE)

# Der Slug wird Teil einer URL und eines Dateipfad-freien SQL-Parameters.
# Streng halten: Kleinbuchstaben, Ziffern, einzelne Bindestriche.
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SLUG_MAXLEN = 80


class SlugFehler(ValueError):
    """Ein Slug verletzt das erlaubte Muster."""


@dataclass
class Article:
    """Ein Ratgeber-Beitrag."""

    slug: str
    title: str
    cluster: str = ""
    description: str = ""
    author: str = ""
    reading_minutes: int = 0
    summary: str = ""
    body: str = ""
    faq: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    teaser_slug: str = ""
    status: str = STATUS_ENTWURF
    queue_position: int = 0
    published_at: Optional[str] = None
    updated_at: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "title": self.title,
            "cluster": self.cluster,
            "description": self.description,
            "author": self.author,
            "reading_minutes": self.reading_minutes,
            "summary": self.summary,
            "body": self.body,
            "faq": self.faq,
            "sources": self.sources,
            "teaser_slug": self.teaser_slug,
            "status": self.status,
            "queue_position": self.queue_position,
            "published_at": self.published_at,
            "updated_at": self.updated_at,
        }


def pruefe_slug(slug: str) -> str:
    slug = (slug or "").strip().lower()
    if not slug or len(slug) > _SLUG_MAXLEN or not _SLUG_RE.match(slug):
        raise SlugFehler(f"Ungültiger Slug: '{slug}'")
    return slug


def db_path() -> Path:
    """Ablageort der Beitragsdatenbank.

    ``RATGEBER_DB_PATH`` übersteuert den Standard — Tests brauchen eine
    eigene Datei, sonst schreiben sie in das echte Volume.
    """
    override = os.environ.get("RATGEBER_DB_PATH", "").strip()
    if override:
        pfad = Path(override)
        pfad.parent.mkdir(parents=True, exist_ok=True)
        return pfad
    base = Path(get_settings().tenants_dir).parent  # persistentes ./data
    base.mkdir(parents=True, exist_ok=True)
    return base / "ratgeber.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(db_path()), timeout=5)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(
        "CREATE TABLE IF NOT EXISTS articles ("
        "slug TEXT PRIMARY KEY,"
        "title TEXT NOT NULL,"
        "cluster TEXT NOT NULL DEFAULT '',"
        "description TEXT NOT NULL DEFAULT '',"
        "author TEXT NOT NULL DEFAULT '',"
        "reading_minutes INTEGER NOT NULL DEFAULT 0,"
        "summary TEXT NOT NULL DEFAULT '',"
        "body TEXT NOT NULL DEFAULT '',"
        "faq TEXT NOT NULL DEFAULT '[]',"
        "sources TEXT NOT NULL DEFAULT '[]',"
        "teaser_slug TEXT NOT NULL DEFAULT '',"
        "status TEXT NOT NULL DEFAULT 'entwurf',"
        "queue_position INTEGER NOT NULL DEFAULT 0,"
        "published_at TEXT,"
        "updated_at TEXT NOT NULL DEFAULT ''"
        ")"
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status)")
    return c


def _liste(rohtext: str) -> list[dict]:
    """JSON-Spalte lesen und dabei Müll nicht nach oben durchreichen."""
    try:
        wert = json.loads(rohtext or "[]")
    except json.JSONDecodeError:
        return []
    return [x for x in wert if isinstance(x, dict)] if isinstance(wert, list) else []


def _aus_zeile(row: sqlite3.Row) -> Article:
    return Article(
        slug=row["slug"],
        title=row["title"],
        cluster=row["cluster"],
        description=row["description"],
        author=row["author"],
        reading_minutes=row["reading_minutes"],
        summary=row["summary"],
        body=row["body"],
        faq=_liste(row["faq"]),
        sources=_liste(row["sources"]),
        teaser_slug=row["teaser_slug"],
        status=row["status"],
        queue_position=row["queue_position"],
        published_at=row["published_at"],
        updated_at=row["updated_at"],
    )


def save(article: Article) -> Article:
    """Beitrag anlegen oder aktualisieren.

    ``published_at`` wird hier nie gesetzt — das macht ausschließlich
    ``publish()``, damit das Datum bei einer Korrektur nicht wandert.
    """
    slug = pruefe_slug(article.slug)
    if article.status not in ERLAUBTE_STATUS:
        raise ValueError(f"Unbekannter Status: '{article.status}'")
    if article.teaser_slug:
        pruefe_slug(article.teaser_slug)

    jetzt = datetime.utcnow().isoformat(timespec="seconds")
    c = _conn()
    try:
        c.execute(
            "INSERT INTO articles ("
            "slug, title, cluster, description, author, reading_minutes,"
            "summary, body, faq, sources, teaser_slug, status,"
            "queue_position, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(slug) DO UPDATE SET"
            " title=excluded.title, cluster=excluded.cluster,"
            " description=excluded.description, author=excluded.author,"
            " reading_minutes=excluded.reading_minutes,"
            " summary=excluded.summary, body=excluded.body,"
            " faq=excluded.faq, sources=excluded.sources,"
            " teaser_slug=excluded.teaser_slug, status=excluded.status,"
            " queue_position=excluded.queue_position,"
            " updated_at=excluded.updated_at",
            (
                slug, article.title, article.cluster, article.description,
                article.author, int(article.reading_minutes or 0),
                article.summary, article.body,
                json.dumps(article.faq or [], ensure_ascii=False),
                json.dumps(article.sources or [], ensure_ascii=False),
                article.teaser_slug, article.status,
                int(article.queue_position or 0), jetzt,
            ),
        )
        c.commit()
    finally:
        c.close()
    geladen = get(slug)
    assert geladen is not None  # gerade geschrieben
    return geladen


def get(slug: str) -> Optional[Article]:
    try:
        slug = pruefe_slug(slug)
    except SlugFehler:
        return None
    c = _conn()
    try:
        row = c.execute("SELECT * FROM articles WHERE slug = ?", (slug,)).fetchone()
    finally:
        c.close()
    return _aus_zeile(row) if row else None


def list_all(status: Optional[str] = None) -> list[Article]:
    """Alle Beiträge, optional nach Status gefiltert."""
    c = _conn()
    try:
        if status:
            rows = c.execute(
                "SELECT * FROM articles WHERE status = ?"
                " ORDER BY queue_position, updated_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM articles ORDER BY queue_position, updated_at DESC"
            ).fetchall()
    finally:
        c.close()
    return [_aus_zeile(r) for r in rows]


def delete(slug: str) -> bool:
    try:
        slug = pruefe_slug(slug)
    except SlugFehler:
        return False
    c = _conn()
    try:
        cur = c.execute("DELETE FROM articles WHERE slug = ?", (slug,))
        c.commit()
        return cur.rowcount > 0
    finally:
        c.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_ratgeber_store.py -q`
Expected: PASS (12 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/ratgeber.py backend/tests/test_ratgeber_store.py
git commit -m "feat(ratgeber): SQLite-Datenschicht für Ratgeber-Beiträge"
```

---

### Task 2: Veröffentlichen, Zurückziehen, Warteschlange

Das Veröffentlichungsdatum wird beim ersten Live-Gang einmal gestempelt und danach nie wieder verschoben. Springt es bei jeder Korrektur, entwertet das die Signalwirkung des Datums.

**Files:**
- Modify: `backend/app/core/ratgeber.py`
- Test: `backend/tests/test_ratgeber_store.py`

**Interfaces:**
- Consumes: `Article`, `get`, `save` aus Task 1
- Produces: `publish(slug, heute=None) -> Article`, `unpublish(slug) -> Article`, `set_queue(slugs) -> None`, `published() -> list[Article]`

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_ratgeber_store.py` anhängen:

```python
from datetime import date


def test_veroeffentlichen_setzt_status_und_datum():
    ratgeber.save(_beitrag())
    veroeffentlicht = ratgeber.publish("erp-einfuehrung", heute=date(2026, 8, 21))
    assert veroeffentlicht.status == "live"
    assert veroeffentlicht.published_at == "2026-08-21"


def test_datum_wandert_bei_spaeterer_bearbeitung_nicht():
    ratgeber.save(_beitrag())
    ratgeber.publish("erp-einfuehrung", heute=date(2026, 8, 21))
    ratgeber.save(_beitrag(title="Korrigierter Titel", status="live"))
    ratgeber.publish("erp-einfuehrung", heute=date(2026, 12, 24))
    assert ratgeber.get("erp-einfuehrung").published_at == "2026-08-21"


def test_zurueckziehen_nimmt_den_beitrag_aus_der_liste_behaelt_aber_das_datum():
    ratgeber.save(_beitrag())
    ratgeber.publish("erp-einfuehrung", heute=date(2026, 8, 21))
    zurueck = ratgeber.unpublish("erp-einfuehrung")
    assert zurueck.status == "entwurf"
    assert zurueck.published_at == "2026-08-21"
    assert ratgeber.published() == []


def test_veroeffentlichte_liste_zeigt_neueste_zuerst():
    ratgeber.save(_beitrag("alt"))
    ratgeber.save(_beitrag("neu"))
    ratgeber.publish("alt", heute=date(2026, 1, 5))
    ratgeber.publish("neu", heute=date(2026, 8, 1))
    assert [a.slug for a in ratgeber.published()] == ["neu", "alt"]


def test_unbekannter_slug_laesst_sich_nicht_veroeffentlichen():
    with pytest.raises(KeyError):
        ratgeber.publish("gibt-es-nicht")


def test_warteschlange_wird_in_der_uebergebenen_reihenfolge_nummeriert():
    for slug in ("a", "b", "c"):
        ratgeber.save(_beitrag(slug, status="warteschlange"))
    ratgeber.set_queue(["c", "a", "b"])
    warteschlange = ratgeber.list_all(status="warteschlange")
    assert [x.slug for x in warteschlange] == ["c", "a", "b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ratgeber_store.py -q -k "veroeffentlich or zurueckziehen or warteschlange or datum"`
Expected: FAIL — `AttributeError: module 'app.core.ratgeber' has no attribute 'publish'`

- [ ] **Step 3: Write minimal implementation**

An `backend/app/core/ratgeber.py` anhängen:

```python
def _status_setzen(slug: str, status: str, published_at: Optional[str]) -> Article:
    c = _conn()
    try:
        cur = c.execute(
            "UPDATE articles SET status = ?, published_at = ?, updated_at = ?"
            " WHERE slug = ?",
            (status, published_at, datetime.utcnow().isoformat(timespec="seconds"), slug),
        )
        c.commit()
        if cur.rowcount == 0:
            raise KeyError(slug)
    finally:
        c.close()
    geladen = get(slug)
    assert geladen is not None
    return geladen


def publish(slug: str, heute: Optional[date] = None) -> Article:
    """Beitrag live stellen.

    Das Datum wird nur beim ersten Mal gesetzt. Eine spätere Korrektur am
    Text darf das Veröffentlichungsdatum nicht nach vorn schieben — sonst
    sieht jede Kleinigkeit aus wie ein neuer Beitrag.
    """
    slug = pruefe_slug(slug)
    vorhanden = get(slug)
    if vorhanden is None:
        raise KeyError(slug)
    datum = vorhanden.published_at or (heute or date.today()).isoformat()
    return _status_setzen(slug, STATUS_LIVE, datum)


def unpublish(slug: str) -> Article:
    """Beitrag aus der Öffentlichkeit nehmen, Datum behalten.

    Wer denselben Beitrag später erneut live stellt, soll nicht plötzlich
    als Erstveröffentlichung dastehen.
    """
    slug = pruefe_slug(slug)
    vorhanden = get(slug)
    if vorhanden is None:
        raise KeyError(slug)
    return _status_setzen(slug, STATUS_ENTWURF, vorhanden.published_at)


def set_queue(slugs: list[str]) -> None:
    """Reihenfolge der Warteschlange festschreiben."""
    geprueft = [pruefe_slug(s) for s in slugs]
    jetzt = datetime.utcnow().isoformat(timespec="seconds")
    c = _conn()
    try:
        for position, slug in enumerate(geprueft):
            c.execute(
                "UPDATE articles SET queue_position = ?, updated_at = ? WHERE slug = ?",
                (position, jetzt, slug),
            )
        c.commit()
    finally:
        c.close()


def published() -> list[Article]:
    """Live-Beiträge, neueste Veröffentlichung zuerst."""
    c = _conn()
    try:
        rows = c.execute(
            "SELECT * FROM articles WHERE status = ?"
            " ORDER BY published_at DESC, updated_at DESC",
            (STATUS_LIVE,),
        ).fetchall()
    finally:
        c.close()
    return [_aus_zeile(r) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_ratgeber_store.py -q`
Expected: PASS (18 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/ratgeber.py backend/tests/test_ratgeber_store.py
git commit -m "feat(ratgeber): Veröffentlichen, Zurückziehen und Warteschlange"
```

---

### Task 3: Markdown-Teilmenge rendern

Kein Markdown-Paket — die Abhängigkeitsliste bleibt unverändert. Gerendert wird genau die Teilmenge, die ein Ratgeber-Text braucht: Überschriften, Absätze, Listen, fett, Links.

**Files:**
- Create: `backend/app/services/ratgeber_render.py`
- Test: `backend/tests/test_ratgeber_render.py`

**Interfaces:**
- Consumes: nichts
- Produces: `render_markdown(text: str) -> str`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_ratgeber_render.py` anlegen:

```python
"""Tests für den Ratgeber-Renderer."""
from app.services.ratgeber_render import render_markdown


def test_ueberschriften_werden_zu_h2_und_h3():
    html = render_markdown("## Vorbereitung\n\n### Details")
    assert "<h2>Vorbereitung</h2>" in html
    assert "<h3>Details</h3>" in html


def test_absaetze_werden_umschlossen():
    html = render_markdown("Erster Absatz.\n\nZweiter Absatz.")
    assert "<p>Erster Absatz.</p>" in html
    assert "<p>Zweiter Absatz.</p>" in html


def test_liste_wird_zu_ul():
    html = render_markdown("- Prozesse\n- Daten\n- Schulung")
    assert html.count("<li>") == 3
    assert "<ul>" in html and "</ul>" in html
    assert "<li>Prozesse</li>" in html


def test_fett_und_links():
    html = render_markdown("Siehe **hier** die [Doku](https://novaerp.de/agb).")
    assert "<strong>hier</strong>" in html
    assert '<a href="https://novaerp.de/agb">Doku</a>' in html


def test_html_im_redaktionstext_wird_escaped():
    html = render_markdown("Ein <script>alert(1)</script> Versuch.")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_javascript_url_wird_nicht_verlinkt():
    html = render_markdown("[klick](javascript:alert(1))")
    assert "javascript:" not in html
    assert "klick" in html


def test_leerer_text_gibt_leeren_string():
    assert render_markdown("") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ratgeber_render.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.ratgeber_render'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/services/ratgeber_render.py` anlegen:

```python
"""Ratgeber-Beitrag zu HTML.

Reine Funktionen ohne Datenbank- oder Request-Zugriff: derselbe Datensatz
ergibt immer dieselbe Seite. Das macht den Renderer testbar und erlaubt der
Admin-Vorschau, denselben Code zu benutzen wie die öffentliche Seite.

Markdown wird bewusst nur als Teilmenge unterstützt statt über ein weiteres
Paket. Redaktionstext ist keine vertrauenswürdige Quelle — alles wird zuerst
escaped, erst danach werden die erlaubten Auszeichnungen eingesetzt.
"""
from __future__ import annotations

import html
import re

_FETT_RE = re.compile(r"\*\*(.+?)\*\*")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def _inline(text: str) -> str:
    """Fett und Links innerhalb einer bereits escapten Zeile."""
    text = _FETT_RE.sub(r"<strong>\1</strong>", text)

    def link(treffer: re.Match) -> str:
        beschriftung, ziel = treffer.group(1), treffer.group(2)
        # &colon; entsteht nicht beim Escapen, aber http/https/relativ sind
        # die einzigen Ziele, die eine Redaktion braucht.
        if not (ziel.startswith("https://") or ziel.startswith("http://")
                or ziel.startswith("/")):
            return beschriftung
        return f'<a href="{ziel}">{beschriftung}</a>'

    return _LINK_RE.sub(link, text)


def render_markdown(text: str) -> str:
    """Überschriften, Absätze, Listen, fett und Links — mehr nicht."""
    if not (text or "").strip():
        return ""

    teile: list[str] = []
    liste: list[str] = []

    def liste_schliessen() -> None:
        if liste:
            teile.append("<ul>\n" + "\n".join(liste) + "\n</ul>")
            liste.clear()

    for block in re.split(r"\n\s*\n", text.strip()):
        zeilen = [z.strip() for z in block.splitlines() if z.strip()]
        for zeile in zeilen:
            sicher = _inline(html.escape(zeile))
            if zeile.startswith("### "):
                liste_schliessen()
                teile.append(f"<h3>{sicher[len('### '):]}</h3>")
            elif zeile.startswith("## "):
                liste_schliessen()
                teile.append(f"<h2>{sicher[len('## '):]}</h2>")
            elif zeile.startswith("- "):
                liste.append(f"<li>{sicher[len('- '):]}</li>")
            else:
                liste_schliessen()
                teile.append(f"<p>{sicher}</p>")
        liste_schliessen()

    return "\n".join(teile)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_ratgeber_render.py -q`
Expected: PASS (7 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ratgeber_render.py backend/tests/test_ratgeber_render.py
git commit -m "feat(ratgeber): Markdown-Teilmenge ohne Zusatzabhängigkeit"
```

---

### Task 4: Beitragsseite mit Article-, FAQPage- und BreadcrumbList-Schema

**Files:**
- Modify: `backend/app/services/ratgeber_render.py`
- Test: `backend/tests/test_ratgeber_render.py`

**Interfaces:**
- Consumes: `render_markdown`, `app.core.ratgeber.Article`, `app.core.site.canonical_origin`
- Produces: `article_graph(article) -> list[dict]`, `render_article_page(article, nachfolger=None) -> str`

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_ratgeber_render.py` anhängen:

```python
import json
import re

import pytest

from app.core.ratgeber import Article
from app.services.ratgeber_render import article_graph, render_article_page

LD_BLOCK = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)


@pytest.fixture
def beitrag():
    return Article(
        slug="erp-einfuehrung",
        title="ERP einführen ohne Chaos",
        cluster="Einführung",
        description="Was ein ERP-Projekt in einem KMU wirklich kostet.",
        author="Nikolaj Unser-Richter",
        reading_minutes=7,
        summary="Ein ERP-Projekt scheitert selten an der Software.",
        body="## Vorbereitung\n\nErst Prozesse, dann Software.",
        faq=[{"frage": "Wie lange dauert das?", "antwort": "Vier bis acht Wochen."}],
        sources=[{"title": "Destatis", "url": "https://www.destatis.de"}],
        status="live",
        published_at="2026-08-21",
    )


def test_graph_enthaelt_article_faq_und_breadcrumb(beitrag):
    typen = {k["@type"] for k in article_graph(beitrag)}
    assert {"Article", "FAQPage", "BreadcrumbList"} <= typen


def test_article_knoten_traegt_datum_autor_und_publisher(beitrag):
    knoten = [k for k in article_graph(beitrag) if k["@type"] == "Article"][0]
    assert knoten["headline"] == "ERP einführen ohne Chaos"
    assert knoten["datePublished"] == "2026-08-21"
    assert knoten["author"]["name"] == "Nikolaj Unser-Richter"
    assert knoten["publisher"] == {"@id": "https://novaerp.de/#org"}
    assert knoten["mainEntityOfPage"] == "https://novaerp.de/ratgeber/erp-einfuehrung"


def test_ohne_faq_kein_faq_knoten(beitrag):
    beitrag.faq = []
    typen = {k["@type"] for k in article_graph(beitrag)}
    assert "FAQPage" not in typen


def test_seite_bringt_canonical_kurzfassung_und_quellen(beitrag):
    html = render_article_page(beitrag)
    assert '<link rel="canonical" href="https://novaerp.de/ratgeber/erp-einfuehrung"' in html
    assert "Ein ERP-Projekt scheitert selten an der Software." in html
    assert 'href="https://www.destatis.de"' in html
    assert "<h1>ERP einführen ohne Chaos</h1>" in html
    assert "7 Min" in html


def test_seiten_schema_ist_valides_json(beitrag):
    html = render_article_page(beitrag)
    bloecke = [json.loads(b) for b in LD_BLOCK.findall(html)]
    assert bloecke and "@graph" in bloecke[0]


def test_titel_mit_sonderzeichen_bricht_das_markup_nicht():
    boese = Article(slug="x", title='Titel mit " und <b>', status="live")
    html = render_article_page(boese)
    assert "<b>" not in html.split("<body")[0]
    assert json.loads(LD_BLOCK.findall(html)[0])  # JSON bleibt lesbar


def test_teaser_verlinkt_den_folgebeitrag(beitrag):
    nachfolger = Article(slug="lager-optimieren", title="Lager optimieren",
                         summary="Weniger Kapital im Regal.", status="live")
    html = render_article_page(beitrag, nachfolger=nachfolger)
    assert 'href="/ratgeber/lager-optimieren"' in html
    assert "Lager optimieren" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ratgeber_render.py -q -k "graph or seite or teaser or titel"`
Expected: FAIL — `ImportError: cannot import name 'article_graph'`

- [ ] **Step 3: Write minimal implementation**

An `backend/app/services/ratgeber_render.py` anhängen (Importe oben ergänzen):

```python
import json
from typing import Optional

from app.core.ratgeber import Article
from app.core.site import canonical_origin

# Gleiche Farbwelt wie die Rechtsseiten im Docroot. Bewusst als eine
# eingebettete Regel statt als eigene CSS-Datei: eine Anfrage weniger und
# kein zweiter Ort, an dem das Layout auseinanderlaufen kann.
_STYLE = """
:root{--abyss:#0a0a0a;--panel:#121212;--ink-0:#F6F1EA;--ink-1:#CDC5BB;
--ink-2:#9A9288;--ink-3:#6C655C;--bronze:#C0814F;--bronze-glow:#D8A06E;
--line:rgba(246,241,234,.08)}
*{box-sizing:border-box}
body{margin:0;background:var(--abyss);color:var(--ink-1);
font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.7}
.wrap{max-width:760px;margin:0 auto;padding:3rem 1.5rem 5rem}
a{color:var(--bronze-glow);text-decoration:none}a:hover{text-decoration:underline}
.logo{display:inline-flex;margin-bottom:2.5rem}.logo img{height:28px;width:auto}
h1{color:var(--ink-0);font-size:2.1rem;font-weight:800;letter-spacing:-.03em;margin:0 0 .75rem}
h2{color:var(--ink-0);font-size:1.35rem;font-weight:700;margin:2.4rem 0 .6rem}
h3{color:var(--ink-0);font-size:1.1rem;font-weight:700;margin:1.8rem 0 .4rem}
p{margin:.7rem 0}li{margin:.35rem 0}
.meta{color:var(--ink-3);font-size:.87rem;margin-bottom:2rem}
.kurz{background:rgba(192,129,79,.12);border:1px solid rgba(192,129,79,.32);
border-radius:.7rem;padding:1.1rem 1.3rem;margin:0 0 2.5rem;color:var(--ink-0)}
.kurz b{display:block;font-size:.74rem;letter-spacing:.09em;text-transform:uppercase;
color:var(--bronze-glow);margin-bottom:.4rem}
.faq{margin-top:3rem;border-top:1px solid var(--line);padding-top:1.5rem}
.faq dt{color:var(--ink-0);font-weight:700;margin-top:1.2rem}
.faq dd{margin:.3rem 0 0}
.quellen{margin-top:3rem;border-top:1px solid var(--line);padding-top:1.5rem;font-size:.9rem}
.quellen li{color:var(--ink-2)}
.teaser{margin-top:3rem;background:var(--panel);border:1px solid var(--line);
border-radius:.8rem;padding:1.25rem 1.4rem}
.teaser .lbl{font-size:.74rem;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3)}
.teaser a{display:block;color:var(--ink-0);font-weight:700;font-size:1.05rem;margin-top:.3rem}
.karte{display:block;background:var(--panel);border:1px solid var(--line);
border-radius:.8rem;padding:1.2rem 1.35rem;margin-bottom:.9rem}
.karte:hover{border-color:rgba(192,129,79,.4);text-decoration:none}
.karte .t{color:var(--ink-0);font-weight:700;font-size:1.05rem}
.karte .s{color:var(--ink-2);font-size:.9rem;margin-top:.3rem}
.back{display:inline-block;margin-top:3rem;color:var(--ink-2)}
"""

_KOPF_LOGO = '<a href="/" class="logo"><img src="/logo-dark.png" alt="NovaERP"/></a>'


def _e(text: str) -> str:
    return html.escape(str(text or ""), quote=True)


def article_url(slug: str) -> str:
    return f"{canonical_origin()}/ratgeber/{slug}"


def article_graph(article: Article) -> list[dict]:
    """Schema-Knoten eines Beitrags.

    Nur belegte Angaben: kein Bild, wenn keins hinterlegt ist, kein
    FAQ-Knoten ohne Fragen. Erfundene Auszeichnung schadet mehr als sie hilft.
    """
    url = article_url(article.slug)
    knoten: list[dict] = [{
        "@type": "Article",
        "@id": f"{url}#article",
        "headline": article.title,
        "description": article.description or article.summary,
        "inLanguage": "de-DE",
        "mainEntityOfPage": url,
        "url": url,
        "isPartOf": {"@id": f"{canonical_origin()}/#website"},
        "publisher": {"@id": f"{canonical_origin()}/#org"},
    }]
    if article.author:
        knoten[0]["author"] = {"@type": "Person", "name": article.author}
    if article.published_at:
        knoten[0]["datePublished"] = article.published_at

    fragen = [f for f in article.faq if f.get("frage") and f.get("antwort")]
    if fragen:
        knoten.append({
            "@type": "FAQPage",
            "@id": f"{url}#faq",
            "mainEntity": [{
                "@type": "Question",
                "name": f["frage"],
                "acceptedAnswer": {"@type": "Answer", "text": f["antwort"]},
            } for f in fragen],
        })

    knoten.append({
        "@type": "BreadcrumbList",
        "@id": f"{url}#breadcrumb",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Start",
             "item": f"{canonical_origin()}/"},
            {"@type": "ListItem", "position": 2, "name": "Ratgeber",
             "item": f"{canonical_origin()}/ratgeber"},
            {"@type": "ListItem", "position": 3, "name": article.title, "item": url},
        ],
    })
    return knoten


def _seitenrahmen(titel: str, beschreibung: str, url: str,
                  graph: list[dict], inhalt: str) -> str:
    # `<` wird zu <: ein Redaktionstitel mit "</script>" würde sonst aus
    # dem Script-Block ausbrechen. Bleibt gültiges JSON.
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph},
                    ensure_ascii=False, indent=2).replace("<", "\\u003c")
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{_e(titel)}</title>
<meta name="description" content="{_e(beschreibung)}"/>
<link rel="canonical" href="{_e(url)}" />
<meta property="og:type" content="article" />
<meta property="og:url" content="{_e(url)}" />
<meta property="og:title" content="{_e(titel)}" />
<meta property="og:description" content="{_e(beschreibung)}" />
<meta property="og:locale" content="de_DE" />
<meta property="og:site_name" content="NovaERP" />
<meta property="og:image" content="{canonical_origin()}/og.png" />
<script type="application/ld+json">
{ld}
</script>
<style>{_STYLE}</style></head><body><div class="wrap">
{_KOPF_LOGO}
{inhalt}
</div></body></html>
"""


def render_article_page(article: Article,
                        nachfolger: Optional[Article] = None) -> str:
    """Vollständige Beitragsseite als HTML."""
    url = article_url(article.slug)
    zeilen = [f"<h1>{_e(article.title)}</h1>"]

    meta = []
    if article.cluster:
        meta.append(_e(article.cluster))
    if article.author:
        meta.append(_e(article.author))
    if article.published_at:
        meta.append(_e(article.published_at))
    if article.reading_minutes:
        meta.append(f"{int(article.reading_minutes)} Min. Lesezeit")
    if meta:
        zeilen.append('<div class="meta">' + " · ".join(meta) + "</div>")

    if article.summary:
        zeilen.append('<div class="kurz"><b>Kurz gefasst</b>'
                      f"{_e(article.summary)}</div>")

    zeilen.append(render_markdown(article.body))

    fragen = [f for f in article.faq if f.get("frage") and f.get("antwort")]
    if fragen:
        zeilen.append('<div class="faq"><h2>Häufige Fragen</h2><dl>')
        for f in fragen:
            zeilen.append(f"<dt>{_e(f['frage'])}</dt><dd>{_e(f['antwort'])}</dd>")
        zeilen.append("</dl></div>")

    quellen = [q for q in article.sources if q.get("url")]
    if quellen:
        zeilen.append('<div class="quellen"><h2>Quellen</h2><ul>')
        for q in quellen:
            ziel = q["url"]
            if not (ziel.startswith("https://") or ziel.startswith("http://")):
                continue
            zeilen.append(
                f'<li><a href="{_e(ziel)}" rel="noopener" target="_blank">'
                f"{_e(q.get('title') or ziel)}</a></li>"
            )
        zeilen.append("</ul></div>")

    if nachfolger is not None:
        zeilen.append(
            '<div class="teaser"><span class="lbl">Weiterlesen</span>'
            f'<a href="/ratgeber/{_e(nachfolger.slug)}">{_e(nachfolger.title)}</a>'
            + (f"<div>{_e(nachfolger.summary)}</div>" if nachfolger.summary else "")
            + "</div>"
        )

    zeilen.append('<a href="/ratgeber" class="back">← Alle Ratgeber-Beiträge</a>')

    return _seitenrahmen(
        titel=f"{article.title} — NovaERP",
        beschreibung=article.description or article.summary,
        url=url,
        graph=article_graph(article),
        inhalt="\n".join(zeilen),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_ratgeber_render.py -q`
Expected: PASS (14 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ratgeber_render.py backend/tests/test_ratgeber_render.py
git commit -m "feat(ratgeber): Beitragsseite mit Article-, FAQ- und Breadcrumb-Schema"
```

---

### Task 5: Übersichtsseite nach Clustern

**Files:**
- Modify: `backend/app/services/ratgeber_render.py`
- Test: `backend/tests/test_ratgeber_render.py`

**Interfaces:**
- Consumes: `_seitenrahmen`, `Article`
- Produces: `render_index_page(articles: list[Article]) -> str`

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_ratgeber_render.py` anhängen:

```python
from app.services.ratgeber_render import render_index_page


def _kurz(slug, titel, cluster):
    return Article(slug=slug, title=titel, cluster=cluster,
                   summary=f"Kurzfassung {slug}", status="live",
                   published_at="2026-08-21")


def test_uebersicht_gruppiert_nach_cluster():
    seiten = [
        _kurz("a", "Beitrag A", "Einführung"),
        _kurz("b", "Beitrag B", "Lager"),
        _kurz("c", "Beitrag C", "Einführung"),
    ]
    html = render_index_page(seiten)
    assert "<h2>Einführung</h2>" in html
    assert "<h2>Lager</h2>" in html
    assert html.count('href="/ratgeber/') == 3


def test_uebersicht_traegt_canonical_und_collectionpage():
    html = render_index_page([_kurz("a", "Beitrag A", "Einführung")])
    assert '<link rel="canonical" href="https://novaerp.de/ratgeber"' in html
    graph = json.loads(LD_BLOCK.findall(html)[0])["@graph"]
    assert any(k["@type"] == "CollectionPage" for k in graph)


def test_leere_uebersicht_bleibt_eine_gueltige_seite():
    html = render_index_page([])
    assert "<h1>Ratgeber</h1>" in html
    assert json.loads(LD_BLOCK.findall(html)[0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ratgeber_render.py -q -k uebersicht`
Expected: FAIL — `ImportError: cannot import name 'render_index_page'`

- [ ] **Step 3: Write minimal implementation**

An `backend/app/services/ratgeber_render.py` anhängen:

```python
def render_index_page(articles: list[Article]) -> str:
    """Übersicht aller veröffentlichten Beiträge, nach Cluster gruppiert."""
    url = f"{canonical_origin()}/ratgeber"
    beschreibung = ("Praxisbeiträge zu ERP-Einführung, Lager, Produktion und "
                    "Buchhaltung für kleine und mittlere Unternehmen.")

    gruppen: dict[str, list[Article]] = {}
    for a in articles:
        gruppen.setdefault(a.cluster or "Allgemein", []).append(a)

    zeilen = ["<h1>Ratgeber</h1>", f"<p>{_e(beschreibung)}</p>"]
    if not articles:
        zeilen.append('<p class="meta">Die ersten Beiträge erscheinen in Kürze.</p>')
    for cluster in sorted(gruppen):
        zeilen.append(f"<h2>{_e(cluster)}</h2>")
        for a in gruppen[cluster]:
            zeilen.append(
                f'<a class="karte" href="/ratgeber/{_e(a.slug)}">'
                f'<div class="t">{_e(a.title)}</div>'
                + (f'<div class="s">{_e(a.summary)}</div>' if a.summary else "")
                + "</a>"
            )
    zeilen.append('<a href="/" class="back">← Zurück zur Startseite</a>')

    graph = [
        {
            "@type": "CollectionPage",
            "@id": url,
            "url": url,
            "name": "Ratgeber — NovaERP",
            "description": beschreibung,
            "inLanguage": "de-DE",
            "isPartOf": {"@id": f"{canonical_origin()}/#website"},
            "publisher": {"@id": f"{canonical_origin()}/#org"},
        },
        {
            "@type": "BreadcrumbList",
            "@id": f"{url}#breadcrumb",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Start",
                 "item": f"{canonical_origin()}/"},
                {"@type": "ListItem", "position": 2, "name": "Ratgeber", "item": url},
            ],
        },
    ]

    return _seitenrahmen("Ratgeber — NovaERP", beschreibung, url, graph,
                         "\n".join(zeilen))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_ratgeber_render.py -q`
Expected: PASS (17 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ratgeber_render.py backend/tests/test_ratgeber_render.py
git commit -m "feat(ratgeber): Übersichtsseite nach Clustern"
```

---

### Task 6: Öffentliche Routen und Einbindung in main.py

**Files:**
- Create: `backend/app/api/ratgeber_public.py`
- Modify: `backend/app/main.py` (Router-Einbindung neben `seo_public.router`)
- Test: `backend/tests/test_ratgeber_public.py`

**Interfaces:**
- Consumes: `app.core.ratgeber.get/published`, `render_article_page`, `render_index_page`, `app.core.site.is_apex_host/hostname/marketing_dir`
- Produces: `router` (APIRouter ohne Präfix)

- [ ] **Step 1: Write the failing test**

`backend/tests/test_ratgeber_public.py` anlegen:

```python
"""Tests für die öffentlichen Ratgeber-Routen."""
import pytest
from fastapi.testclient import TestClient

from app.core import ratgeber
from app.main import app

APEX = {"Host": "novaerp.de"}
TENANT = {"Host": "dev.novaerp.de"}


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("RATGEBER_DB_PATH", str(tmp_path / "ratgeber.db"))
    return TestClient(app)


def _live(slug="erp-einfuehrung", titel="ERP einführen ohne Chaos"):
    ratgeber.save(ratgeber.Article(
        slug=slug, title=titel, cluster="Einführung",
        description="Was ein ERP-Projekt kostet.",
        summary="Scheitert selten an der Software.",
        body="## Vorbereitung\n\nErst Prozesse, dann Software.",
    ))
    return ratgeber.publish(slug)


def test_uebersicht_ist_erreichbar(web):
    _live()
    r = web.get("/ratgeber", headers=APEX)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "ERP einführen ohne Chaos" in r.text


def test_beitrag_wird_serverseitig_ausgeliefert(web):
    _live()
    r = web.get("/ratgeber/erp-einfuehrung", headers=APEX)
    assert r.status_code == 200
    # Ohne JavaScript lesbar — sonst sieht ein Crawler nichts.
    assert "<h1>ERP einführen ohne Chaos</h1>" in r.text
    assert "Erst Prozesse, dann Software." in r.text


def test_entwurf_ist_oeffentlich_nicht_sichtbar(web):
    ratgeber.save(ratgeber.Article(slug="geheim", title="Noch nicht fertig"))
    r = web.get("/ratgeber/geheim", headers=APEX)
    assert r.status_code == 404


def test_unbekannter_beitrag_gibt_404(web):
    r = web.get("/ratgeber/gibt-es-nicht", headers=APEX)
    assert r.status_code == 404


def test_ratgeber_gibt_es_nur_auf_dem_apex(web):
    _live()
    assert web.get("/ratgeber", headers=TENANT).status_code == 404
    assert web.get("/ratgeber/erp-einfuehrung", headers=TENANT).status_code == 404


def test_ungueltiger_slug_wird_abgewiesen(web):
    r = web.get("/ratgeber/Nicht Erlaubt", headers=APEX)
    assert r.status_code == 404


def test_teaser_zeigt_auf_den_folgebeitrag(web):
    _live("lager-optimieren", "Lager optimieren")
    ratgeber.save(ratgeber.Article(
        slug="erp-einfuehrung", title="ERP einführen ohne Chaos",
        teaser_slug="lager-optimieren", status="live",
    ))
    ratgeber.publish("erp-einfuehrung")
    r = web.get("/ratgeber/erp-einfuehrung", headers=APEX)
    assert 'href="/ratgeber/lager-optimieren"' in r.text


def test_teaser_auf_einen_entwurf_wird_nicht_verlinkt(web):
    ratgeber.save(ratgeber.Article(slug="spaeter", title="Kommt noch"))
    _live()
    ratgeber.save(ratgeber.Article(
        slug="erp-einfuehrung", title="ERP einführen ohne Chaos",
        teaser_slug="spaeter", status="live",
    ))
    ratgeber.publish("erp-einfuehrung")
    r = web.get("/ratgeber/erp-einfuehrung", headers=APEX)
    assert "/ratgeber/spaeter" not in r.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ratgeber_public.py -q`
Expected: FAIL — die Routen fehlen, der Catch-All liefert die Marketing-Startseite mit 200 statt 404

- [ ] **Step 3: Write minimal implementation**

`backend/app/api/ratgeber_public.py` anlegen:

```python
"""Öffentliche Ratgeber-Seiten.

Serverseitig gerendert, damit ein Crawler den Text ohne JavaScript sieht.
Nur der Apex antwortet, und nur mit Beiträgen im Status ``live`` — Entwürfe
werden ausschließlich über die Admin-Vorschau sichtbar.

Der Router muss in ``main.py`` VOR dem Catch-All eingebunden werden.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.core import ratgeber
from app.core.site import hostname, is_apex_host, marketing_dir
from app.services.ratgeber_render import render_article_page, render_index_page

router = APIRouter(include_in_schema=False)


def _nicht_gefunden() -> HTMLResponse | JSONResponse:
    """Dieselbe 404-Seite wie der Rest des Apex."""
    seite = marketing_dir() / "404.html"
    if seite.exists():
        return HTMLResponse(seite.read_text(encoding="utf-8"), status_code=404)
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


@router.get("/ratgeber", response_class=HTMLResponse)
async def ratgeber_index(request: Request):
    if not is_apex_host(hostname(request)):
        return _nicht_gefunden()
    return HTMLResponse(render_index_page(ratgeber.published()))


@router.get("/ratgeber/{slug}", response_class=HTMLResponse)
async def ratgeber_beitrag(slug: str, request: Request):
    if not is_apex_host(hostname(request)):
        return _nicht_gefunden()
    beitrag = ratgeber.get(slug)
    if beitrag is None or beitrag.status != ratgeber.STATUS_LIVE:
        return _nicht_gefunden()

    nachfolger = None
    if beitrag.teaser_slug:
        kandidat = ratgeber.get(beitrag.teaser_slug)
        # Ein Teaser auf einen Entwurf führt Leser und Crawler ins 404.
        if kandidat is not None and kandidat.status == ratgeber.STATUS_LIVE:
            nachfolger = kandidat

    return HTMLResponse(render_article_page(beitrag, nachfolger=nachfolger))
```

In `backend/app/main.py` den Import ergänzen:

```python
from app.api import ratgeber_public, seo_public
```

und direkt nach `app.include_router(seo_public.router)` einfügen:

```python
# Öffentlicher Ratgeber. Ebenfalls vor dem Catch-All.
app.include_router(ratgeber_public.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_ratgeber_public.py tests/test_seo_public.py -q`
Expected: PASS (46 Tests, 1 übersprungen)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/ratgeber_public.py backend/app/main.py backend/tests/test_ratgeber_public.py
git commit -m "feat(ratgeber): öffentliche Routen /ratgeber und /ratgeber/<slug>"
```

---

### Task 7: Sitemap und llms.txt kennen die Beiträge

Teil 1 hat `content_articles()` als Rumpf angelegt. Jetzt liest er aus der Datenbank — Sitemap und `llms.txt` selbst werden nicht angefasst.

**Files:**
- Modify: `backend/app/api/seo_public.py` (Funktion `content_articles`)
- Test: `backend/tests/test_ratgeber_public.py`

**Interfaces:**
- Consumes: `app.core.ratgeber.published`
- Produces: `content_articles() -> list[SitemapArticle]` mit echtem Inhalt

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_ratgeber_public.py` anhängen:

```python
def test_sitemap_listet_veroeffentlichte_beitraege(web):
    _live()
    r = web.get("/sitemap.xml", headers=APEX)
    assert "https://novaerp.de/ratgeber/erp-einfuehrung" in r.text
    assert "<lastmod>" in r.text


def test_sitemap_zeigt_keine_entwuerfe(web):
    ratgeber.save(ratgeber.Article(slug="geheim", title="Noch nicht fertig"))
    r = web.get("/sitemap.xml", headers=APEX)
    assert "geheim" not in r.text


def test_llms_txt_nennt_die_beitraege(web):
    _live()
    r = web.get("/llms.txt", headers=APEX)
    assert "## Ratgeber" in r.text
    assert "https://novaerp.de/ratgeber/erp-einfuehrung" in r.text


def test_sitemap_ueberlebt_eine_defekte_beitragsdatenbank(web, monkeypatch, tmp_path):
    # Ein kaputter Speicher darf robots/sitemap nicht mitreißen — sonst
    # verliert die ganze Domain ihre Indexierbarkeit.
    kaputt = tmp_path / "kaputt.db"
    kaputt.write_text("kein sqlite")
    monkeypatch.setenv("RATGEBER_DB_PATH", str(kaputt))
    r = web.get("/sitemap.xml", headers=APEX)
    assert r.status_code == 200
    assert "https://novaerp.de/impressum" in r.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ratgeber_public.py -q -k "sitemap or llms"`
Expected: FAIL — die Beiträge tauchen nicht auf, `content_articles()` liefert `[]`

- [ ] **Step 3: Write minimal implementation**

In `backend/app/api/seo_public.py` die Funktion ersetzen:

```python
def content_articles() -> list[SitemapArticle]:
    """Veröffentlichte Ratgeber-Beiträge für Sitemap und llms.txt.

    Fehler der Beitragsdatenbank werden hier geschluckt: robots.txt und
    Sitemap sind die Grundlage der Indexierung. Sie dürfen nicht ausfallen,
    weil der Ratgeber-Speicher klemmt.
    """
    try:
        from app.core import ratgeber
        beitraege = ratgeber.published()
    except Exception:  # noqa: BLE001 — bewusst breit, siehe Docstring
        return []

    ergebnis = []
    for a in beitraege:
        lastmod = None
        for quelle in (a.updated_at, a.published_at):
            if quelle:
                try:
                    lastmod = date.fromisoformat(quelle[:10])
                    break
                except ValueError:
                    continue
        ergebnis.append(SitemapArticle(
            slug=a.slug,
            title=a.title,
            summary=a.summary or a.description,
            lastmod=lastmod,
        ))
    return ergebnis
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_ratgeber_public.py tests/test_seo_public.py -q`
Expected: PASS (50 Tests, 1 übersprungen)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/seo_public.py backend/tests/test_ratgeber_public.py
git commit -m "feat(ratgeber): Sitemap und llms.txt ziehen die veröffentlichten Beiträge"
```

---

### Task 8: Admin-API

**Files:**
- Create: `backend/app/api/v1/ratgeber.py`
- Modify: `backend/app/main.py` (Router einbinden, neben `platform.router`)
- Test: `backend/tests/test_ratgeber_admin.py`

**Interfaces:**
- Consumes: `app.api.v1.platform._require_admin`, `app.core.ratgeber.*`, `render_article_page`
- Produces: `router` mit Präfix `/platform/ratgeber`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_ratgeber_admin.py` anlegen:

```python
"""Tests für die Ratgeber-Admin-API."""
import pytest
from fastapi.testclient import TestClient

from app.core import ratgeber
from app.main import app

API = "/api/v1/platform/ratgeber"
SCHLUESSEL = "test-admin-key-123"


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("RATGEBER_DB_PATH", str(tmp_path / "ratgeber.db"))
    monkeypatch.setenv("PLATFORM_ADMIN_KEY", SCHLUESSEL)
    return TestClient(app)


def kopf():
    return {"X-Platform-Admin-Key": SCHLUESSEL}


ENTWURF = {
    "title": "ERP einführen ohne Chaos",
    "cluster": "Einführung",
    "description": "Was ein ERP-Projekt kostet.",
    "author": "Nikolaj Unser-Richter",
    "reading_minutes": 7,
    "summary": "Scheitert selten an der Software.",
    "body": "## Vorbereitung\n\nErst Prozesse, dann Software.",
    "faq": [{"frage": "Wie lange?", "antwort": "Vier bis acht Wochen."}],
    "sources": [{"title": "Destatis", "url": "https://www.destatis.de"}],
}


def test_ohne_key_kein_zugriff(web):
    assert web.get(API).status_code == 401
    assert web.put(f"{API}/x", json=ENTWURF).status_code == 401


def test_falscher_key_wird_abgewiesen(web):
    r = web.get(API, headers={"X-Platform-Admin-Key": "falsch"})
    assert r.status_code == 401


def test_anlegen_lesen_und_auflisten(web):
    r = web.put(f"{API}/erp-einfuehrung", json=ENTWURF, headers=kopf())
    assert r.status_code == 200
    assert r.json()["status"] == "entwurf"

    r = web.get(f"{API}/erp-einfuehrung", headers=kopf())
    assert r.json()["title"] == "ERP einführen ohne Chaos"
    assert r.json()["faq"][0]["frage"] == "Wie lange?"

    r = web.get(API, headers=kopf())
    assert [x["slug"] for x in r.json()["articles"]] == ["erp-einfuehrung"]


def test_ungueltiger_slug_gibt_400(web):
    r = web.put(f"{API}/Gross Und Falsch", json=ENTWURF, headers=kopf())
    assert r.status_code == 400


def test_veroeffentlichen_und_zurueckziehen(web):
    web.put(f"{API}/erp-einfuehrung", json=ENTWURF, headers=kopf())
    r = web.post(f"{API}/erp-einfuehrung/publish", headers=kopf())
    assert r.status_code == 200
    assert r.json()["status"] == "live"
    assert r.json()["published_at"]

    r = web.post(f"{API}/erp-einfuehrung/unpublish", headers=kopf())
    assert r.json()["status"] == "entwurf"


def test_veroeffentlichen_eines_unbekannten_beitrags_gibt_404(web):
    r = web.post(f"{API}/gibt-es-nicht/publish", headers=kopf())
    assert r.status_code == 404


def test_vorschau_rendert_auch_entwuerfe(web):
    web.put(f"{API}/erp-einfuehrung", json=ENTWURF, headers=kopf())
    r = web.get(f"{API}/erp-einfuehrung/preview", headers=kopf())
    assert r.status_code == 200
    assert "<h1>ERP einführen ohne Chaos</h1>" in r.text


def test_loeschen(web):
    web.put(f"{API}/erp-einfuehrung", json=ENTWURF, headers=kopf())
    assert web.delete(f"{API}/erp-einfuehrung", headers=kopf()).status_code == 204
    assert web.get(f"{API}/erp-einfuehrung", headers=kopf()).status_code == 404


def test_warteschlange_sortieren(web):
    for slug in ("a", "b", "c"):
        web.put(f"{API}/{slug}", json={**ENTWURF, "status": "warteschlange"},
                headers=kopf())
    r = web.post(f"{API}/queue", json={"slugs": ["c", "a", "b"]}, headers=kopf())
    assert r.status_code == 200
    assert [x.slug for x in ratgeber.list_all(status="warteschlange")] == ["c", "a", "b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ratgeber_admin.py -q`
Expected: FAIL — 404 auf allen Routen, das Modul existiert nicht

- [ ] **Step 3: Write minimal implementation**

`backend/app/api/v1/ratgeber.py` anlegen:

```python
"""Redaktions-API für den Ratgeber.

Geschützt durch denselben ``X-Platform-Admin-Key`` wie die übrige
Platform-Administration — der Prüfcode wird bewusst importiert statt
kopiert, damit es nur einen zeitkonstanten Vergleich im Projekt gibt.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.v1.platform import _require_admin as require_platform_admin
from app.core import ratgeber
from app.services.ratgeber_render import render_article_page

router = APIRouter(prefix="/platform/ratgeber", tags=["Ratgeber"])


class BeitragBody(BaseModel):
    title: str
    cluster: str = ""
    description: str = ""
    author: str = ""
    reading_minutes: int = 0
    summary: str = ""
    body: str = ""
    faq: list[dict] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    teaser_slug: str = ""
    status: str = ratgeber.STATUS_ENTWURF


class QueueBody(BaseModel):
    slugs: list[str]


def _holen(slug: str) -> ratgeber.Article:
    beitrag = ratgeber.get(slug)
    if beitrag is None:
        raise HTTPException(status_code=404, detail=f"Kein Beitrag '{slug}'")
    return beitrag


@router.get("")
def liste(status: Optional[str] = None, _: None = Depends(require_platform_admin)):
    """Alle Beiträge, optional nach Status."""
    return {"articles": [a.as_dict() for a in ratgeber.list_all(status=status)]}


@router.post("/queue")
def warteschlange(body: QueueBody, _: None = Depends(require_platform_admin)):
    """Reihenfolge der Warteschlange festschreiben."""
    try:
        ratgeber.set_queue(body.slugs)
    except ratgeber.SlugFehler as fehler:
        raise HTTPException(status_code=400, detail=str(fehler))
    return {"ok": True, "count": len(body.slugs)}


@router.get("/{slug}")
def lesen(slug: str, _: None = Depends(require_platform_admin)):
    return _holen(slug).as_dict()


@router.put("/{slug}")
def speichern(slug: str, body: BeitragBody,
              _: None = Depends(require_platform_admin)):
    """Anlegen oder aktualisieren. Setzt nie das Veröffentlichungsdatum."""
    try:
        gespeichert = ratgeber.save(ratgeber.Article(slug=slug, **body.model_dump()))
    except (ratgeber.SlugFehler, ValueError) as fehler:
        raise HTTPException(status_code=400, detail=str(fehler))
    return gespeichert.as_dict()


@router.delete("/{slug}", status_code=204)
def loeschen(slug: str, _: None = Depends(require_platform_admin)):
    if not ratgeber.delete(slug):
        raise HTTPException(status_code=404, detail=f"Kein Beitrag '{slug}'")
    return Response(status_code=204)


@router.post("/{slug}/publish")
def veroeffentlichen(slug: str, _: None = Depends(require_platform_admin)):
    _holen(slug)
    return ratgeber.publish(slug).as_dict()


@router.post("/{slug}/unpublish")
def zurueckziehen(slug: str, _: None = Depends(require_platform_admin)):
    _holen(slug)
    return ratgeber.unpublish(slug).as_dict()


@router.get("/{slug}/preview", response_class=HTMLResponse)
def vorschau(slug: str, _: None = Depends(require_platform_admin)):
    """Die fertige Seite, auch für Entwürfe.

    Derselbe Renderer wie öffentlich — sonst prüft die Redaktion etwas
    anderes, als später ausgeliefert wird.
    """
    beitrag = _holen(slug)
    nachfolger = ratgeber.get(beitrag.teaser_slug) if beitrag.teaser_slug else None
    return HTMLResponse(render_article_page(beitrag, nachfolger=nachfolger))
```

> Reihenfolge beachten: `/queue` steht vor `/{slug}`, sonst matcht der
> Platzhalter zuerst und `queue` landet als Slug in `lesen`.

In `backend/app/main.py` neben dem Platform-Router einbinden:

```python
from app.api.v1 import ratgeber as ratgeber_admin  # zur bestehenden v1-Importzeile passend ergänzen

app.include_router(
    ratgeber_admin.router,
    prefix="/api/v1",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_ratgeber_admin.py -q`
Expected: PASS (9 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/ratgeber.py backend/app/main.py backend/tests/test_ratgeber_admin.py
git commit -m "feat(ratgeber): Redaktions-API hinter dem Platform-Admin-Key"
```

---

### Task 9: Editor im Platform-Admin

**Files:**
- Modify: `backend/static_admin/index.html`
- Test: manuell (statische Seite ohne Testinfrastruktur), plus Smoke-Test der API-Pfade

**Interfaces:**
- Consumes: `/api/v1/platform/ratgeber*`
- Produces: nichts für andere Tasks

- [ ] **Step 1: Abschnitt in die Seite einsetzen**

Nach dem `<!-- Tenants -->`-Block in `backend/static_admin/index.html` einfügen:

```html
      <!-- Ratgeber -->
      <div class="section">
        <h2>Ratgeber</h2>
        <div class="create-row" style="margin-bottom:1rem">
          <div class="field">
            <label for="artSlug">Slug</label>
            <input id="artSlug" type="text" placeholder="erp-einfuehrung" />
          </div>
          <button class="btn btn-ghost" onclick="neuerBeitrag()">Neu</button>
        </div>
        <div id="artList"><div class="empty">Lädt…</div></div>

        <div id="artForm" class="hidden" style="margin-top:1.5rem;border-top:1px solid var(--line);padding-top:1.5rem">
          <div class="create-row">
            <div class="field"><label for="artTitle">Titel</label><input id="artTitle" type="text" /></div>
            <div class="field"><label for="artCluster">Cluster</label><input id="artCluster" type="text" placeholder="Einführung" /></div>
            <div class="field"><label for="artMinutes">Lesezeit (Min.)</label><input id="artMinutes" type="text" placeholder="7" /></div>
          </div>
          <div class="create-row" style="margin-top:.75rem">
            <div class="field"><label for="artAuthor">Autor</label><input id="artAuthor" type="text" /></div>
            <div class="field"><label for="artTeaser">Teaser auf Slug</label><input id="artTeaser" type="text" placeholder="lager-optimieren" /></div>
          </div>
          <div style="margin-top:.75rem"><label for="artDesc">Meta-Beschreibung</label><input id="artDesc" type="text" /></div>
          <div style="margin-top:.75rem"><label for="artSummary">Kurzfassung</label><input id="artSummary" type="text" /></div>
          <div style="margin-top:.75rem">
            <label for="artBody">Text (Markdown-Teilmenge: ## ### - **fett** [Text](URL))</label>
            <textarea id="artBody" rows="14" style="width:100%;background:var(--panel-2);border:1px solid var(--line);border-radius:.6rem;color:var(--ink-0);padding:.8rem 1rem;font-family:ui-monospace,monospace;font-size:.88rem"></textarea>
          </div>
          <div style="margin-top:.75rem">
            <label for="artFaq">FAQ als JSON — [{"frage":"…","antwort":"…"}]</label>
            <textarea id="artFaq" rows="4" style="width:100%;background:var(--panel-2);border:1px solid var(--line);border-radius:.6rem;color:var(--ink-0);padding:.8rem 1rem;font-family:ui-monospace,monospace;font-size:.85rem">[]</textarea>
          </div>
          <div style="margin-top:.75rem">
            <label for="artSources">Quellen als JSON — [{"title":"…","url":"https://…"}]</label>
            <textarea id="artSources" rows="4" style="width:100%;background:var(--panel-2);border:1px solid var(--line);border-radius:.6rem;color:var(--ink-0);padding:.8rem 1rem;font-family:ui-monospace,monospace;font-size:.85rem">[]</textarea>
          </div>
          <div style="margin-top:1rem;display:flex;gap:.6rem;flex-wrap:wrap">
            <button class="btn btn-bronze" onclick="beitragSpeichern()">Speichern</button>
            <button class="btn btn-ghost" onclick="beitragVorschau()">Vorschau</button>
            <button class="btn btn-ghost" onclick="beitragPublish(true)">Veröffentlichen</button>
            <button class="btn btn-ghost" onclick="beitragPublish(false)">Zurückziehen</button>
            <button class="btn btn-danger" onclick="beitragLoeschen()">Löschen</button>
          </div>
        </div>
      </div>
```

- [ ] **Step 2: JavaScript ergänzen**

Vor `// Auto-login if key present` einfügen:

```javascript
    const ART_API = '/api/v1/platform/ratgeber';
    let aktuellerSlug = '';

    async function ladeBeitraege(){
      try {
        const res = await fetch(ART_API, { headers: headers() });
        if(!res.ok) return;
        const data = await res.json();
        const el = document.getElementById('artList');
        const arts = data.articles || [];
        if(!arts.length){ el.innerHTML = '<div class="empty">Noch keine Beiträge.</div>'; return; }
        el.innerHTML = `
          <table>
            <thead><tr><th>Slug</th><th>Titel</th><th>Cluster</th><th>Status</th><th>Veröffentlicht</th></tr></thead>
            <tbody>
              ${arts.map(a => `
                <tr style="cursor:pointer" onclick="beitragOeffnen('${esc(a.slug)}')">
                  <td class="slug">${esc(a.slug)}</td>
                  <td>${esc(a.title)}</td>
                  <td class="muted">${esc(a.cluster)}</td>
                  <td>${esc(a.status)}</td>
                  <td class="muted">${esc(a.published_at || '–')}</td>
                </tr>`).join('')}
            </tbody>
          </table>`;
      } catch(e){ toast('Ratgeber laden fehlgeschlagen: ' + e.message, 'err'); }
    }

    function formFuellen(a){
      document.getElementById('artForm').classList.remove('hidden');
      document.getElementById('artSlug').value = a.slug || '';
      document.getElementById('artTitle').value = a.title || '';
      document.getElementById('artCluster').value = a.cluster || '';
      document.getElementById('artMinutes').value = a.reading_minutes || '';
      document.getElementById('artAuthor').value = a.author || '';
      document.getElementById('artTeaser').value = a.teaser_slug || '';
      document.getElementById('artDesc').value = a.description || '';
      document.getElementById('artSummary').value = a.summary || '';
      document.getElementById('artBody').value = a.body || '';
      document.getElementById('artFaq').value = JSON.stringify(a.faq || [], null, 2);
      document.getElementById('artSources').value = JSON.stringify(a.sources || [], null, 2);
      aktuellerSlug = a.slug || '';
    }

    function neuerBeitrag(){ formFuellen({}); }

    async function beitragOeffnen(slug){
      const res = await fetch(`${ART_API}/${encodeURIComponent(slug)}`, { headers: headers() });
      if(!res.ok){ toast('Beitrag nicht gefunden', 'err'); return; }
      formFuellen(await res.json());
    }

    function jsonFeld(id){
      try { return JSON.parse(document.getElementById(id).value || '[]'); }
      catch(e){ toast(`Feld ${id}: kein gültiges JSON`, 'err'); throw e; }
    }

    async function beitragSpeichern(){
      const slug = document.getElementById('artSlug').value.trim().toLowerCase();
      if(!slug){ toast('Slug fehlt', 'err'); return; }
      let faq, sources;
      try { faq = jsonFeld('artFaq'); sources = jsonFeld('artSources'); } catch(e){ return; }
      const body = {
        title: document.getElementById('artTitle').value.trim(),
        cluster: document.getElementById('artCluster').value.trim(),
        description: document.getElementById('artDesc').value.trim(),
        author: document.getElementById('artAuthor').value.trim(),
        reading_minutes: parseInt(document.getElementById('artMinutes').value || '0', 10) || 0,
        summary: document.getElementById('artSummary').value.trim(),
        body: document.getElementById('artBody').value,
        teaser_slug: document.getElementById('artTeaser').value.trim().toLowerCase(),
        faq, sources,
      };
      const res = await fetch(`${ART_API}/${encodeURIComponent(slug)}`,
        { method:'PUT', headers: headers(), body: JSON.stringify(body) });
      const antwort = await res.json().catch(()=>({}));
      if(res.ok){ aktuellerSlug = slug; toast('Gespeichert', 'ok'); ladeBeitraege(); }
      else { toast(antwort.detail || 'Speichern fehlgeschlagen', 'err'); }
    }

    function beitragVorschau(){
      if(!aktuellerSlug){ toast('Erst speichern', 'err'); return; }
      // Die Vorschau braucht den Key im Header — daher holen und als Blob öffnen.
      fetch(`${ART_API}/${encodeURIComponent(aktuellerSlug)}/preview`, { headers: headers() })
        .then(r => r.text())
        .then(html => {
          const w = window.open('', '_blank');
          w.document.write(html); w.document.close();
        })
        .catch(e => toast('Vorschau fehlgeschlagen: ' + e.message, 'err'));
    }

    async function beitragPublish(live){
      if(!aktuellerSlug){ toast('Erst speichern', 'err'); return; }
      const pfad = live ? 'publish' : 'unpublish';
      const res = await fetch(`${ART_API}/${encodeURIComponent(aktuellerSlug)}/${pfad}`,
        { method:'POST', headers: headers() });
      if(res.ok){ toast(live ? 'Veröffentlicht' : 'Zurückgezogen', 'ok'); ladeBeitraege(); }
      else { toast('Statuswechsel fehlgeschlagen', 'err'); }
    }

    async function beitragLoeschen(){
      if(!aktuellerSlug) return;
      if(!confirm(`Beitrag „${aktuellerSlug}" löschen?`)) return;
      const res = await fetch(`${ART_API}/${encodeURIComponent(aktuellerSlug)}`,
        { method:'DELETE', headers: headers() });
      if(res.status === 204){
        toast('Gelöscht', 'ok');
        document.getElementById('artForm').classList.add('hidden');
        aktuellerSlug = '';
        ladeBeitraege();
      } else { toast('Löschen fehlgeschlagen', 'err'); }
    }
```

und in `loadAll()` nach `renderTenants(...)` ergänzen:

```javascript
        await ladeBeitraege();
```

- [ ] **Step 3: Gesamtlauf**

Run: `cd backend && python -m pytest tests/test_ratgeber_store.py tests/test_ratgeber_render.py tests/test_ratgeber_public.py tests/test_ratgeber_admin.py tests/test_seo_public.py -q`
Expected: PASS

Run: `cd backend && python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py`
Expected: keine neuen Fehler gegenüber dem Stand vor Task 1 (Baseline: 15 vorbestehende Fehler, 1 Fehlerfall)

- [ ] **Step 4: Commit**

```bash
git add backend/static_admin/index.html
git commit -m "feat(ratgeber): Redaktions-Editor im Platform-Admin"
```

---

## Abnahme

| Prüfung | Erwartung |
|---|---|
| `GET /ratgeber` (Apex) | 200, HTML, Beiträge nach Cluster |
| `GET /ratgeber/<slug>` (Apex, live) | 200, Text ohne JavaScript lesbar, Article-Schema |
| `GET /ratgeber/<slug>` (Entwurf) | 404 |
| `GET /ratgeber` (Tenant-Host) | 404 |
| `GET /sitemap.xml` | enthält jeden Live-Beitrag mit `lastmod` |
| `GET /llms.txt` | Abschnitt „## Ratgeber" mit absoluten URLs |
| Admin-API ohne Key | 401 |
| Zweites `publish` nach Textkorrektur | `published_at` unverändert |
| Beitragsdatenbank defekt | Sitemap bleibt 200 mit den statischen Seiten |

Außerhalb des Codes: das `./data`-Volume braucht ab jetzt ein Backup — die Redaktionsinhalte liegen nicht im Git.
