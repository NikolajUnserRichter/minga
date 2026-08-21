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
