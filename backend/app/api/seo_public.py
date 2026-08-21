"""Öffentliche SEO-Dateien der Marketing-Seite.

robots.txt, sitemap.xml und llms.txt werden erzeugt statt als Datei
ausgeliefert. Zwei Gründe: robots.txt muss je Host unterschiedlich
antworten (Apex frei, Tenant-Instanzen gesperrt), und die Sitemap enthält
ab der Content-Engine die in der Datenbank gepflegten Ratgeber-Beiträge.

Der Router muss in ``main.py`` VOR dem Catch-All ``/{full_path:path}``
eingebunden werden — FastAPI matcht in Deklarationsreihenfolge.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response

from app.core.site import canonical_origin, hostname, is_apex_host, marketing_dir

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

# Pfade, die niemand indexieren soll: die API und die interne
# Reichweitenauswertung.
_DISALLOWED = ("/api/", "/stats.html", "/stats")


def _agent_group(agent: str) -> str:
    """Eine robots.txt-Gruppe.

    Die Disallow-Zeilen werden je Gruppe wiederholt, weil ein Crawler mit
    eigener Gruppe die Regeln aus ``User-agent: *`` nicht mehr liest.
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


def _url_entry(
    loc: str, lastmod: Optional[date], changefreq: str, priority: str
) -> list[str]:
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
        lines.extend(
            _url_entry(f"{origin}{path}", _page_lastmod(path), changefreq, priority)
        )
    for article in content_articles():
        lines.extend(
            _url_entry(
                f"{origin}/ratgeber/{article.slug}", article.lastmod, "monthly", "0.6"
            )
        )
    lines.append("</urlset>")

    return Response("\n".join(lines) + "\n", media_type="application/xml")
