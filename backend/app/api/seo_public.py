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
