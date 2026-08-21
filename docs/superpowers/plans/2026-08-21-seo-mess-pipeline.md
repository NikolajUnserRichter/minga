# SEO/GEO-Mess-Pipeline Implementation Plan (Teil 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nächtliche Messung von Search-Console-Daten, KI-Zitaten (Gemini mit Google-Search-Grounding) und First-Party-KI-Verweisen — mit hartem Kostenriegel, Discovery/Marke-Trennung und Auswertung im Platform-Admin.

**Architecture:** Eine eigene SQLite-Datei `seo.db` im persistenten `./data`-Volume nimmt Tagesdaten auf (`app/core/seo_store.py`). Drei Sammler in `app/services/seo_geo.py` — jeder einzeln abschaltbar und ohne Zugangsdaten inaktiv — laufen nächtlich als APScheduler-Job `seo-geo-nightly` (analog `demo-reset`, nicht mandantengebunden). Auswertung, heuristische Vorschläge und ein manueller Auslöser liegen hinter dem `X-Platform-Admin-Key` und werden im Platform-Admin-Dashboard angezeigt. Automatisch ausgerollt wird nichts.

**Tech Stack:** FastAPI, SQLite (stdlib `sqlite3`, WAL), httpx (vorhanden), python-jose für den Service-Account-JWT (vorhanden), APScheduler (vorhanden). **Keine neuen Einträge in `backend/requirements.txt`.**

**Spec:** `docs/superpowers/specs/2026-08-21-seo-geo-novaerp-design.md` (Abschnitt „Teil 3 — Mess- und Optimierpipeline")

## Global Constraints

- Keine neuen Einträge in `backend/requirements.txt` — Google-Zugriff über httpx + python-jose statt `google-api-python-client`.
- Es existieren weder GSC-Property, Service-Account noch Gemini-Key: **jeder Sammler muss ohne Zugangsdaten sauber als No-Op mit `{"status": "inaktiv", ...}` durchlaufen.**
- Harter Kostenriegel VOR jedem Grounding-Request: `GEO_BUDGET_DAY` (Default 50) und `GEO_BUDGET_MONTH` (Default 4500, unterhalb des Gemini-Freikontingents von 5.000/Monat).
- GEO-Quoten getrennt nach `discovery` und `marke` — Marken-Prompts nennen die Domain zwangsläufig, eine Mischquote täuscht Fortschritt vor.
- Discovery-Prompts dürfen „NovaERP" nicht enthalten.
- Speicherort: `Path(get_settings().tenants_dir).parent / "seo.db"`, Test-Override über `SEO_DB_PATH` (Muster: `app/core/ratgeber.py`).
- Deutsche Docstrings und Kommentare, wie im übrigen Backend.
- Tests laufen aus `backend/`: jeder Aufruf mit `cd /Users/nikolajunser-richter/minga-greens-erp/backend && python -m pytest …`.
- Kein automatisches Umschreiben der Marketing-Seiten; Vorschläge sind reine Anzeige im Dashboard.
- Statuswerte der Sammler: `ok`, `inaktiv`, `fehler`.

---

### Task 1: seo_store — GSC-Tagesdaten und Änderungsprotokoll

**Files:**
- Create: `backend/app/core/seo_store.py`
- Test: `backend/tests/test_seo_store.py`

**Interfaces:**
- Produces: `db_path() -> Path`, `record_gsc_rows(day: str, rows: list[dict]) -> int`, `gsc_summary(days=28, heute=None) -> dict`, `gsc_top_queries(days=28, limit=20, heute=None) -> list[dict]`, `log_change(quelle: str, nachricht: str) -> None`, `changelog_entries(limit=50) -> list[dict]`
- `_conn()` legt ALLE Tabellen an (auch die aus Task 2), damit spätere Tasks das Schema nicht anfassen.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_seo_store.py` anlegen:

```python
"""Tests für den SEO/GEO-Messdatenspeicher."""
from datetime import date

import pytest

from app.core import seo_store


@pytest.fixture(autouse=True)
def eigene_db(tmp_path, monkeypatch):
    """Jeder Test bekommt eine frische Datei — der Speicher ist global."""
    monkeypatch.setenv("SEO_DB_PATH", str(tmp_path / "seo.db"))


def test_gsc_zeilen_roundtrip_und_idempotenz():
    n = seo_store.record_gsc_rows("2026-08-18", [
        {"page": "https://novaerp.de/", "query": "erp kmu",
         "clicks": 3, "impressions": 80, "position": 6.4},
        {"page": "https://novaerp.de/ratgeber/erp-einfuehrung",
         "query": "erp einführung", "clicks": 1, "impressions": 40, "position": 9.1},
    ])
    assert n == 2
    # Zweiter Import desselben Tages überschreibt statt zu doppeln.
    seo_store.record_gsc_rows("2026-08-18", [
        {"page": "https://novaerp.de/", "query": "erp kmu",
         "clicks": 5, "impressions": 90, "position": 6.0},
    ])
    z = seo_store.gsc_summary(days=28, heute=date(2026, 8, 21))
    assert z["totals"] == {"clicks": 6, "impressions": 130}


def test_gsc_summary_ignoriert_alte_tage():
    seo_store.record_gsc_rows("2026-05-01", [
        {"page": "https://novaerp.de/", "query": "alt",
         "clicks": 99, "impressions": 999, "position": 1.0},
    ])
    seo_store.record_gsc_rows("2026-08-20", [
        {"page": "https://novaerp.de/", "query": "neu",
         "clicks": 2, "impressions": 10, "position": 3.0},
    ])
    z = seo_store.gsc_summary(days=28, heute=date(2026, 8, 21))
    assert z["totals"]["clicks"] == 2
    assert [t["day"] for t in z["per_day"]] == ["2026-08-20"]


def test_top_queries_aggregieren_ueber_seiten():
    seo_store.record_gsc_rows("2026-08-20", [
        {"page": "https://novaerp.de/", "query": "erp kmu",
         "clicks": 3, "impressions": 80, "position": 6.0},
        {"page": "https://novaerp.de/preise", "query": "erp kmu",
         "clicks": 2, "impressions": 50, "position": 8.0},
        {"page": "https://novaerp.de/", "query": "erp einführung",
         "clicks": 1, "impressions": 40, "position": 9.0},
    ])
    top = seo_store.gsc_top_queries(days=28, heute=date(2026, 8, 21))
    assert top[0]["query"] == "erp kmu"
    assert top[0]["clicks"] == 5
    assert top[0]["impressions"] == 130


def test_changelog_neueste_zuerst():
    seo_store.log_change("test", "erster")
    seo_store.log_change("test", "zweiter")
    eintraege = seo_store.changelog_entries()
    assert [e["nachricht"] for e in eintraege][:2] == ["zweiter", "erster"]
    assert eintraege[0]["quelle"] == "test"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_store.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.seo_store'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/core/seo_store.py` anlegen:

```python
"""Speicher für SEO- und GEO-Messdaten.

Eigene Datei ``seo.db`` im persistenten ``./data``-Volume, getrennt von
Redaktion (``ratgeber.db``) und Reichweitenzählung (``webstats.db``):
Messdaten wachsen täglich und dürfen die anderen Speicher nicht aufblähen.
Der Ablageort folgt ``app/core/webstats.py``.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from app.config import get_settings

ART_DISCOVERY = "discovery"
ART_MARKE = "marke"


def db_path() -> Path:
    """Ablageort der Messdatenbank; ``SEO_DB_PATH`` übersteuert für Tests."""
    override = os.environ.get("SEO_DB_PATH", "").strip()
    if override:
        pfad = Path(override)
        pfad.parent.mkdir(parents=True, exist_ok=True)
        return pfad
    base = Path(get_settings().tenants_dir).parent  # persistentes ./data
    base.mkdir(parents=True, exist_ok=True)
    return base / "seo.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(db_path()), timeout=5)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(
        "CREATE TABLE IF NOT EXISTS gsc_daily ("
        "day TEXT NOT NULL, page TEXT NOT NULL, query TEXT NOT NULL,"
        "clicks INTEGER NOT NULL DEFAULT 0,"
        "impressions INTEGER NOT NULL DEFAULT 0,"
        "position REAL NOT NULL DEFAULT 0,"
        "PRIMARY KEY (day, page, query))"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS geo_runs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "day TEXT NOT NULL, prompt_id TEXT NOT NULL, art TEXT NOT NULL,"
        "zitiert INTEGER NOT NULL DEFAULT 0,"
        "domains TEXT NOT NULL DEFAULT '[]')"
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_geo_runs_day ON geo_runs(day)")
    c.execute(
        "CREATE TABLE IF NOT EXISTS grounding_usage ("
        "day TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS ai_referrals ("
        "day TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0,"
        "domains TEXT NOT NULL DEFAULT '[]')"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS changelog ("
        "ts TEXT NOT NULL, quelle TEXT NOT NULL, nachricht TEXT NOT NULL)"
    )
    return c


def _seit(days: int, heute: Optional[date]) -> str:
    return ((heute or date.today()) - timedelta(days=days)).isoformat()


def record_gsc_rows(day: str, rows: list[dict]) -> int:
    """Tageszeilen aus der Search Console ablegen — je Tag idempotent."""
    c = _conn()
    try:
        for r in rows:
            c.execute(
                "INSERT INTO gsc_daily (day, page, query, clicks, impressions, position)"
                " VALUES (?,?,?,?,?,?)"
                " ON CONFLICT(day, page, query) DO UPDATE SET"
                " clicks=excluded.clicks, impressions=excluded.impressions,"
                " position=excluded.position",
                (day, r.get("page", ""), r.get("query", ""),
                 int(r.get("clicks", 0)), int(r.get("impressions", 0)),
                 float(r.get("position", 0.0))),
            )
        c.commit()
    finally:
        c.close()
    return len(rows)


def gsc_summary(days: int = 28, heute: Optional[date] = None) -> dict:
    """Klicks und Impressionen der letzten ``days`` Tage."""
    seit = _seit(days, heute)
    c = _conn()
    try:
        per_day = c.execute(
            "SELECT day, SUM(clicks) k, SUM(impressions) i FROM gsc_daily"
            " WHERE day >= ? GROUP BY day ORDER BY day", (seit,)
        ).fetchall()
        tot = c.execute(
            "SELECT COALESCE(SUM(clicks),0), COALESCE(SUM(impressions),0)"
            " FROM gsc_daily WHERE day >= ?", (seit,)
        ).fetchone()
    finally:
        c.close()
    return {
        "seit": seit,
        "totals": {"clicks": tot[0], "impressions": tot[1]},
        "per_day": [{"day": d, "clicks": k, "impressions": i} for d, k, i in per_day],
    }


def gsc_top_queries(days: int = 28, limit: int = 20,
                    heute: Optional[date] = None) -> list[dict]:
    """Suchanfragen nach Impressionen, über Seiten aggregiert."""
    c = _conn()
    try:
        rows = c.execute(
            "SELECT query, SUM(clicks) k, SUM(impressions) i, AVG(position) p"
            " FROM gsc_daily WHERE day >= ? GROUP BY query"
            " ORDER BY i DESC LIMIT ?", (_seit(days, heute), limit)
        ).fetchall()
    finally:
        c.close()
    return [{"query": q, "clicks": k, "impressions": i, "position": round(p, 1)}
            for q, k, i, p in rows]


def log_change(quelle: str, nachricht: str) -> None:
    """Einen Eintrag ins Änderungsprotokoll schreiben."""
    c = _conn()
    try:
        c.execute(
            "INSERT INTO changelog (ts, quelle, nachricht) VALUES (?,?,?)",
            (datetime.utcnow().isoformat(timespec="seconds"), quelle, nachricht),
        )
        c.commit()
    finally:
        c.close()


def changelog_entries(limit: int = 50) -> list[dict]:
    """Jüngste Protokolleinträge, neueste zuerst."""
    c = _conn()
    try:
        rows = c.execute(
            "SELECT ts, quelle, nachricht FROM changelog"
            " ORDER BY rowid DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        c.close()
    return [{"ts": t, "quelle": q, "nachricht": n} for t, q, n in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_store.py -q`
Expected: PASS (4 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/seo_store.py backend/tests/test_seo_store.py
git commit -m "feat(seo): Messdatenspeicher für Search-Console-Tage und Protokoll"
```

---

### Task 2: seo_store — GEO-Läufe, Grounding-Zähler, KI-Verweise

**Files:**
- Modify: `backend/app/core/seo_store.py`
- Test: `backend/tests/test_seo_store.py`

**Interfaces:**
- Produces: `record_geo_run(day, prompt_id, art, zitiert: bool, domains: list[str]) -> None`, `geo_summary(days=28, heute=None) -> dict` (Form: `{"discovery": {"laeufe", "zitiert", "quote"}, "marke": {...}}`), `grounding_increment(day: str, n=1) -> None`, `grounding_spent(day: str) -> tuple[int, int]` (Tag, laufender Monat), `record_ai_referrals(day, count, domains) -> None`, `ai_referrals_summary(days=28, heute=None) -> dict`

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_seo_store.py` anhängen:

```python
# --- GEO-Läufe, Grounding, KI-Verweise --------------------------------------


def test_geo_laeufe_werden_nach_art_getrennt():
    seo_store.record_geo_run("2026-08-21", "erp-kmu", "discovery",
                             zitiert=True, domains=["novaerp.de"])
    seo_store.record_geo_run("2026-08-21", "erp-lager", "discovery",
                             zitiert=False, domains=["sap.com"])
    seo_store.record_geo_run("2026-08-21", "marke-was-ist", "marke",
                             zitiert=True, domains=["novaerp.de"])
    z = seo_store.geo_summary(days=7, heute=date(2026, 8, 21))
    assert z["discovery"] == {"laeufe": 2, "zitiert": 1, "quote": 0.5}
    assert z["marke"]["quote"] == 1.0


def test_unbekannte_art_wird_abgewiesen():
    with pytest.raises(ValueError):
        seo_store.record_geo_run("2026-08-21", "x", "gemischt",
                                 zitiert=False, domains=[])


def test_grounding_zaehler_tag_und_monat():
    seo_store.grounding_increment("2026-08-20", 3)
    seo_store.grounding_increment("2026-08-21", 2)
    seo_store.grounding_increment("2026-08-21")
    assert seo_store.grounding_spent("2026-08-21") == (3, 6)
    # Monatswechsel beginnt bei null.
    assert seo_store.grounding_spent("2026-09-01") == (0, 0)


def test_ai_referrals_pro_tag_ueberschreibbar():
    seo_store.record_ai_referrals("2026-08-21", 2, ["chatgpt.com"])
    seo_store.record_ai_referrals("2026-08-21", 4, ["chatgpt.com", "perplexity.ai"])
    z = seo_store.ai_referrals_summary(days=7, heute=date(2026, 8, 21))
    assert z["gesamt"] == 4
    assert z["per_day"] == [{"day": "2026-08-21", "count": 4}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_store.py -q -k "geo or grounding or referrals or art"`
Expected: FAIL — `AttributeError: module 'app.core.seo_store' has no attribute 'record_geo_run'`

- [ ] **Step 3: Write minimal implementation**

An `backend/app/core/seo_store.py` anhängen:

```python
def record_geo_run(day: str, prompt_id: str, art: str,
                   zitiert: bool, domains: list[str]) -> None:
    """Eine GEO-Messung festhalten (ein Prompt, eine Engine-Antwort)."""
    if art not in (ART_DISCOVERY, ART_MARKE):
        raise ValueError(f"Unbekannte Prompt-Art: '{art}'")
    c = _conn()
    try:
        c.execute(
            "INSERT INTO geo_runs (day, prompt_id, art, zitiert, domains)"
            " VALUES (?,?,?,?,?)",
            (day, prompt_id, art, 1 if zitiert else 0,
             json.dumps(domains, ensure_ascii=False)),
        )
        c.commit()
    finally:
        c.close()


def geo_summary(days: int = 28, heute: Optional[date] = None) -> dict:
    """Zitatquoten, strikt getrennt nach Discovery und Marke."""
    c = _conn()
    try:
        rows = c.execute(
            "SELECT art, COUNT(*), COALESCE(SUM(zitiert),0) FROM geo_runs"
            " WHERE day >= ? GROUP BY art", (_seit(days, heute),)
        ).fetchall()
    finally:
        c.close()
    leer = {"laeufe": 0, "zitiert": 0, "quote": 0.0}
    out = {ART_DISCOVERY: dict(leer), ART_MARKE: dict(leer)}
    for art, n, z in rows:
        if art in out:
            out[art] = {"laeufe": n, "zitiert": z, "quote": round(z / n, 3)}
    return out


def grounding_increment(day: str, n: int = 1) -> None:
    """Verbrauch des Grounding-Kontingents hochzählen."""
    c = _conn()
    try:
        c.execute(
            "INSERT INTO grounding_usage (day, count) VALUES (?, ?)"
            " ON CONFLICT(day) DO UPDATE SET count = count + excluded.count",
            (day, n),
        )
        c.commit()
    finally:
        c.close()


def grounding_spent(day: str) -> tuple[int, int]:
    """Verbrauch (Tag, laufender Monat) — Grundlage des Kostenriegels."""
    monat = day[:7]
    c = _conn()
    try:
        tag = c.execute(
            "SELECT COALESCE(count,0) FROM grounding_usage WHERE day = ?", (day,)
        ).fetchone()
        mon = c.execute(
            "SELECT COALESCE(SUM(count),0) FROM grounding_usage WHERE day LIKE ?",
            (f"{monat}-%",),
        ).fetchone()
    finally:
        c.close()
    return (tag[0] if tag else 0, mon[0])


def record_ai_referrals(day: str, count: int, domains: list[str]) -> None:
    """Besuche über KI-Verweise für einen Tag festhalten (überschreibend)."""
    c = _conn()
    try:
        c.execute(
            "INSERT INTO ai_referrals (day, count, domains) VALUES (?,?,?)"
            " ON CONFLICT(day) DO UPDATE SET"
            " count=excluded.count, domains=excluded.domains",
            (day, int(count), json.dumps(domains, ensure_ascii=False)),
        )
        c.commit()
    finally:
        c.close()


def ai_referrals_summary(days: int = 28, heute: Optional[date] = None) -> dict:
    """KI-Verweis-Besuche der letzten ``days`` Tage."""
    c = _conn()
    try:
        rows = c.execute(
            "SELECT day, count FROM ai_referrals WHERE day >= ? ORDER BY day",
            (_seit(days, heute),),
        ).fetchall()
    finally:
        c.close()
    return {
        "gesamt": sum(n for _, n in rows),
        "per_day": [{"day": d, "count": n} for d, n in rows],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_store.py -q`
Expected: PASS (8 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/seo_store.py backend/tests/test_seo_store.py
git commit -m "feat(seo): GEO-Läufe, Grounding-Zähler und KI-Verweise im Speicher"
```

---

### Task 3: GEO-Promptbibliothek

**Files:**
- Create: `backend/app/services/geo_prompts.py`
- Test: `backend/tests/test_seo_geo.py`

**Interfaces:**
- Produces: `PROMPTS: list[dict]` — 28 Einträge `{"id": str, "art": "discovery"|"marke", "text": str}`; 20× discovery, 8× marke.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_seo_geo.py` anlegen:

```python
"""Tests für die SEO/GEO-Sammler."""
from datetime import date

import pytest

from app.core import seo_store
from app.services import seo_geo
from app.services.geo_prompts import PROMPTS


@pytest.fixture(autouse=True)
def saubere_umgebung(tmp_path, monkeypatch):
    """Frische DB, keine Zugangsdaten aus der echten Umgebung."""
    monkeypatch.setenv("SEO_DB_PATH", str(tmp_path / "seo.db"))
    monkeypatch.setenv("RATGEBER_DB_PATH", str(tmp_path / "ratgeber.db"))
    for var in ("GEMINI_API_KEY", "GSC_SERVICE_ACCOUNT_JSON", "GSC_SITE_URL",
                "GEO_BUDGET_DAY", "GEO_BUDGET_MONTH"):
        monkeypatch.delenv(var, raising=False)


def test_promptbibliothek_ist_vollstaendig_und_eindeutig():
    ids = [p["id"] for p in PROMPTS]
    assert len(ids) == 28
    assert len(set(ids)) == 28
    assert {p["art"] for p in PROMPTS} == {"discovery", "marke"}
    assert sum(1 for p in PROMPTS if p["art"] == "marke") == 8
    # Discovery-Prompts dürfen die Marke nicht nennen — sonst misst die
    # Discovery-Quote keine Entdeckung, sondern Markenbekanntheit.
    for p in PROMPTS:
        if p["art"] == "discovery":
            assert "novaerp" not in p["text"].lower(), p["id"]
        assert p["text"].strip().endswith("?")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_geo.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.geo_prompts'` (bzw. `seo_geo`; für den Import-Test genügt vorerst ein leeres `seo_geo`-Modul NICHT — Task 4 legt es an. Für diesen Task die Import-Zeile `from app.services import seo_geo` im Test zunächst weglassen? Nein: Task 3 legt `geo_prompts.py` an und eine minimale `seo_geo.py`-Hülle mit nur dem Modul-Docstring, damit der Test importierbar ist.)

- [ ] **Step 3: Write minimal implementation**

`backend/app/services/geo_prompts.py` anlegen:

```python
"""GEO-Promptbibliothek.

28 feste Prompts, getrennt nach ``discovery`` (ein Nutzer sucht eine Lösung,
ohne die Marke zu kennen) und ``marke`` (ein Nutzer fragt gezielt nach
NovaERP). Die Trennung ist Messmethodik: Marken-Prompts nennen die Domain
zwangsläufig — in einer Mischquote würden sie Fortschritt vortäuschen.

Die Liste ist bewusst stabil. Wer Prompts ändert, macht die Zeitreihe
unvergleichbar und vermerkt das im Änderungsprotokoll.
"""

PROMPTS: list[dict] = [
    # --- Discovery: Lösungssuche ohne Markenkenntnis (20) -------------------
    {"id": "erp-kmu-allgemein", "art": "discovery",
     "text": "Welches ERP-System eignet sich für ein kleines Unternehmen in Deutschland?"},
    {"id": "erp-lebensmittel", "art": "discovery",
     "text": "Welche ERP-Software gibt es für kleine Lebensmittelbetriebe mit Chargenrückverfolgung?"},
    {"id": "erp-microgreens", "art": "discovery",
     "text": "Welche Software hilft einer Microgreens-Farm bei Produktionsplanung und Vertrieb?"},
    {"id": "erp-handel", "art": "discovery",
     "text": "Welches Warenwirtschaftssystem passt zu einem kleinen Handelsunternehmen?"},
    {"id": "erp-produktion", "art": "discovery",
     "text": "Welche ERP-Lösung eignet sich für eine kleine Manufaktur oder Fertigung?"},
    {"id": "erp-dsgvo", "art": "discovery",
     "text": "Welches ERP-System hostet Daten ausschließlich in Deutschland und ist DSGVO-konform?"},
    {"id": "erp-kosten", "art": "discovery",
     "text": "Was kostet ein ERP-System für ein Start-up und welche günstigen Anbieter gibt es?"},
    {"id": "erp-cloud-kuendbar", "art": "discovery",
     "text": "Welche Cloud-ERP-Systeme für kleine Unternehmen sind monatlich kündbar?"},
    {"id": "erp-einfuehrung", "art": "discovery",
     "text": "Wie führe ich ein ERP-System in einem kleinen Betrieb ein und welche Anbieter erleichtern das?"},
    {"id": "erp-forecasting", "art": "discovery",
     "text": "Welche ERP-Systeme bieten KI-gestützte Absatzprognosen für kleine und mittlere Unternehmen?"},
    {"id": "erp-lager-produktion", "art": "discovery",
     "text": "Welche Software verbindet Lagerverwaltung und Produktionsplanung für kleine Betriebe?"},
    {"id": "erp-abo-modelle", "art": "discovery",
     "text": "Welche ERP-Anbieter unterstützen Abo-Modelle und wiederkehrende Lieferungen?"},
    {"id": "erp-multi-standort", "art": "discovery",
     "text": "Welches ERP-System eignet sich für kleine Unternehmen mit mehreren Standorten?"},
    {"id": "erp-sap-alternative", "art": "discovery",
     "text": "Welche Alternativen zu SAP Business One gibt es für kleine Unternehmen?"},
    {"id": "erp-lexware-alternative", "art": "discovery",
     "text": "Welche moderne Alternative zu Lexware gibt es für Produktion und Handel?"},
    {"id": "erp-rueckverfolgbarkeit", "art": "discovery",
     "text": "Welche Software bietet chargengenaue Rückverfolgbarkeit für Lebensmittelproduzenten?"},
    {"id": "erp-excel-abloesen", "art": "discovery",
     "text": "Wir planen Produktion und Bestellungen in Excel — welche Software löst das sinnvoll ab?"},
    {"id": "erp-vertical-farming", "art": "discovery",
     "text": "Welche Software gibt es für Vertical Farming und Indoor-Farmen?"},
    {"id": "erp-onpremise", "art": "discovery",
     "text": "Welche ERP-Systeme für kleine Unternehmen gibt es als On-Premise-Einmalkauf?"},
    {"id": "erp-schnellstart", "art": "discovery",
     "text": "Welches ERP-System ist ohne monatelanges Einführungsprojekt schnell einsatzbereit?"},
    # --- Marke: gezielte Fragen nach NovaERP (8) -----------------------------
    {"id": "marke-was-ist", "art": "marke",
     "text": "Was ist NovaERP?"},
    {"id": "marke-preise", "art": "marke",
     "text": "Was kostet NovaERP pro Monat?"},
    {"id": "marke-funktionen", "art": "marke",
     "text": "Welche Funktionen bietet NovaERP?"},
    {"id": "marke-hosting", "art": "marke",
     "text": "Wo hostet NovaERP die Daten und ist das DSGVO-konform?"},
    {"id": "marke-sprouddesk", "art": "marke",
     "text": "Was ist Sprouddesk von NovaERP?"},
    {"id": "marke-editionen", "art": "marke",
     "text": "Welche Branchen-Editionen bietet NovaERP an?"},
    {"id": "marke-erfahrungen", "art": "marke",
     "text": "Gibt es Erfahrungen oder Bewertungen zu NovaERP (novaerp.de)?"},
    {"id": "marke-vergleich", "art": "marke",
     "text": "Wie schneidet NovaERP im Vergleich zu anderen ERP-Systemen für KMU ab?"},
]
```

`backend/app/services/seo_geo.py` als Hülle anlegen (Task 4 füllt sie):

```python
"""Nächtliche SEO/GEO-Sammler.

Drei Sammler, jeder einzeln abschaltbar und ohne Zugangsdaten inaktiv:
Search Console (Service-Account), GEO-Messung (Gemini mit
Google-Search-Grounding) und die vorhandene First-Party-Zählung als
Nutzensignal. Kein Sammler wirft nach außen — ein Ausfall darf die
anderen nicht mitreißen.
"""
from __future__ import annotations
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_geo.py -q`
Expected: PASS (1 Test)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/geo_prompts.py backend/app/services/seo_geo.py backend/tests/test_seo_geo.py
git commit -m "feat(seo): GEO-Promptbibliothek, Discovery und Marke getrennt"
```

---

### Task 4: Kostenriegel und Gemini-GEO-Messung

**Files:**
- Modify: `backend/app/services/seo_geo.py`
- Test: `backend/tests/test_seo_geo.py`

**Interfaces:**
- Consumes: `seo_store.grounding_spent/grounding_increment/record_geo_run/log_change`, `geo_prompts.PROMPTS`, `app.core.site.root_domain`
- Produces: `measure_geo(tag: date, post=_post_json) -> dict`, `budget_status(heute=None) -> dict`, `_post_json(url, *, json_body=None, data=None, headers=None, timeout=30.0) -> dict`, `_grounding_domains(antwort: dict) -> list[str]`

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_seo_geo.py` anhängen:

```python
# --- GEO-Messung -------------------------------------------------------------


def _antwort_mit(domain):
    return {"candidates": [{"groundingMetadata": {"groundingChunks": [
        {"web": {"uri": f"https://{domain}/x", "title": domain}}]}}]}


def test_geo_ohne_key_ist_inaktiv():
    assert seo_geo.measure_geo(date(2026, 8, 21))["status"] == "inaktiv"


def test_geo_misst_zitate_und_zaehlt_verbrauch(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    aufrufe = []

    def fake_post(url, **kwargs):
        aufrufe.append(url)
        return _antwort_mit("novaerp.de" if len(aufrufe) == 1 else "sap.com")

    ergebnis = seo_geo.measure_geo(date(2026, 8, 21), post=fake_post)
    assert ergebnis == {"status": "ok", "gemessen": 28, "uebersprungen": 0}
    z = seo_store.geo_summary(days=1, heute=date(2026, 8, 21))
    assert z["discovery"]["laeufe"] + z["marke"]["laeufe"] == 28
    assert z["discovery"]["zitiert"] == 1  # nur der erste Prompt traf novaerp.de
    assert seo_store.grounding_spent("2026-08-21") == (28, 28)


def test_tagesriegel_stoppt_vor_dem_request(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("GEO_BUDGET_DAY", "5")
    aufrufe = []

    def fake_post(url, **kwargs):
        aufrufe.append(url)
        return _antwort_mit("sap.com")

    ergebnis = seo_geo.measure_geo(date(2026, 8, 21), post=fake_post)
    assert len(aufrufe) == 5
    assert ergebnis == {"status": "ok", "gemessen": 5, "uebersprungen": 23}
    assert any("Kostenriegel" in e["nachricht"]
               for e in seo_store.changelog_entries())


def test_monatsriegel_greift_ohne_einen_einzigen_request(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("GEO_BUDGET_MONTH", "10")
    seo_store.grounding_increment("2026-08-01", 10)

    def explodiert(url, **kwargs):
        raise AssertionError("Bei erschöpftem Monatsbudget darf kein Request rausgehen")

    ergebnis = seo_geo.measure_geo(date(2026, 8, 21), post=explodiert)
    assert ergebnis == {"status": "ok", "gemessen": 0, "uebersprungen": 28}


def test_budget_status_meldet_verbrauch_und_grenzen():
    seo_store.grounding_increment("2026-08-21", 7)
    status = seo_geo.budget_status(heute=date(2026, 8, 21))
    assert status == {"heute": 7, "monat": 7, "budget_tag": 50, "budget_monat": 4500}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_geo.py -q`
Expected: FAIL — `AttributeError: module 'app.services.seo_geo' has no attribute 'measure_geo'`

- [ ] **Step 3: Write minimal implementation**

An `backend/app/services/seo_geo.py` anhängen (unter dem Docstring/`from __future__`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_geo.py -q`
Expected: PASS (6 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/seo_geo.py backend/tests/test_seo_geo.py
git commit -m "feat(seo): GEO-Messung über Gemini-Grounding mit hartem Kostenriegel"
```

---

### Task 5: Search-Console-Sammler

**Files:**
- Modify: `backend/app/services/seo_geo.py`
- Test: `backend/tests/test_seo_geo.py`

**Interfaces:**
- Produces: `collect_gsc(tag: date, post=_post_json) -> dict`, `_gsc_zugang() -> Optional[dict]`, `_signierte_assertion(zugang: dict) -> str`
- Env: `GSC_SERVICE_ACCOUNT_JSON` (Inline-JSON oder Dateipfad), `GSC_SITE_URL` (z. B. `sc-domain:novaerp.de`)

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_seo_geo.py` anhängen:

```python
# --- Search Console ----------------------------------------------------------


def test_gsc_ohne_zugang_ist_inaktiv():
    assert seo_geo.collect_gsc(date(2026, 8, 18))["status"] == "inaktiv"


def test_gsc_zugang_aus_datei(tmp_path, monkeypatch):
    datei = tmp_path / "sa.json"
    datei.write_text('{"client_email": "a@b", "private_key": "k"}', encoding="utf-8")
    monkeypatch.setenv("GSC_SERVICE_ACCOUNT_JSON", str(datei))
    assert seo_geo._gsc_zugang()["client_email"] == "a@b"


def test_gsc_holt_token_und_speichert_zeilen(monkeypatch):
    monkeypatch.setenv("GSC_SITE_URL", "sc-domain:novaerp.de")
    monkeypatch.setenv(
        "GSC_SERVICE_ACCOUNT_JSON",
        '{"client_email": "seo@p.iam.gserviceaccount.com", "private_key": "test"}',
    )
    # Ein echter RS256-Key hat im Test nichts verloren — die Signatur wird ersetzt.
    monkeypatch.setattr(seo_geo, "_signierte_assertion", lambda zugang: "test-jwt")
    aufrufe = []

    def fake_post(url, json_body=None, data=None, headers=None, **kw):
        aufrufe.append(url)
        if "oauth2" in url:
            assert data["assertion"] == "test-jwt"
            return {"access_token": "zugriff"}
        assert headers["Authorization"] == "Bearer zugriff"
        assert "sc-domain%3Anovaerp.de" in url
        assert json_body["dimensions"] == ["page", "query"]
        return {"rows": [{"keys": ["https://novaerp.de/", "erp kmu"],
                          "clicks": 3, "impressions": 50, "position": 7.2}]}

    ergebnis = seo_geo.collect_gsc(date(2026, 8, 18), post=fake_post)
    assert ergebnis == {"status": "ok", "zeilen": 1}
    assert len(aufrufe) == 2
    z = seo_store.gsc_summary(days=28, heute=date(2026, 8, 21))
    assert z["totals"] == {"clicks": 3, "impressions": 50}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_geo.py -q -k gsc`
Expected: FAIL — `AttributeError: module 'app.services.seo_geo' has no attribute 'collect_gsc'`

- [ ] **Step 3: Write minimal implementation**

An `backend/app/services/seo_geo.py` anhängen:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_geo.py -q`
Expected: PASS (9 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/seo_geo.py backend/tests/test_seo_geo.py
git commit -m "feat(seo): Search-Console-Sammler über Service-Account ohne Google-SDK"
```

---

### Task 6: First-Party-Signal, Sammlerstatus und Nachtlauf

**Files:**
- Modify: `backend/app/services/seo_geo.py`
- Test: `backend/tests/test_seo_geo.py`

**Interfaces:**
- Consumes: `app.core.webstats.stats` (per Injektion ersetzbar), `seo_store.record_ai_referrals/log_change`
- Produces: `collect_firstparty(tag: date, stats_fn=None) -> dict`, `sammler_status() -> dict`, `nightly(heute: Optional[date] = None) -> dict`

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_seo_geo.py` anhängen:

```python
# --- First-Party-Signal und Nachtlauf ----------------------------------------


def test_firstparty_zaehlt_nur_ki_verweise():
    def fake_stats(days=1):
        return {"top_referrers": [
            {"ref": "https://chatgpt.com/", "views": 3},
            {"ref": "https://www.google.com/", "views": 50},
            {"ref": "https://perplexity.ai/search", "views": 2},
        ]}

    ergebnis = seo_geo.collect_firstparty(date(2026, 8, 21), stats_fn=fake_stats)
    assert ergebnis == {"status": "ok", "ki_besuche": 5}
    z = seo_store.ai_referrals_summary(days=7, heute=date(2026, 8, 21))
    assert z["gesamt"] == 5


def test_sammler_status_ohne_zugangsdaten():
    assert seo_geo.sammler_status() == {
        "gsc": False, "geo": False, "firstparty": True}


def test_nightly_isoliert_fehler_einzelner_sammler(monkeypatch):
    def kaputt(tag, post=None):
        raise RuntimeError("GSC explodiert")

    monkeypatch.setattr(seo_geo, "collect_gsc", kaputt)
    monkeypatch.setattr(seo_geo, "collect_firstparty",
                        lambda tag, stats_fn=None: {"status": "ok", "ki_besuche": 0})
    ergebnis = seo_geo.nightly(heute=date(2026, 8, 21))
    assert ergebnis["gsc"]["status"] == "fehler"
    assert ergebnis["geo"]["status"] == "inaktiv"  # kein Key in der Testumgebung
    assert ergebnis["firstparty"]["status"] == "ok"
    assert any(e["quelle"] == "nightly" for e in seo_store.changelog_entries())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_geo.py -q -k "firstparty or nightly or status"`
Expected: FAIL — `AttributeError: module 'app.services.seo_geo' has no attribute 'collect_firstparty'`

- [ ] **Step 3: Write minimal implementation**

An `backend/app/services/seo_geo.py` anhängen:

```python
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
```

Hinweis: `nightly` referenziert `collect_gsc`/`measure_geo`/`collect_firstparty` als Modul-Globals — genau deshalb greifen die `monkeypatch.setattr`-Ersetzungen im Test.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_geo.py -q`
Expected: PASS (12 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/seo_geo.py backend/tests/test_seo_geo.py
git commit -m "feat(seo): First-Party-KI-Signal und fehlerisolierter Nachtlauf"
```

---

### Task 7: Heuristische Vorschläge

**Files:**
- Modify: `backend/app/services/seo_geo.py`
- Test: `backend/tests/test_seo_geo.py`

**Interfaces:**
- Consumes: `seo_store.gsc_top_queries/geo_summary`, `app.core.ratgeber.published`
- Produces: `suggestions(heute: Optional[date] = None) -> list[dict]` — Einträge `{"art": "inhalt"|"snippet"|"geo", "text": str}`

Drei Regeln, bewusst deterministisch und ohne LLM:
1. **inhalt** — Anfrage mit ≥ 50 Impressionen, Position > 10, und kein Live-Ratgeber-Beitrag deckt alle Wörter der Anfrage ab → Beitrag anlegen.
2. **snippet** — Anfrage mit ≥ 50 Impressionen, Position ≤ 10, CTR < 1 % → Snippet/Meta-Description prüfen.
3. **geo** — ≥ 20 Discovery-Läufe und null Zitate → Discovery-Hinweis.

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_seo_geo.py` anhängen:

```python
# --- Vorschläge ---------------------------------------------------------------


def test_vorschlag_fuer_unbedientes_thema():
    seo_store.record_gsc_rows("2026-08-20", [
        {"page": "https://novaerp.de/", "query": "lager software kmu",
         "clicks": 0, "impressions": 120, "position": 18.0},
    ])
    hinweise = seo_geo.suggestions(heute=date(2026, 8, 21))
    assert any(h["art"] == "inhalt" and "lager software kmu" in h["text"]
               for h in hinweise)


def test_kein_vorschlag_wenn_ratgeber_das_thema_traegt():
    from app.core import ratgeber
    ratgeber.save(ratgeber.Article(
        slug="lager-software", title="Lagerverwaltung: die richtige Software für KMU",
        summary="Software-Auswahl fürs Lager.", body="Lager, Software, KMU."))
    ratgeber.publish("lager-software")
    seo_store.record_gsc_rows("2026-08-20", [
        {"page": "https://novaerp.de/", "query": "lager software kmu",
         "clicks": 0, "impressions": 120, "position": 18.0},
    ])
    hinweise = seo_geo.suggestions(heute=date(2026, 8, 21))
    assert not any(h["art"] == "inhalt" for h in hinweise)


def test_vorschlag_bei_schwacher_ctr():
    seo_store.record_gsc_rows("2026-08-20", [
        {"page": "https://novaerp.de/", "query": "erp preise",
         "clicks": 1, "impressions": 200, "position": 4.0},
    ])
    hinweise = seo_geo.suggestions(heute=date(2026, 8, 21))
    assert any(h["art"] == "snippet" and "erp preise" in h["text"]
               for h in hinweise)


def test_geo_null_quote_erzeugt_hinweis():
    for i in range(20):
        seo_store.record_geo_run("2026-08-21", "erp-kmu-allgemein", "discovery",
                                 zitiert=False, domains=["sap.com"])
    hinweise = seo_geo.suggestions(heute=date(2026, 8, 21))
    assert any(h["art"] == "geo" for h in hinweise)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_geo.py -q -k "vorschlag or null_quote or thema"`
Expected: FAIL — `AttributeError: module 'app.services.seo_geo' has no attribute 'suggestions'`

- [ ] **Step 3: Write minimal implementation**

An `backend/app/services/seo_geo.py` anhängen:

```python
def suggestions(heute: Optional[date] = None) -> list[dict]:
    """Heuristische Vorschläge aus den Messdaten.

    Nur Hinweise, kein automatischer Eingriff: die Marketing-Seiten liegen
    im Image, und über Ratgeber-Inhalte entscheidet die Redaktion. Bewusst
    ohne LLM — dieselben Daten ergeben immer dieselben Vorschläge.
    """
    hinweise: list[dict] = []
    try:
        from app.core import ratgeber
        live = ratgeber.published()
    except Exception:  # noqa: BLE001 — kaputter Redaktionsspeicher blockiert nicht
        live = []
    texte = " ".join(f"{a.title} {a.summary} {a.body}".lower() for a in live)

    for q in seo_store.gsc_top_queries(days=28, limit=50, heute=heute):
        anfrage = q["query"].strip().lower()
        if not anfrage or q["impressions"] < 50:
            continue
        ctr = q["clicks"] / q["impressions"]
        deckt_ab = all(wort in texte for wort in anfrage.split())
        if q["position"] > 10 and not deckt_ab:
            hinweise.append({
                "art": "inhalt",
                "text": (f"Ratgeber-Beitrag zu „{anfrage}“ anlegen — "
                         f"{q['impressions']} Impressionen auf Position "
                         f"{q['position']}, kein passender Beitrag."),
            })
        elif q["position"] <= 10 and ctr < 0.01:
            hinweise.append({
                "art": "snippet",
                "text": (f"Snippet für „{anfrage}“ prüfen — Position "
                         f"{q['position']}, aber CTR unter 1 %."),
            })

    geo = seo_store.geo_summary(days=28, heute=heute)
    if geo["discovery"]["laeufe"] >= 20 and geo["discovery"]["zitiert"] == 0:
        hinweise.append({
            "art": "geo",
            "text": ("Kein einziges KI-Zitat im Discovery-Set — "
                     "Ratgeber-Cluster ausbauen und zitierfähige Zahlen/Quellen "
                     "in die Beiträge bringen."),
        })
    return hinweise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_geo.py -q`
Expected: PASS (16 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/seo_geo.py backend/tests/test_seo_geo.py
git commit -m "feat(seo): deterministische Vorschläge aus GSC- und GEO-Daten"
```

---

### Task 8: Admin-API `/platform/seo`

**Files:**
- Create: `backend/app/api/v1/seo_dashboard.py`
- Modify: `backend/app/main.py` (Import + Router-Einbindung neben `ratgeber_admin`)
- Test: `backend/tests/test_seo_admin.py`

**Interfaces:**
- Consumes: `app.api.v1.platform._require_admin`, `seo_store.*`, `seo_geo.sammler_status/budget_status/suggestions/nightly`
- Produces: `router` mit Präfix `/platform/seo`: `GET /overview`, `POST /run`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_seo_admin.py` anlegen:

```python
"""Tests für das SEO/GEO-Admin-Dashboard-API."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

API = "/api/v1/platform/seo"
SCHLUESSEL = "test-admin-key-123"


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("SEO_DB_PATH", str(tmp_path / "seo.db"))
    monkeypatch.setenv("RATGEBER_DB_PATH", str(tmp_path / "ratgeber.db"))
    monkeypatch.setenv("PLATFORM_ADMIN_KEY", SCHLUESSEL)
    for var in ("GEMINI_API_KEY", "GSC_SERVICE_ACCOUNT_JSON", "GSC_SITE_URL",
                "GEO_BUDGET_DAY", "GEO_BUDGET_MONTH"):
        monkeypatch.delenv(var, raising=False)
    return TestClient(app)


def kopf():
    return {"X-Platform-Admin-Key": SCHLUESSEL}


def test_ohne_key_kein_zugriff(web):
    assert web.get(f"{API}/overview").status_code == 401
    assert web.post(f"{API}/run").status_code == 401


def test_overview_liefert_alle_bausteine(web):
    r = web.get(f"{API}/overview", headers=kopf())
    assert r.status_code == 200
    d = r.json()
    assert set(d) >= {"sammler", "gsc", "geo", "grounding",
                      "ai_referrals", "vorschlaege", "protokoll"}
    assert d["sammler"] == {"gsc": False, "geo": False, "firstparty": True}
    assert d["grounding"]["budget_tag"] == 50
    assert d["grounding"]["budget_monat"] == 4500


def test_run_startet_den_nachtlauf(web, monkeypatch):
    from app.services import seo_geo
    monkeypatch.setattr(
        seo_geo, "collect_firstparty",
        lambda tag, stats_fn=None: {"status": "ok", "ki_besuche": 0})
    r = web.post(f"{API}/run", headers=kopf())
    assert r.status_code == 200
    d = r.json()
    assert d["gsc"]["status"] == "inaktiv"
    assert d["geo"]["status"] == "inaktiv"
    assert d["firstparty"]["status"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_admin.py -q`
Expected: FAIL — 404 auf beiden Routen, das Modul existiert nicht

- [ ] **Step 3: Write minimal implementation**

`backend/app/api/v1/seo_dashboard.py` anlegen:

```python
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
```

In `backend/app/main.py` den Import ergänzen (an der `ratgeber_admin`-Zeile):

```python
from app.api.v1 import ratgeber as ratgeber_admin
from app.api.v1 import seo_dashboard
```

und nach dem `ratgeber_admin`-Include einfügen:

```python
# SEO/GEO-Dashboard, ebenfalls über den Platform-Admin-Key
app.include_router(
    seo_dashboard.router,
    prefix="/api/v1",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_admin.py -q`
Expected: PASS (3 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/seo_dashboard.py backend/app/main.py backend/tests/test_seo_admin.py
git commit -m "feat(seo): Dashboard-API hinter dem Platform-Admin-Key"
```

---

### Task 9: Scheduler-Job `seo-geo-nightly`

**Files:**
- Modify: `backend/app/services/scheduler_service.py`

**Interfaces:**
- Consumes: `seo_geo.nightly`
- Env: `SEO_GEO_ENABLED` (Default `true`; die Sammler sind ohne Zugangsdaten ohnehin No-Ops)

- [ ] **Step 1: Job registrieren**

In `backend/app/services/scheduler_service.py` direkt nach dem `demo-reset`-Block einfügen:

```python
    # SEO/GEO-Nachtlauf: Search Console, GEO-Messung, First-Party-Signal.
    # NICHT per-Tenant gewrappt — Marketing-Domain, kein Mandantenbezug.
    # Ohne Zugangsdaten laufen die Sammler als No-Op durch.
    if os.getenv("SEO_GEO_ENABLED", "true").lower() in ("1", "true", "yes"):
        from app.services.seo_geo import nightly as seo_geo_nightly
        sched.add_job(
            seo_geo_nightly,
            trigger=CronTrigger(hour=4, minute=15),
            id="seo-geo-nightly",
            name="seo-geo-nightly",
            coalesce=True,
            max_instances=1,
            replace_existing=True,
        )
```

(04:15 liegt nach `expired-cleanup` 03:00 und `demo-reset` 03:30, vor `daily-subscriptions` 05:00.)

- [ ] **Step 2: Verifizieren**

Run: `cd backend && python -c "import ast; ast.parse(open('app/services/scheduler_service.py').read()); print('syntaktisch ok')" && grep -c "seo-geo-nightly" app/services/scheduler_service.py`
Expected: `syntaktisch ok` und `2`

Hinweis: `start_scheduler()` ist lokal nicht lauffähig (importiert Forecast-Tasks → `pandas` fehlt in der lokalen Umgebung). Die Job-Registrierung wird in Produktion über den bestehenden Scheduler-Debug-Endpoint (`app/api/v1/admin.py`) sichtbar.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/scheduler_service.py
git commit -m "feat(seo): nächtlicher Scheduler-Job seo-geo-nightly"
```

---

### Task 10: Dashboard-Panel im Platform-Admin + Gesamtlauf

**Files:**
- Modify: `backend/static_admin/index.html`
- Test: Gesamtlauf aller Backend-Tests, manuelle Sichtprüfung des Panels

- [ ] **Step 1: Abschnitt in die Seite einsetzen**

Nach dem `<!-- Ratgeber -->`-Block (vor `</div>` des `.wrap`-Inhalts) einfügen:

```html
      <!-- SEO / GEO -->
      <div class="section">
        <h2>SEO &amp; GEO</h2>
        <div class="grid" id="seoStats" style="margin-bottom:1rem"></div>
        <div id="seoVorschlaege"></div>
        <div id="seoProtokoll" class="muted" style="margin-top:1rem;font-family:ui-monospace,monospace;font-size:.78rem;line-height:1.9"></div>
        <div style="margin-top:1rem">
          <button class="btn btn-ghost" onclick="seoLaufStarten()">Nightly jetzt ausführen</button>
        </div>
      </div>
```

- [ ] **Step 2: JavaScript ergänzen**

Vor `// Auto-login if key present` einfügen:

```javascript
    async function ladeSeo(){
      try {
        const res = await fetch(API + '/seo/overview', { headers: headers() });
        if(!res.ok) return;
        const d = await res.json();
        const s = d.sammler || {};
        const badge = on => on
          ? '<span style="color:var(--ok)">aktiv</span>'
          : '<span style="color:var(--ink-3)">inaktiv</span>';
        const disc = (d.geo && d.geo.discovery) || {laeufe:0, quote:0};
        const marke = (d.geo && d.geo.marke) || {laeufe:0, quote:0};
        const g = d.grounding || {};
        const gsc = (d.gsc && d.gsc.totals) || {clicks:0, impressions:0};
        document.getElementById('seoStats').innerHTML = `
          <div class="stat"><div class="num">${gsc.clicks}</div><div class="lbl">GSC-Klicks 28 T · ${badge(s.gsc)}</div></div>
          <div class="stat"><div class="num">${Math.round((disc.quote||0)*100)}%</div><div class="lbl">GEO Discovery (${disc.laeufe||0} Läufe) · ${badge(s.geo)}</div></div>
          <div class="stat"><div class="num">${Math.round((marke.quote||0)*100)}%</div><div class="lbl">GEO Marke (${marke.laeufe||0} Läufe)</div></div>
          <div class="stat"><div class="num">${g.monat ?? 0}/${g.budget_monat ?? 0}</div><div class="lbl">Grounding-Budget Monat</div></div>
          <div class="stat"><div class="num">${(d.ai_referrals && d.ai_referrals.gesamt) || 0}</div><div class="lbl">Besuche über KI-Verweise 28 T</div></div>`;
        const v = d.vorschlaege || [];
        document.getElementById('seoVorschlaege').innerHTML = v.length
          ? '<ul style="margin:.5rem 0;padding-left:1.2rem">' +
            v.map(x => `<li style="margin:.35rem 0">${esc(x.text)}</li>`).join('') + '</ul>'
          : '<div class="empty">Keine Vorschläge — Datenlage zu dünn oder alles im grünen Bereich.</div>';
        const p = d.protokoll || [];
        document.getElementById('seoProtokoll').innerHTML =
          p.slice(0, 8).map(e => `${esc(e.ts)} · ${esc(e.quelle)} · ${esc(e.nachricht)}`).join('<br>');
      } catch(e){ /* Panel ist Zusatz — Fehler nicht in den Login-Flow tragen */ }
    }

    async function seoLaufStarten(){
      toast('Nightly gestartet…');
      const res = await fetch(API + '/seo/run', { method:'POST', headers: headers() });
      if(res.ok){ toast('Nightly abgeschlossen', 'ok'); ladeSeo(); }
      else { toast('Nightly fehlgeschlagen', 'err'); }
    }
```

und in `loadAll()` nach `await ladeBeitraege();` ergänzen:

```javascript
        await ladeSeo();
```

- [ ] **Step 3: Gesamtlauf**

Run: `cd backend && python -m pytest tests/test_seo_store.py tests/test_seo_geo.py tests/test_seo_admin.py tests/test_ratgeber_store.py tests/test_ratgeber_render.py tests/test_ratgeber_public.py tests/test_ratgeber_admin.py tests/test_seo_public.py -q`
Expected: PASS (121 Tests, 1 übersprungen)

Run: `cd backend && python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py`
Expected: keine neuen Fehler gegenüber der Baseline (15 vorbestehende Fehler, 1 Fehlerfall)

- [ ] **Step 4: Commit**

```bash
git add backend/static_admin/index.html
git commit -m "feat(seo): SEO/GEO-Panel im Platform-Admin"
```

---

## Abnahme

| Prüfung | Erwartung |
|---|---|
| `GET /api/v1/platform/seo/overview` ohne Key | 401 |
| `GET …/overview` mit Key, ohne Zugangsdaten | 200, `sammler` = gsc/geo inaktiv, firstparty aktiv, Budgets 50/4500 |
| `POST …/run` ohne Zugangsdaten | 200, gsc+geo `inaktiv`, firstparty `ok`, Protokolleintrag `nightly` |
| Grounding-Budget Tag erschöpft | kein weiterer Gemini-Request, Protokolleintrag „Kostenriegel" |
| Grounding-Budget Monat erschöpft | null Requests |
| GEO-Quote | getrennt `discovery`/`marke`, nie gemischt |
| GSC-Import zweimal derselbe Tag | überschreibt statt doppelt |
| `seo.db` | liegt im `./data`-Volume, nicht im Image |
| Scheduler | Job `seo-geo-nightly` 04:15, per `SEO_GEO_ENABLED=false` abschaltbar |

Außerhalb des Codes (unverändert offen, siehe Spec): GSC-Property per DNS-TXT verifizieren + Sitemap einreichen, Service-Account anlegen und in der GSC freigeben, Google-Cloud-Projekt mit Billing + Gemini-Key, Backup des `./data`-Volumes.
