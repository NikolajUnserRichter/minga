"""Belegstatus (Paket 4, Abschnitt C): GET /api/v1/belegstatus.

Rechte wie die Rechnungen (main.py: _deps_geld — Admin, Vertrieb,
Buchhaltung): die Übersicht zeigt Rechnungs-, Versand- und Zahlstatus.
Regeln: app/services/belegstatus.py.
"""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.deps import DBSession, Pagination
from app.schemas.belegstatus import BelegstatusListe
from app.services.belegstatus import belegstatus
from app.services.order_status_service import heute_berlin

router = APIRouter(prefix="/belegstatus", tags=["Belegstatus"])


@router.get("", response_model=BelegstatusListe)
def belegstatus_liste(
    db: DBSession,
    pagination: Pagination,
    von: Optional[date] = None,
    bis: Optional[date] = None,
    kunde_id: Optional[UUID] = None,
    nur_unvollstaendig: bool = False,
):
    """Je Bestellung: Lieferschein erstellt, Rechnung erstellt, versendet, bezahlt.

    - **von** / **bis**: Liefertag (tatsächlich, sonst Wunschtermin)
    - **kunde_id**: ein Kunde
    - **nur_unvollstaendig**: nur geliefert, aber ohne Rechnung, mit
      Rechnungsentwurf oder Rechnung nicht versendet
    - **page** / **page_size**: Seiten (höchstens 100 je Seite)

    `unvollstaendig` zählt die Lücken in Zeitraum und Kunde, auch wenn
    `nur_unvollstaendig` aus ist (Zahl am Filter).
    """
    if von and bis and von > bis:
        raise HTTPException(status_code=422, detail="„von“ liegt nach „bis“")
    heute = heute_berlin()
    zeilen = belegstatus(db, heute=heute, von=von, bis=bis, kunde_id=kunde_id)
    unvollstaendig = [z for z in zeilen if z["unvollstaendig"]]
    auswahl = unvollstaendig if nur_unvollstaendig else zeilen
    return {
        "items": auswahl[pagination.offset:pagination.offset + pagination.page_size],
        "total": len(auswahl),
        "unvollstaendig": len(unvollstaendig),
        "heute": heute,
    }
