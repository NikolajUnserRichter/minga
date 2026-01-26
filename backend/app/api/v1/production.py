from typing import Optional
"""
API Endpoints für Produktions-Verwaltung
"""
from datetime import date, timedelta
from uuid import UUID
from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import DBSession, Pagination
from app.models.seed import Seed, SeedBatch
from app.models.production import GrowBatch, GrowBatchStatus, Harvest
from app.schemas.production import (
    GrowBatchCreate, GrowBatchUpdate, GrowBatchResponse, GrowBatchListResponse,
    HarvestCreate, HarvestResponse, HarvestListResponse
)

router = APIRouter()


# ============== GrowBatch Endpoints ==============

@router.get("/grow-batches", response_model=GrowBatchListResponse)
async def list_grow_batches(
    db: DBSession,
    pagination: Pagination,
    status_filter: Optional[GrowBatchStatus] = Query(None, alias="status"),
    seed_id: Optional[UUID] = None,
    erntereif: Optional[bool] = None
):
    """
    Liste aller Wachstumschargen.

    Filter:
    - **status**: KEIMUNG, WACHSTUM, ERNTEREIF, GEERNTET, VERLUST
    - **seed_id**: Nur Chargen einer bestimmten Sorte
    - **erntereif**: Nur erntereife Chargen (im Erntefenster)
    """
    query = select(GrowBatch).options(joinedload(GrowBatch.seed_batch).joinedload(SeedBatch.seed))

    if status_filter:
        query = query.where(GrowBatch.status == status_filter)

    if seed_id:
        query = query.join(SeedBatch).where(SeedBatch.seed_id == seed_id)

    if erntereif is True:
        today = date.today()
        query = query.where(
            GrowBatch.erwartete_ernte_min <= today,
            GrowBatch.erwartete_ernte_max >= today,
            GrowBatch.status.in_([GrowBatchStatus.WACHSTUM, GrowBatchStatus.ERNTEREIF])
        )

    # Total Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Paginated Results
    query = query.order_by(GrowBatch.aussaat_datum.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    batches = db.execute(query).scalars().unique().all()

    items = []
    for batch in batches:
        response = GrowBatchResponse.model_validate(batch)
        response.seed_name = batch.seed_batch.seed.name if batch.seed_batch else None
        items.append(response)

    return GrowBatchListResponse(items=items, total=total)


@router.get("/grow-batches/{batch_id}", response_model=GrowBatchResponse)
async def get_grow_batch(batch_id: UUID, db: DBSession):
    """Einzelne Wachstumscharge abrufen."""
    batch = db.execute(
        select(GrowBatch)
        .options(joinedload(GrowBatch.seed_batch).joinedload(SeedBatch.seed))
        .where(GrowBatch.id == batch_id)
    ).scalar_one_or_none()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wachstumscharge nicht gefunden"
        )

    response = GrowBatchResponse.model_validate(batch)
    response.seed_name = batch.seed_batch.seed.name if batch.seed_batch else None
    return response


@router.post("/grow-batches", response_model=GrowBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_grow_batch(batch_data: GrowBatchCreate, db: DBSession):
    """
    Neue Wachstumscharge anlegen (Aussaat starten).

    Berechnet automatisch:
    - Erwartete Erntedaten basierend auf Saatgut-Parametern
    - Reduziert verfügbares Saatgut in der Charge
    """
    # Seed Batch laden mit Seed
    seed_batch = db.execute(
        select(SeedBatch)
        .options(joinedload(SeedBatch.seed))
        .where(SeedBatch.id == batch_data.seed_batch_id)
    ).scalar_one_or_none()

    if not seed_batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saatgut-Charge nicht gefunden"
        )

    seed = seed_batch.seed

    # Erntedaten berechnen
    keim_ende = batch_data.aussaat_datum + timedelta(days=seed.keimdauer_tage)
    ernte_min = keim_ende + timedelta(days=seed.erntefenster_min_tage - seed.keimdauer_tage)
    ernte_optimal = keim_ende + timedelta(days=seed.erntefenster_optimal_tage - seed.keimdauer_tage)
    ernte_max = keim_ende + timedelta(days=seed.erntefenster_max_tage - seed.keimdauer_tage)

    grow_batch = GrowBatch(
        seed_batch_id=batch_data.seed_batch_id,
        tray_anzahl=batch_data.tray_anzahl,
        aussaat_datum=batch_data.aussaat_datum,
        erwartete_ernte_min=ernte_min,
        erwartete_ernte_optimal=ernte_optimal,
        erwartete_ernte_max=ernte_max,
        regal_position=batch_data.regal_position,
        notizen=batch_data.notizen,
        status=GrowBatchStatus.KEIMUNG
    )

    db.add(grow_batch)
    db.commit()
    db.refresh(grow_batch)

    response = GrowBatchResponse.model_validate(grow_batch)
    response.seed_name = seed.name
    return response


@router.patch("/grow-batches/{batch_id}", response_model=GrowBatchResponse)
async def update_grow_batch(batch_id: UUID, batch_data: GrowBatchUpdate, db: DBSession):
    """
    Wachstumscharge aktualisieren.

    Typische Verwendung:
    - Status ändern (KEIMUNG -> WACHSTUM -> ERNTEREIF)
    - Regalposition ändern
    """
    batch = db.execute(
        select(GrowBatch)
        .options(joinedload(GrowBatch.seed_batch).joinedload(SeedBatch.seed))
        .where(GrowBatch.id == batch_id)
    ).scalar_one_or_none()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wachstumscharge nicht gefunden"
        )

    update_data = batch_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(batch, field, value)

    db.commit()
    db.refresh(batch)

    response = GrowBatchResponse.model_validate(batch)
    response.seed_name = batch.seed_batch.seed.name if batch.seed_batch else None
    return response


@router.post("/grow-batches/{batch_id}/status/{new_status}", response_model=GrowBatchResponse)
async def update_grow_batch_status(
    batch_id: UUID,
    new_status: GrowBatchStatus,
    db: DBSession
):
    """Schneller Status-Update für Wachstumscharge."""
    batch = db.execute(
        select(GrowBatch)
        .options(joinedload(GrowBatch.seed_batch).joinedload(SeedBatch.seed))
        .where(GrowBatch.id == batch_id)
    ).scalar_one_or_none()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wachstumscharge nicht gefunden"
        )

    batch.status = new_status
    db.commit()
    db.refresh(batch)

    response = GrowBatchResponse.model_validate(batch)
    response.seed_name = batch.seed_batch.seed.name if batch.seed_batch else None
    return response


# ============== Harvest Endpoints ==============

@router.get("/harvests", response_model=HarvestListResponse)
async def list_harvests(
    db: DBSession,
    pagination: Pagination,
    von_datum: Optional[date] = None,
    bis_datum: Optional[date] = None,
    grow_batch_id: Optional[UUID] = None
):
    """
    Liste aller Ernten.

    Filter:
    - **von_datum** / **bis_datum**: Zeitraum
    - **grow_batch_id**: Ernten einer bestimmten Charge
    """
    query = select(Harvest)

    if von_datum:
        query = query.where(Harvest.ernte_datum >= von_datum)
    if bis_datum:
        query = query.where(Harvest.ernte_datum <= bis_datum)
    if grow_batch_id:
        query = query.where(Harvest.grow_batch_id == grow_batch_id)

    # Total Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Paginated Results
    query = query.order_by(Harvest.ernte_datum.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    harvests = db.execute(query).scalars().all()

    return HarvestListResponse(
        items=[HarvestResponse.model_validate(h) for h in harvests],
        total=total
    )


@router.post("/harvests", response_model=HarvestResponse, status_code=status.HTTP_201_CREATED)
async def create_harvest(harvest_data: HarvestCreate, db: DBSession):
    """
    Ernte erfassen.

    Aktualisiert automatisch den Status der GrowBatch auf GEERNTET,
    wenn die gesamte erwartete Menge geerntet wurde.
    """
    grow_batch = db.get(GrowBatch, harvest_data.grow_batch_id)
    if not grow_batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wachstumscharge nicht gefunden"
        )

    if grow_batch.status == GrowBatchStatus.GEERNTET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Charge wurde bereits vollständig geerntet"
        )

    if grow_batch.status == GrowBatchStatus.VERLUST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Charge wurde als Verlust markiert"
        )

    harvest = Harvest(**harvest_data.model_dump())
    db.add(harvest)

    # Status auf ERNTEREIF oder GEERNTET setzen
    grow_batch.status = GrowBatchStatus.ERNTEREIF

    db.commit()
    db.refresh(harvest)

    return HarvestResponse.model_validate(harvest)


@router.get("/harvests/{harvest_id}", response_model=HarvestResponse)
async def get_harvest(harvest_id: UUID, db: DBSession):
    """Einzelne Ernte abrufen."""
    harvest = db.get(Harvest, harvest_id)
    if not harvest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ernte nicht gefunden"
        )
    return HarvestResponse.model_validate(harvest)


# ============== Dashboard Endpoints ==============

@router.get("/dashboard/summary")
async def production_dashboard(db: DBSession):
    """
    Produktions-Dashboard Zusammenfassung.

    Liefert Übersicht über:
    - Aktive Chargen nach Status
    - Ernten diese Woche
    - Anstehende Erntefenster
    """
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # Chargen nach Status
    status_counts = db.execute(
        select(GrowBatch.status, func.count(GrowBatch.id))
        .where(GrowBatch.status.in_([
            GrowBatchStatus.KEIMUNG,
            GrowBatchStatus.WACHSTUM,
            GrowBatchStatus.ERNTEREIF
        ]))
        .group_by(GrowBatch.status)
    ).all()

    # Erntereife Chargen
    erntereife = db.execute(
        select(func.count(GrowBatch.id))
        .where(
            GrowBatch.erwartete_ernte_min <= today,
            GrowBatch.erwartete_ernte_max >= today,
            GrowBatch.status.in_([GrowBatchStatus.WACHSTUM, GrowBatchStatus.ERNTEREIF])
        )
    ).scalar() or 0

    # Ernten diese Woche
    ernten_woche = db.execute(
        select(func.sum(Harvest.menge_gramm))
        .where(Harvest.ernte_datum.between(week_start, week_end))
    ).scalar() or 0

    # Verluste diese Woche
    verluste_woche = db.execute(
        select(func.sum(Harvest.verlust_gramm))
        .where(Harvest.ernte_datum.between(week_start, week_end))
    ).scalar() or 0

    return {
        "chargen_nach_status": {s.value: c for s, c in status_counts},
        "erntereife_chargen": erntereife,
        "ernten_diese_woche_gramm": float(ernten_woche),
        "verluste_diese_woche_gramm": float(verluste_woche),
        "woche": {
            "start": week_start.isoformat(),
            "ende": week_end.isoformat()
        }
    }
