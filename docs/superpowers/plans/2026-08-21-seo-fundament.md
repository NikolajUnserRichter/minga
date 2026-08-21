# SEO-Fundament novaerp.de — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Marketing-Seite novaerp.de wird technisch indexierbar und für KI-Crawler zitierfähig — robots.txt, sitemap.xml und llms.txt existieren, jede Seite hat genau eine URL, und unbekannte Pfade antworten mit einem echten 404.

**Architecture:** Die drei SEO-Dateien werden von FastAPI erzeugt statt statisch ausgeliefert, weil robots.txt je Host unterschiedlich antworten muss und die Sitemap später Datenbank-Inhalte enthält. Die Host-Rollen-Erkennung (Apex, Admin, Tenant) und die Docroot-Auflösung ziehen aus `main.py` in ein eigenes Modul, damit Routen und Catch-All dieselbe Definition teilen. URL-Kanonisierung läuft als Middleware, das 404-Verhalten wird im bestehenden Catch-All repariert.

**Tech Stack:** Python 3.11, FastAPI, Starlette-Middleware, pytest + `fastapi.testclient.TestClient`, statisches HTML in `backend/static_marketing/`.

**Spec:** `docs/superpowers/specs/2026-08-21-seo-geo-novaerp-design.md`

## Global Constraints

- Zieldomain und Schema-IDs immer `https://novaerp.de` — nie eine Tenant- oder Staging-Domain.
- Root-Domain kommt aus der Env `SPROUDDESK_ROOT_DOMAIN`, Default `novaerp.de`. Nie hart verdrahten.
- Nur Apex (`novaerp.de`, `www.novaerp.de`) liefert Marketing-Inhalte. `admin.<root>` und alle Tenant-Subdomains dürfen weder in robots.txt freigegeben noch in der Sitemap genannt werden.
- Der Subdomain-Zweig des Catch-Alls muss weiterhin `index.html` mit Status 200 liefern — die React-SPA braucht den Fallback für Client-Routing. Nur der Apex-Zweig bekommt echte 404er.
- Keine neuen Abhängigkeiten in `backend/requirements.txt`.
- Tests laufen aus `backend/`: `cd backend && python -m pytest tests/test_seo_public.py -v`.
- Deutschsprachige Docstrings und Kommentare, wie im übrigen Backend.
- Erfinde keine Fakten für Markup. `sameAs` bleibt weg, solange keine echten Profile bekannt sind.

---

### Task 1: Host-Rollen und Docroot in ein Modul ziehen

Heute steht die Host-Logik als private Funktionen mitten in der 900 Zeilen langen `main.py`. Die neuen SEO-Routen brauchen dieselbe Logik; ein Import aus `main.py` wäre zirkulär. Also zuerst herausziehen.

**Files:**
- Create: `backend/app/core/site.py`
- Modify: `backend/app/main.py:194-219` (Docroot-Auflösung und Host-Helfer)
- Test: `backend/tests/test_seo_public.py`

**Interfaces:**
- Consumes: nichts
- Produces: `app.core.site.root_domain() -> str`, `hostname(request: Request) -> str`, `is_apex_host(host: str) -> bool`, `is_www_host(host: str) -> bool`, `is_admin_host(host: str) -> bool`, `canonical_origin() -> str`, `marketing_dir() -> Path`

- [ ] **Step 1: Write the failing test**

Neue Datei `backend/tests/test_seo_public.py`:

```python
"""Tests für das SEO-Fundament der Marketing-Seite (Apex novaerp.de)."""
from pathlib import Path

from app.core import site


def test_apex_erkennt_root_und_www():
    assert site.is_apex_host("novaerp.de")
    assert site.is_apex_host("www.novaerp.de")


def test_apex_erkennt_admin_und_tenants_nicht():
    assert not site.is_apex_host("admin.novaerp.de")
    assert not site.is_apex_host("demo.novaerp.de")
    assert site.is_admin_host("admin.novaerp.de")
    assert site.is_www_host("www.novaerp.de")
    assert not site.is_www_host("novaerp.de")


def test_canonical_origin_zeigt_auf_die_zieldomain():
    assert site.canonical_origin() == "https://novaerp.de"


def test_marketing_dir_enthaelt_die_startseite():
    assert (site.marketing_dir() / "index.html").is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'app.core.site'`

- [ ] **Step 3: Write minimal implementation**

Neue Datei `backend/app/core/site.py`:

```python
"""Auslieferungs-Rollen der Marketing-Site.

Ein einziger Prozess bedient drei Rollen, unterschieden allein am
Host-Header:

  * ``novaerp.de`` und ``www.novaerp.de`` → öffentliche Marketing-Seite
  * ``admin.novaerp.de``                  → Platform-Admin-UI
  * ``<tenant>.novaerp.de``               → React-SPA (ERP)

Die Erkennung liegt hier statt in ``main.py``, weil sowohl der Catch-All
als auch die SEO-Routen sie brauchen und ein Import aus ``main.py``
zirkulär wäre.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import Request


def root_domain() -> str:
    """Basisdomain der Plattform, per Env überschreibbar."""
    return os.environ.get("SPROUDDESK_ROOT_DOMAIN", "novaerp.de").lower()


def hostname(request: Request) -> str:
    """Host-Header ohne Port, kleingeschrieben. Leerer String, wenn keiner da ist."""
    return (request.headers.get("host") or "").split(":")[0].lower()


def is_apex_host(host: str) -> bool:
    """Apex einschließlich www.

    www zählt bewusst als Apex, damit es nicht auf die ERP-SPA durchfällt.
    Umgeleitet wird es an anderer Stelle.
    """
    root = root_domain()
    return host == root or host == f"www.{root}"


def is_www_host(host: str) -> bool:
    return host == f"www.{root_domain()}"


def is_admin_host(host: str) -> bool:
    return host == f"admin.{root_domain()}"


def canonical_origin() -> str:
    """Origin, auf den alle kanonischen URLs und Schema-IDs zeigen."""
    return f"https://{root_domain()}"


def marketing_dir() -> Path:
    """Docroot der Marketing-Seite — im Container gemountet, lokal im Repo."""
    packaged = Path("/app/static_marketing")
    if packaged.exists():
        return packaged
    return Path(__file__).resolve().parents[2] / "static_marketing"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v`
Expected: PASS (4 Tests)

- [ ] **Step 5: main.py auf das Modul umstellen**

In `backend/app/main.py` den Import ergänzen (bei den übrigen `app.core`-Importen):

```python
from app.core.site import (
    canonical_origin, hostname, is_admin_host, is_apex_host, is_www_host,
    marketing_dir, root_domain,
)
```

Den Block der Docroot-Auflösung und der Host-Helfer ersetzen. Vorher:

```python
# Marketing-Seite (apex novaerp.de) — separate Static-Dir, kein Auth nötig.
marketing_dist = Path("/app/static_marketing")
if not marketing_dist.exists():
    marketing_dist = Path(__file__).parent.parent / "static_marketing"
```

Nachher:

```python
# Marketing-Seite (apex novaerp.de) — separate Static-Dir, kein Auth nötig.
marketing_dist = marketing_dir()
```

Und die drei Host-Helfer auf das Modul delegieren, damit es nur noch eine
Definition gibt:

```python
def _root_domain() -> str:
    return root_domain()


def _is_apex_request(request: Request) -> bool:
    """Apex = novaerp.de oder www.novaerp.de."""
    return is_apex_host(hostname(request))


def _is_admin_request(request: Request) -> bool:
    """admin.novaerp.de → Platform-Admin-UI. Die UI selbst ist statisch;
    alle Aktionen sind durch den X-Platform-Admin-Key geschützt."""
    return is_admin_host(hostname(request))
```

- [ ] **Step 6: Regression prüfen**

Run: `cd backend && python -m pytest tests/test_seo_public.py tests/test_api.py -v`
Expected: PASS, keine neuen Fehler gegenüber dem Stand vor der Änderung

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/site.py backend/app/main.py backend/tests/test_seo_public.py
git commit -m "refactor(seo): Host-Rollen und Docroot in app.core.site ziehen, www zaehlt als Apex"
```

---

### Task 2: robots.txt

**Files:**
- Create: `backend/app/api/seo_public.py`
- Modify: `backend/app/main.py` (Router einbinden, vor dem Catch-All)
- Test: `backend/tests/test_seo_public.py`

**Interfaces:**
- Consumes: `app.core.site.hostname`, `is_apex_host`, `canonical_origin`
- Produces: `app.api.seo_public.router` (APIRouter ohne Prefix), `AI_CRAWLERS: tuple[str, ...]`

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_seo_public.py` anhängen:

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app

APEX = {"Host": "novaerp.de"}
TENANT = {"Host": "dev.novaerp.de"}


@pytest.fixture(scope="module")
def web():
    """Client für die öffentlichen Seiten — braucht keine DB-Fixtures."""
    return TestClient(app)


def test_robots_gibt_apex_frei_und_nennt_die_sitemap(web):
    r = web.get("/robots.txt", headers=APEX)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "User-agent: *" in r.text
    assert "Sitemap: https://novaerp.de/sitemap.xml" in r.text


def test_robots_erlaubt_die_ki_crawler(web):
    r = web.get("/robots.txt", headers=APEX)
    for agent in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"):
        assert f"User-agent: {agent}" in r.text


def test_robots_haelt_api_und_statistik_aus_dem_index(web):
    r = web.get("/robots.txt", headers=APEX)
    assert "Disallow: /api/" in r.text
    assert "Disallow: /stats.html" in r.text


def test_robots_sperrt_tenant_subdomains_komplett(web):
    r = web.get("/robots.txt", headers=TENANT)
    assert r.status_code == 200
    assert r.text.strip() == "User-agent: *\nDisallow: /"
    assert "Sitemap:" not in r.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v -k robots`
Expected: FAIL — die Route liefert HTML aus dem Catch-All, `content-type` ist `text/html`

- [ ] **Step 3: Write minimal implementation**

Neue Datei `backend/app/api/seo_public.py`:

```python
"""Öffentliche SEO-Dateien der Marketing-Seite.

robots.txt, sitemap.xml und llms.txt werden erzeugt statt als Datei
ausgeliefert. Zwei Gründe: robots.txt muss je Host unterschiedlich
antworten (Apex frei, Tenant-Instanzen gesperrt), und die Sitemap enthält
ab der Content-Engine die in der Datenbank gepflegten Ratgeber-Beiträge.

Der Router muss in ``main.py`` VOR dem Catch-All ``/{full_path:path}``
eingebunden werden — FastAPI matcht in Deklarationsreihenfolge.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.core.site import canonical_origin, hostname, is_apex_host

router = APIRouter(include_in_schema=False)

# Crawler generativer Engines. Ohne deren Zugang gibt es keine Zitate in
# KI-Antworten — die gesamte GEO-Messung hinge sonst in der Luft.
AI_CRAWLERS = (
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-Web",
    "anthropic-ai",
    "PerplexityBot",
    "Perplexity-User",
    "Google-Extended",
    "CCBot",
    "Applebot-Extended",
)

# Pfade, die niemand indexieren soll: die API und die interne Reichweiten-
# auswertung.
_DISALLOWED = ("/api/", "/stats.html", "/stats")


def _agent_group(agent: str) -> str:
    """Eine robots.txt-Gruppe.

    Die Disallow-Zeilen werden je Gruppe wiederholt, weil ein Crawler mit
    eigener Gruppe die Regeln aus ``User-agent: *`` nicht mehr sieht.
    """
    lines = [f"User-agent: {agent}", "Allow: /"]
    lines.extend(f"Disallow: {path}" for path in _DISALLOWED)
    return "\n".join(lines)


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt(request: Request) -> PlainTextResponse:
    if not is_apex_host(hostname(request)):
        # Admin-UI und Tenant-Instanzen gehören in keinen Index.
        return PlainTextResponse("User-agent: *\nDisallow: /\n")

    groups = [_agent_group("*")]
    groups.extend(_agent_group(agent) for agent in AI_CRAWLERS)
    body = "\n\n".join(groups)
    body += f"\n\nSitemap: {canonical_origin()}/sitemap.xml\n"
    return PlainTextResponse(body)
```

- [ ] **Step 4: Router einbinden**

In `backend/app/main.py` den Import erweitern:

```python
from app.api import seo_public
```

Und direkt vor dem ersten `app.include_router(...)`-Aufruf einbinden — auf
jeden Fall oberhalb der Zeile, in der `@app.get("/{full_path:path}")`
deklariert wird:

```python
# Öffentliche SEO-Dateien (robots.txt, sitemap.xml, llms.txt).
# MUSS vor dem Catch-All stehen, sonst schluckt der die Pfade.
app.include_router(seo_public.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v`
Expected: PASS (8 Tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/seo_public.py backend/app/main.py backend/tests/test_seo_public.py
git commit -m "feat(seo): robots.txt je Host ausliefern, KI-Crawler freigeben"
```

---

### Task 3: sitemap.xml

**Files:**
- Modify: `backend/app/api/seo_public.py`
- Test: `backend/tests/test_seo_public.py`

**Interfaces:**
- Consumes: `app.core.site.marketing_dir`, `canonical_origin`, `hostname`, `is_apex_host`
- Produces: `SitemapArticle` (frozen dataclass mit `slug: str`, `title: str`, `summary: str`, `lastmod: date | None`), `content_articles() -> list[SitemapArticle]`, `STATIC_PAGES: tuple[tuple[str, str, str], ...]`

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_seo_public.py` anhängen:

```python
import re


def test_sitemap_listet_alle_statischen_seiten(web):
    r = web.get("/sitemap.xml", headers=APEX)
    assert r.status_code == 200
    assert "xml" in r.headers["content-type"]
    assert r.text.startswith('<?xml version="1.0" encoding="UTF-8"?>')

    locs = re.findall(r"<loc>(.*?)</loc>", r.text)
    assert locs == [
        "https://novaerp.de/",
        "https://novaerp.de/impressum",
        "https://novaerp.de/datenschutz",
        "https://novaerp.de/agb",
    ]


def test_sitemap_nennt_weder_statistik_noch_subdomains(web):
    r = web.get("/sitemap.xml", headers=APEX)
    assert "stats" not in r.text
    assert "dev.novaerp.de" not in r.text


def test_sitemap_gibt_es_nur_auf_dem_apex(web):
    r = web.get("/sitemap.xml", headers=TENANT)
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v -k sitemap`
Expected: FAIL — `ElementTree.ParseError`, weil der Catch-All HTML liefert

- [ ] **Step 3: Write minimal implementation**

In `backend/app/api/seo_public.py` ergänzen — Importe oben erweitern:

```python
from dataclasses import dataclass
from datetime import date
from typing import Optional
from xml.sax.saxutils import escape

from fastapi.responses import Response

from app.core.site import marketing_dir
```

Und den Sitemap-Teil anhängen:

```python
# Statische Seiten der Marketing-Site: Pfad, changefreq, priority.
# Bewusst ohne /stats.html — die interne Auswertung gehört nicht in den Index.
STATIC_PAGES: tuple[tuple[str, str, str], ...] = (
    ("/", "weekly", "1.0"),
    ("/impressum", "yearly", "0.3"),
    ("/datenschutz", "yearly", "0.3"),
    ("/agb", "yearly", "0.3"),
)


@dataclass(frozen=True)
class SitemapArticle:
    """Ein Ratgeber-Beitrag, so wie Sitemap und llms.txt ihn brauchen."""

    slug: str
    title: str
    summary: str
    lastmod: Optional[date]


def content_articles() -> list[SitemapArticle]:
    """Veröffentlichte Ratgeber-Beiträge.

    Das Fundament kennt noch keine Beiträge. Die Content-Engine ersetzt
    diesen Rumpf, ohne dass Sitemap oder llms.txt angefasst werden müssen.
    """
    return []


def _page_lastmod(path: str) -> Optional[date]:
    """Änderungsdatum aus der Datei im Docroot, sofern lesbar."""
    name = "index.html" if path == "/" else f"{path.lstrip('/')}.html"
    try:
        return date.fromtimestamp((marketing_dir() / name).stat().st_mtime)
    except OSError:
        return None


def _url_entry(loc: str, lastmod: Optional[date], changefreq: str, priority: str) -> list[str]:
    parts = ["  <url>", f"    <loc>{escape(loc)}</loc>"]
    if lastmod is not None:
        parts.append(f"    <lastmod>{lastmod.isoformat()}</lastmod>")
    parts.append(f"    <changefreq>{changefreq}</changefreq>")
    parts.append(f"    <priority>{priority}</priority>")
    parts.append("  </url>")
    return parts


@router.get("/sitemap.xml")
async def sitemap_xml(request: Request) -> Response:
    if not is_apex_host(hostname(request)):
        raise HTTPException(status_code=404, detail="Not Found")

    origin = canonical_origin()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, changefreq, priority in STATIC_PAGES:
        lines.extend(_url_entry(f"{origin}{path}", _page_lastmod(path), changefreq, priority))
    for article in content_articles():
        lines.extend(
            _url_entry(f"{origin}/ratgeber/{article.slug}", article.lastmod, "monthly", "0.6")
        )
    lines.append("</urlset>")

    return Response("\n".join(lines) + "\n", media_type="application/xml")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v`
Expected: PASS (11 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/seo_public.py backend/tests/test_seo_public.py
git commit -m "feat(seo): sitemap.xml dynamisch erzeugen, Ratgeber-Haken vorbereitet"
```

---

### Task 4: llms.txt

Die Datei ist die kuratierte Kurzfassung der Site für KI-Systeme. Sie ist nur dann etwas wert, wenn die Fakten stimmen — Inhalte deshalb aus `backend/static_marketing/index.html` ablesen, nicht erfinden.

**Files:**
- Modify: `backend/app/api/seo_public.py`
- Test: `backend/tests/test_seo_public.py`

**Interfaces:**
- Consumes: `content_articles()`, `canonical_origin()`, `hostname()`, `is_apex_host()`
- Produces: Route `GET /llms.txt`

Alle Angaben unten stammen aus `static_marketing/index.html` (Meta-Description, Preis-Offers im JSON-LD, FAQ-Block). Nichts davon ist hinzugedichtet — wer den Text ändert, gleicht ihn wieder mit der Startseite ab.

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_seo_public.py` anhängen:

```python
def test_llms_txt_liefert_markdown_mit_kernangaben(web):
    r = web.get("/llms.txt", headers=APEX)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert r.text.startswith("# NovaERP")
    # Verweise müssen absolut auf die Zieldomain zeigen, sonst laufen sie
    # in KI-Antworten ins Leere.
    assert "https://novaerp.de/impressum" in r.text
    assert "https://novaerp.de/datenschutz" in r.text


def test_llms_txt_nennt_die_belegbaren_eckdaten(web):
    r = web.get("/llms.txt", headers=APEX)
    for fakt in ("Falkenstein", "99 €", "299 €", "499 €", "monatlich kündbar"):
        assert fakt in r.text


def test_llms_txt_gibt_es_nur_auf_dem_apex(web):
    r = web.get("/llms.txt", headers=TENANT)
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v -k llms`
Expected: FAIL — `content-type` ist `text/html`, der Text beginnt mit `<!DOCTYPE html>`

- [ ] **Step 3: Write minimal implementation**

In `backend/app/api/seo_public.py` anhängen:

```python
# Kurzprofil der Site. Jede Angabe ist auf der Startseite belegt
# (Meta-Description, Preis-Offers und FAQ im JSON-LD). Wer hier etwas
# ändert, gleicht es dort wieder ab — eine llms.txt mit falschen Preisen
# streut Fehlinformation direkt in KI-Antworten.
_LLMS_INTRO = """\
> NovaERP ist eine ERP-Plattform für kleine und mittlere Unternehmen mit \
branchenfertigen Editionen für Lebensmittel, Handel und Produktion.

NovaERP bündelt Produktion, Lager, Vertrieb und Buchhaltung in einem System. \
Statt eines Baukastens gibt es drei fertige Branchen-Editionen: Sprouddesk \
für Farmen und Lebensmittelbetriebe, Tradesk für den Handel, Craftdesk für \
Fertigung und Manufaktur. Zum Funktionsumfang gehören Produktions- und \
Auftragsplanung, chargengenaue Rückverfolgbarkeit, KI-Bedarfsprognosen, \
Lagerverwaltung, Kundenverwaltung und BI-Dashboards.

Betrieb ausschließlich in Deutschland, im Hetzner-Rechenzentrum Falkenstein \
(ISO 27001). Jeder Kunde erhält eine eigene, isolierte Datenbank; ein \
AV-Vertrag nach Art. 28 DSGVO ist enthalten. Ein Workspace mit eigener \
Subdomain steht in rund fünf Minuten, Stammdaten lassen sich per Excel \
importieren.

Preise pro Monat: Starter 99 € (ein Standort, bis 3 Nutzer), Professional \
299 € (bis 10 Nutzer, KI-Forecasting, BI-Dashboards), Business 499 € \
(Multi-Standort, unbegrenzte Nutzer, API-Zugang). Daneben gibt es eine \
On-Premise-Variante als Einmalkauf. Verträge sind monatlich kündbar, \
alternativ mit Rabatt auf zwölf Monate; Daten sind jederzeit exportierbar."""


@router.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt(request: Request) -> PlainTextResponse:
    """Kuratierte Kurzfassung der Site nach llmstxt.org.

    Zweck ist nicht Vollständigkeit, sondern dass ein Sprachmodell in
    wenigen Zeilen erfassen kann, was NovaERP ist und wohin es für Details
    greifen muss.
    """
    if not is_apex_host(hostname(request)):
        raise HTTPException(status_code=404, detail="Not Found")

    origin = canonical_origin()
    lines = [
        "# NovaERP",
        "",
        _LLMS_INTRO,
        "",
        "## Seiten",
        "",
        f"- [Startseite]({origin}/): Funktionsumfang, Branchen-Editionen, "
        "Preise und häufige Fragen",
        f"- [Impressum]({origin}/impressum): Anbieterkennzeichnung",
        f"- [Datenschutz]({origin}/datenschutz): Datenschutzerklärung",
        f"- [AGB]({origin}/agb): Allgemeine Geschäftsbedingungen",
    ]

    articles = content_articles()
    if articles:
        lines += ["", "## Ratgeber", ""]
        lines += [
            f"- [{a.title}]({origin}/ratgeber/{a.slug}): {a.summary}" for a in articles
        ]

    return PlainTextResponse("\n".join(lines) + "\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v`
Expected: PASS (14 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/seo_public.py backend/tests/test_seo_public.py
git commit -m "feat(seo): llms.txt fuer KI-Systeme ausliefern"
```

---

### Task 5: Eine Seite, eine URL

`www.novaerp.de` liefert heute die ERP-SPA, `/impressum/` liefert die Startseite und `/impressum.html` ist eine zweite URL für dieselbe Seite. Alle drei erzeugen Dubletten.

**Files:**
- Modify: `backend/app/main.py` (neue Middleware neben `tenant_middleware`)
- Test: `backend/tests/test_seo_public.py`

**Interfaces:**
- Consumes: `app.core.site.canonical_origin`, `hostname`, `is_apex_host`, `is_www_host`
- Produces: Middleware `apex_canonical_middleware`

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_seo_public.py` anhängen:

```python
WWW = {"Host": "www.novaerp.de"}


def test_www_wird_dauerhaft_auf_den_apex_geleitet(web):
    r = web.get("/", headers=WWW, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://novaerp.de/"


def test_schraegstrich_variante_wird_normalisiert(web):
    r = web.get("/impressum/", headers=APEX, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://novaerp.de/impressum"


def test_html_endung_wird_normalisiert(web):
    r = web.get("/impressum.html", headers=APEX, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://novaerp.de/impressum"


def test_index_html_zeigt_auf_die_wurzel(web):
    r = web.get("/index.html", headers=APEX, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://novaerp.de/"


def test_kanonische_url_wird_nicht_umgeleitet(web):
    r = web.get("/impressum", headers=APEX, follow_redirects=False)
    assert r.status_code == 200


def test_subdomains_werden_nicht_umgeleitet(web):
    r = web.get("/irgendwas/", headers=TENANT, follow_redirects=False)
    assert r.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v -k "www or normalisiert or wurzel"`
Expected: FAIL — alle liefern 200 statt 301

- [ ] **Step 3: Write minimal implementation**

In `backend/app/main.py` den Import erweitern:

```python
from fastapi.responses import RedirectResponse
```

Direkt nach der Definition von `tenant_middleware` einfügen:

```python
@app.middleware("http")
async def apex_canonical_middleware(request: Request, call_next):
    """Eine Seite, genau eine URL.

    www, Schrägstrich-Varianten und .html-Endungen werden dauerhaft auf die
    kanonische Form umgeleitet. Ohne das indexiert Google dieselbe Seite
    mehrfach und verteilt ihre Signale auf Dubletten. Betrifft nur den Apex —
    Subdomains liefern die SPA und brauchen ihre Pfade unverändert.
    """
    host = hostname(request)
    if not is_apex_host(host):
        return await call_next(request)

    path = request.url.path
    canonical_path = path
    if canonical_path.endswith(".html"):
        canonical_path = canonical_path[: -len(".html")]
        if canonical_path in ("", "/index"):
            canonical_path = "/"
    if len(canonical_path) > 1 and canonical_path.endswith("/"):
        canonical_path = canonical_path.rstrip("/")

    if is_www_host(host) or canonical_path != path:
        target = f"{canonical_origin()}{canonical_path}"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        return RedirectResponse(target, status_code=301)

    return await call_next(request)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v`
Expected: PASS (20 Tests)

- [ ] **Step 5: Prüfen, dass das Kontaktformular weiter funktioniert**

Die Marketing-Seite postet auf `/api/track` und das Kontaktformular. Beide
Pfade enden weder auf `/` noch auf `.html` und dürfen daher nicht umgeleitet
werden — ein 301 auf ein POST würde den Body verlieren.

Run: `cd backend && python -m pytest tests/ -v -k "track or kontakt or contact"`
Expected: PASS oder "no tests ran"; in keinem Fall neue Fehler

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_seo_public.py
git commit -m "fix(seo): www, Schraegstrich- und .html-Varianten auf die kanonische URL leiten"
```

---

### Task 6: Echtes 404, und nichts ausliefern, was nicht ins Web gehört

Im Docroot liegen neben den Seiten auch `ruvector.db` (1,5 MB SQLite) und eine
`index.backup-*.html`. `_safe_static_file` liefert jede existierende Datei aus
— beide sind damit öffentlich abrufbar. Der Apex-Zweig bekommt deshalb neben
dem 404 eine Endungs-Freigabeliste.

**Files:**
- Create: `backend/static_marketing/404.html`
- Modify: `backend/app/main.py` (Apex-Zweig in `spa_fallback`)
- Test: `backend/tests/test_seo_public.py`

**Interfaces:**
- Consumes: `app.core.site.marketing_dir`
- Produces: nichts für spätere Tasks

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_seo_public.py` anhängen:

```python
def test_unbekannter_apex_pfad_liefert_echtes_404(web):
    r = web.get("/gibt-es-nicht-xyz123", headers=APEX)
    assert r.status_code == 404


def test_404_seite_ist_auf_noindex_gestellt(web):
    r = web.get("/gibt-es-nicht-xyz123", headers=APEX)
    assert "noindex" in r.text


def test_datenbank_im_docroot_wird_nicht_ausgeliefert(web):
    # Liegt tatsächlich dort und wäre sonst als 1,5-MB-Download offen.
    r = web.get("/ruvector.db", headers=APEX)
    assert r.status_code == 404


def test_backup_html_wird_nicht_ausgeliefert(web):
    r = web.get("/index.backup-20260629-220459", headers=APEX)
    assert r.status_code == 404


def test_echte_seiten_werden_weiter_ausgeliefert(web):
    for pfad in ("/", "/impressum", "/og.png", "/shot-dashboard.jpg"):
        assert web.get(pfad, headers=APEX).status_code == 200, pfad


def test_subdomain_behaelt_den_spa_fallback(web):
    # Client-Routing der React-App braucht 200 auf unbekannten Pfaden.
    r = web.get("/produktion/uebersicht", headers=TENANT)
    assert r.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v -k 404`
Expected: FAIL — Status ist 200, die Startseite wird ausgeliefert

- [ ] **Step 3: 404-Seite anlegen**

Neue Datei `backend/static_marketing/404.html`. Farben und Schrift aus
`index.html` übernehmen (`--abyss: #0a0a0a`, `--bronze: #C0814F`):

```html
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Seite nicht gefunden — NovaERP</title>
  <meta name="robots" content="noindex, nofollow" />
  <style>
    body {
      margin: 0; min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
      background: #0a0a0a; color: #F6F1EA;
      font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
      text-align: center; padding: 2rem;
    }
    .code { font-size: 4rem; font-weight: 700; color: #C0814F; margin: 0; }
    h1 { font-size: 1.5rem; font-weight: 600; margin: .5rem 0 1rem; }
    p { color: rgba(246,241,234,.7); margin: 0 0 2rem; }
    a {
      display: inline-block; padding: .75rem 1.5rem; border-radius: .5rem;
      background: #C0814F; color: #0a0a0a; font-weight: 600;
      text-decoration: none;
    }
  </style>
</head>
<body>
  <main>
    <p class="code">404</p>
    <h1>Diese Seite gibt es nicht</h1>
    <p>Der Link ist veraltet oder enthält einen Tippfehler.</p>
    <a href="/">Zur Startseite</a>
  </main>
</body>
</html>
```

- [ ] **Step 4: Catch-All reparieren**

In `backend/app/main.py` oberhalb von `spa_fallback` die Freigabeliste
ergänzen:

```python
# Nur diese Endungen liefert der Apex aus. Der Docroot enthält auch
# Arbeitsdateien (eine SQLite-DB, HTML-Backups); ohne Freigabeliste wären
# die per URL herunterladbar.
_MARKETING_EXTENSIONS = frozenset({
    ".html", ".css", ".js", ".map",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".avif",
    ".woff", ".woff2", ".ttf",
    ".txt", ".xml", ".webmanifest", ".pdf",
})


def _marketing_file(rel_path: str) -> Optional[Path]:
    """Wie ``_safe_static_file``, aber nur für webtaugliche Dateitypen."""
    safe = _safe_static_file(marketing_dist, rel_path)
    if safe and safe.suffix.lower() in _MARKETING_EXTENSIONS:
        return safe
    return None
```

Dann den Apex-Zweig ersetzen. Vorher:

```python
    # Apex (novaerp.de) → Marketing-Seite
    if _is_apex_request(request) and marketing_dist.exists():
        # Direkte Dateianforderung (z.B. /assets/foo.png) prüfen
        safe = _safe_static_file(marketing_dist, full_path)
        if safe:
            return FileResponse(safe)
        # Saubere URLs ohne .html mappen: /impressum → impressum.html
        safe_html = _safe_static_file(marketing_dist, f"{full_path}.html")
        if safe_html:
            return FileResponse(safe_html)
        # Sonst: Marketing-Index ausliefern
        if (marketing_dist / "index.html").exists():
            return FileResponse(marketing_dist / "index.html")
```

Nachher:

```python
    # Apex (novaerp.de) → Marketing-Seite
    if _is_apex_request(request) and marketing_dist.exists():
        # Direkte Dateianforderung (z.B. /assets/foo.png) prüfen
        safe = _marketing_file(full_path)
        if safe:
            return FileResponse(safe)
        # Saubere URLs ohne .html mappen: /impressum → impressum.html
        # Backup-Kopien (index.backup-*.html) bleiben dabei außen vor.
        if not full_path.startswith("index.backup-"):
            safe_html = _marketing_file(f"{full_path}.html")
            if safe_html:
                return FileResponse(safe_html)
        # Unbekannter Pfad auf dem Apex ist ein echter Fehler. Früher kam
        # hier die Startseite mit Status 200 — damit war jede erfundene URL
        # indexierbar und erzeugte eine Dublette.
        not_found = marketing_dist / "404.html"
        if not_found.exists():
            return FileResponse(not_found, status_code=404)
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v`
Expected: PASS (26 Tests)

- [ ] **Step 6: Commit**

```bash
git add backend/static_marketing/404.html backend/app/main.py backend/tests/test_seo_public.py
git commit -m "fix(seo): unbekannte Apex-Pfade liefern 404 statt stiller Startseite"
```

---

### Task 7: Markup auf den Rechtsseiten und noindex auf der Statistik

**Files:**
- Modify: `backend/static_marketing/impressum.html`, `datenschutz.html`, `agb.html`, `stats.html`
- Test: `backend/tests/test_seo_public.py`

**Interfaces:**
- Consumes: `app.core.site.marketing_dir`
- Produces: nichts für spätere Tasks

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_seo_public.py` anhängen:

```python
import json

LD_BLOCK = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL
)

RECHTSSEITEN = {
    "impressum.html": "https://novaerp.de/impressum",
    "datenschutz.html": "https://novaerp.de/datenschutz",
    "agb.html": "https://novaerp.de/agb",
}


@pytest.mark.parametrize("datei,canonical", RECHTSSEITEN.items())
def test_rechtsseiten_haben_canonical_und_open_graph(datei, canonical):
    html = (site.marketing_dir() / datei).read_text(encoding="utf-8")
    assert f'<link rel="canonical" href="{canonical}" />' in html
    assert f'<meta property="og:url" content="{canonical}" />' in html
    assert 'property="og:title"' in html
    assert 'property="og:site_name" content="NovaERP"' in html


@pytest.mark.parametrize("datei", list(RECHTSSEITEN))
def test_rechtsseiten_tragen_webpage_schema(datei):
    html = (site.marketing_dir() / datei).read_text(encoding="utf-8")
    blocks = [json.loads(b) for b in LD_BLOCK.findall(html)]
    assert any(b.get("@type") == "WebPage" for b in blocks)


@pytest.mark.parametrize("datei", ["stats.html", "404.html"])
def test_interne_seiten_sind_auf_noindex(datei):
    html = (site.marketing_dir() / datei).read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex, nofollow" />' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v -k "rechtsseiten or noindex"`
Expected: FAIL — den Rechtsseiten fehlt canonical, `stats.html` fehlt noindex

- [ ] **Step 3: Rechtsseiten ergänzen**

In jede der drei Dateien direkt nach dem `<meta name="viewport" ...>`-Tag
einsetzen, mit der jeweils passenden URL und Beschreibung. Beispiel für
`impressum.html`:

```html
  <meta name="description" content="Anbieterkennzeichnung und Kontaktdaten zu NovaERP." />
  <link rel="canonical" href="https://novaerp.de/impressum" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://novaerp.de/impressum" />
  <meta property="og:title" content="Impressum — NovaERP" />
  <meta property="og:description" content="Anbieterkennzeichnung und Kontaktdaten zu NovaERP." />
  <meta property="og:locale" content="de_DE" />
  <meta property="og:site_name" content="NovaERP" />
  <meta property="og:image" content="https://novaerp.de/og.png" />
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "@id": "https://novaerp.de/impressum",
    "url": "https://novaerp.de/impressum",
    "name": "Impressum — NovaERP",
    "inLanguage": "de-DE",
    "isPartOf": { "@id": "https://novaerp.de/#website" },
    "publisher": { "@id": "https://novaerp.de/#org" }
  }
  </script>
```

Für `datenschutz.html` und `agb.html` dasselbe Muster mit
`/datenschutz` beziehungsweise `/agb`, passendem `name` und passender
Beschreibung. Die `@id`-Verweise auf `#website` und `#org` werden in Task 8
angelegt.

- [ ] **Step 4: Statistik auf noindex stellen**

In `backend/static_marketing/stats.html` nach dem Viewport-Tag einsetzen:

```html
  <meta name="robots" content="noindex, nofollow" />
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v`
Expected: PASS (34 Tests)

- [ ] **Step 6: Commit**

```bash
git add backend/static_marketing/impressum.html backend/static_marketing/datenschutz.html backend/static_marketing/agb.html backend/static_marketing/stats.html backend/tests/test_seo_public.py
git commit -m "feat(seo): canonical, Open Graph und WebPage-Schema auf den Rechtsseiten"
```

---

### Task 8: Entity-Markup der Startseite vervollständigen

Die Startseite hat Organization, SoftwareApplication, Offer und FAQPage. Es fehlen der `WebSite`-Knoten, auf den die Rechtsseiten verweisen, und die Angaben, an denen Suchmaschinen die Entität festmachen.

**Files:**
- Modify: `backend/static_marketing/index.html` (JSON-LD-Block ab Zeile 44)
- Test: `backend/tests/test_seo_public.py`

**Interfaces:**
- Consumes: `app.core.site.marketing_dir`
- Produces: Schema-IDs `https://novaerp.de/#org` und `https://novaerp.de/#website`

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_seo_public.py` anhängen:

```python
def _startseiten_graph():
    html = (site.marketing_dir() / "index.html").read_text(encoding="utf-8")
    blocks = [json.loads(b) for b in LD_BLOCK.findall(html)]
    knoten = []
    for b in blocks:
        knoten.extend(b["@graph"] if "@graph" in b else [b])
    return knoten


def test_startseite_hat_website_knoten_mit_publisher():
    website = [k for k in _startseiten_graph() if k.get("@type") == "WebSite"]
    assert len(website) == 1
    assert website[0]["@id"] == "https://novaerp.de/#website"
    assert website[0]["publisher"] == {"@id": "https://novaerp.de/#org"}
    assert website[0]["inLanguage"] == "de-DE"


def test_organisation_traegt_logo_und_kontakt():
    org = [k for k in _startseiten_graph() if k.get("@type") == "Organization"][0]
    assert org["@id"] == "https://novaerp.de/#org"
    assert org["logo"].startswith("https://novaerp.de/")
    assert org["contactPoint"]["email"] == "info@novaerp.de"


def test_kein_erfundenes_sameas():
    # Erfundene Profilverweise schaden der Entity-Erkennung mehr als sie nutzen.
    org = [k for k in _startseiten_graph() if k.get("@type") == "Organization"][0]
    assert "sameAs" not in org or org["sameAs"]


def test_alle_json_ld_bloecke_der_marketing_seiten_sind_valide():
    for datei in ("index.html", "impressum.html", "datenschutz.html", "agb.html"):
        html = (site.marketing_dir() / datei).read_text(encoding="utf-8")
        for block in LD_BLOCK.findall(html):
            json.loads(block)  # wirft bei kaputtem JSON
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v -k "website_knoten or logo_und_kontakt"`
Expected: FAIL — `IndexError`, weil es keinen `WebSite`-Knoten gibt

- [ ] **Step 3: Graph erweitern**

In `backend/static_marketing/index.html` den `Organization`-Knoten
ergänzen und einen `WebSite`-Knoten davor setzen:

```json
      {
        "@type": "WebSite",
        "@id": "https://novaerp.de/#website",
        "url": "https://novaerp.de/",
        "name": "NovaERP",
        "inLanguage": "de-DE",
        "publisher": { "@id": "https://novaerp.de/#org" }
      },
      {
        "@type": "Organization",
        "@id": "https://novaerp.de/#org",
        "name": "NovaERP",
        "url": "https://novaerp.de/",
        "email": "info@novaerp.de",
        "logo": "https://novaerp.de/logo-dark.png",
        "slogan": "Das ERP, das mit deinem Start-up mitwächst.",
        "address": { "@type": "PostalAddress", "addressLocality": "Karlsruhe", "addressCountry": "DE" },
        "contactPoint": {
          "@type": "ContactPoint",
          "contactType": "customer support",
          "email": "info@novaerp.de",
          "areaServed": "DE",
          "availableLanguage": ["German"]
        }
      },
```

`sameAs` bleibt weg, solange keine echten Profile bekannt sind. Ebenso
`foundingDate` — die Spec nennt es, aber das Gründungsjahr steht nirgends
im Repo. Sobald es feststeht, kommt es als eine Zeile dazu; geraten wird es
nicht.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seo_public.py -v`
Expected: PASS (38 Tests)

- [ ] **Step 5: Gesamte Test-Suite gegen Regressionen**

Run: `cd backend && python -m pytest tests/ -q`
Expected: keine neuen Fehler gegenüber dem Stand vor Task 1

- [ ] **Step 6: Commit**

```bash
git add backend/static_marketing/index.html backend/tests/test_seo_public.py
git commit -m "feat(seo): WebSite-Knoten und Entity-Angaben im Startseiten-Schema"
```

---

## Abnahme

Nach dem letzten Task muss auf dem Apex gelten:

| Prüfung | Erwartung |
|---|---|
| `GET /robots.txt` | 200, `text/plain`, Sitemap-Zeile, KI-Crawler freigegeben |
| `GET /sitemap.xml` | 200, valides XML, vier URLs |
| `GET /llms.txt` | 200, `text/plain`, beginnt mit `# NovaERP` |
| `GET /gibt-es-nicht` | 404 mit noindex-Seite |
| `GET /impressum/` | 301 auf `/impressum` |
| `GET /impressum.html` | 301 auf `/impressum` |
| `www.novaerp.de` | 301 auf den Apex |
| `demo.novaerp.de/robots.txt` | 200, `Disallow: /` |
| Tenant-Subdomain, unbekannter Pfad | weiterhin 200 mit der SPA |

Nicht Teil dieses Plans, aber ohne diese Schritte bleibt die Wirkung aus:
GSC-Property `novaerp.de` per DNS-TXT verifizieren und die Sitemap dort
einreichen.
