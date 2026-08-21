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
