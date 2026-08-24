"""Druck-Warteschlange: ERP reiht ein, ein Agent im Hofnetz druckt.

Der Server steht im Rechenzentrum, der Etikettendrucker im Hofnetz — dazwischen
liegt keine Route und soll auch keine liegen. Im Alltag druckt deshalb der
Browser direkt, denn der sieht beide Seiten.

Diese Schnittstelle deckt den anderen Fall ab: das ERP legt einen fertigen
Druckauftrag samt PDF ab, und ein kleiner Agent im Hofnetz fragt regelmäßig
nach, übernimmt einen Auftrag, druckt ihn und meldet zurück. Der Agent bringt
seinen eigenen Schlüssel mit (``PRINT_AGENT_KEY``) — er ist kein ERP-Benutzer
und soll auch keiner sein.

Aufgeteilt in zwei Router, weil die beiden Seiten unterschiedlich anmelden:
``router`` hängt an der normalen Benutzer-Anmeldung, ``agent_router`` am
Agent-Schlüssel.
"""
from __future__ import annotations

import os
import secrets
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import select, update

from app.api.deps import CurrentUser, DBSession
from app.models.print_job import PrintJob, PrintJobStatus
from app.schemas.print_job import PrintJobClaim, PrintJobFailure, PrintJobResponse
from app.services.label_service import (
    KeineAussaat,
    UnbekanntesFormat,
    baue_aussaat_etikettenbogen,
)


def _require_print_agent(x_print_agent_key: Optional[str] = Header(default=None)) -> None:
    """Türsteher für den lokalen Druck-Agenten.

    Ohne gesetzten ``PRINT_AGENT_KEY`` bleibt die Schnittstelle zu — eine
    unkonfigurierte Warteschlange soll nicht versehentlich offen stehen.
    """
    expected = os.environ.get("PRINT_AGENT_KEY", "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="PRINT_AGENT_KEY ist nicht konfiguriert — Druck-Agent deaktiviert.",
        )
    # Constant-time-Vergleich gegen Timing-Attack
    if not x_print_agent_key or not secrets.compare_digest(x_print_agent_key, expected):
        raise HTTPException(status_code=401, detail="Ungültiger Druck-Agent-Key")


router = APIRouter(prefix="/print-jobs", tags=["Druck"])
agent_router = APIRouter(
    prefix="/print-agent",
    tags=["Druck"],
    dependencies=[Depends(_require_print_agent)],
)


def _benutzer_id(user) -> Optional[UUID]:
    """User-ID als UUID — Basic-Auth-Kennungen sind keine, dann eben None."""
    try:
        return UUID(user["id"])
    except (KeyError, TypeError, ValueError):
        return None


def _hole(db, job_id: UUID) -> PrintJob:
    job = db.get(PrintJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")
    return job


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# ERP-Seite: einreihen und nachsehen
# --------------------------------------------------------------------------

@router.post("/aussaat-etiketten", response_model=PrintJobResponse,
             status_code=status.HTTP_201_CREATED)
def enqueue_aussaat_labels(
    db: DBSession,
    user: CurrentUser,
    datum: Optional[date] = Query(None, description="Aussaattag, Vorgabe: heute"),
    format: str = Query("avery-48x17", description="Etikettenformat"),
    kopien: int = Query(1, ge=1, le=20, description="Anzahl Ausdrucke"),
    drucker: Optional[str] = Query(None, max_length=100,
                                   description="Zielgerät, leer = Standarddrucker des Agenten"),
):
    """Reiht den Etikettenbogen eines Aussaattages in die Warteschlange ein.

    Das PDF wird sofort gerendert und am Auftrag abgelegt. Gedruckt wird damit
    der Stand von jetzt — auch wenn der Agent erst in einer Stunde vorbeischaut
    und die Chargen sich bis dahin geändert haben.
    """
    tag = datum or date.today()
    try:
        pdf, dateiname = baue_aussaat_etikettenbogen(db, tag, format)
    except UnbekanntesFormat as fehler:
        raise HTTPException(status_code=400, detail=str(fehler))
    except KeineAussaat as fehler:
        raise HTTPException(status_code=404, detail=str(fehler))

    job = PrintJob(
        titel=f"Aussaat-Etiketten {tag.strftime('%d.%m.%Y')}",
        dateiname=dateiname,
        dokument=pdf,
        groesse_bytes=len(pdf),
        format=format,
        drucker=drucker,
        kopien=kopien,
        erstellt_von=_benutzer_id(user),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return PrintJobResponse.model_validate(job)


@router.get("", response_model=list[PrintJobResponse])
def list_print_jobs(
    db: DBSession,
    status_filter: Optional[PrintJobStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
):
    """Druckaufträge, neueste zuerst."""
    query = select(PrintJob).order_by(PrintJob.erstellt_am.desc()).limit(limit)
    if status_filter is not None:
        query = query.where(PrintJob.status == status_filter)

    jobs = db.execute(query).scalars().all()
    return [PrintJobResponse.model_validate(j) for j in jobs]


@router.post("/{job_id}/requeue", response_model=PrintJobResponse)
def requeue_print_job(job_id: UUID, db: DBSession):
    """Stellt einen Auftrag zurück in die Warteschlange.

    Für den Papierstau ebenso wie für den Agenten, der mitten im Druck
    abgestürzt ist — sonst bliebe der Auftrag auf IN_ARBEIT stehen und
    niemand würde ihn je wieder anfassen.
    """
    job = _hole(db, job_id)
    if job.status == PrintJobStatus.OFFEN:
        return PrintJobResponse.model_validate(job)

    job.status = PrintJobStatus.OFFEN
    job.fehler = None
    job.agent = None
    job.geholt_am = None
    job.erledigt_am = None
    db.commit()
    db.refresh(job)
    return PrintJobResponse.model_validate(job)


# --------------------------------------------------------------------------
# Agent-Seite: abholen, drucken, zurückmelden
# --------------------------------------------------------------------------

@agent_router.get("/jobs", response_model=list[PrintJobResponse])
def agent_list_open_jobs(db: DBSession, limit: int = Query(20, ge=1, le=100)):
    """Was zu drucken ist — älteste zuerst, damit nichts liegen bleibt."""
    jobs = db.execute(
        select(PrintJob)
        .where(PrintJob.status == PrintJobStatus.OFFEN)
        .order_by(PrintJob.erstellt_am)
        .limit(limit)
    ).scalars().all()
    return [PrintJobResponse.model_validate(j) for j in jobs]


@agent_router.post("/jobs/{job_id}/claim", response_model=PrintJobResponse)
def agent_claim_job(job_id: UUID, db: DBSession, daten: Optional[PrintJobClaim] = None):
    """Übernimmt einen Auftrag — genau einmal.

    Der Wechsel OFFEN → IN_ARBEIT passiert als ein einziges UPDATE mit
    Bedingung auf den alten Status. Zwei Agenten (oder ein Agent nach einem
    Neustart) können denselben Auftrag so nicht doppelt drucken.
    """
    _hole(db, job_id)

    ergebnis = db.execute(
        update(PrintJob)
        .where(PrintJob.id == job_id, PrintJob.status == PrintJobStatus.OFFEN)
        .values(
            status=PrintJobStatus.IN_ARBEIT,
            geholt_am=_jetzt(),
            agent=(daten.agent if daten else None),
            versuche=PrintJob.versuche + 1,
        )
    )
    if ergebnis.rowcount == 0:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Druckauftrag ist nicht (mehr) offen — vermutlich hat ihn schon jemand übernommen.",
        )

    db.commit()
    return PrintJobResponse.model_validate(_hole(db, job_id))


@agent_router.get("/jobs/{job_id}/document")
def agent_get_document(job_id: UUID, db: DBSession):
    """Die PDF-Bytes des Auftrags, so wie sie beim Einreihen entstanden sind."""
    job = _hole(db, job_id)
    return Response(
        content=job.dokument,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={job.dateiname}"},
    )


@agent_router.post("/jobs/{job_id}/complete", response_model=PrintJobResponse)
def agent_complete_job(job_id: UUID, db: DBSession):
    """Gedruckt."""
    job = _hole(db, job_id)
    job.status = PrintJobStatus.GEDRUCKT
    job.fehler = None
    job.erledigt_am = _jetzt()
    db.commit()
    db.refresh(job)
    return PrintJobResponse.model_validate(job)


@agent_router.post("/jobs/{job_id}/fail", response_model=PrintJobResponse)
def agent_fail_job(job_id: UUID, daten: PrintJobFailure, db: DBSession):
    """Schiefgegangen — der Grund bleibt am Auftrag stehen.

    Zurück in die Schlange geht er nicht von allein: warum der Druck scheitert,
    steht meist vor dem Gerät und nicht im Server.
    """
    job = _hole(db, job_id)
    job.status = PrintJobStatus.FEHLER
    job.fehler = daten.fehler
    job.erledigt_am = _jetzt()
    db.commit()
    db.refresh(job)
    return PrintJobResponse.model_validate(job)
