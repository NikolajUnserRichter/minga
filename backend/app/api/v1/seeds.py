from typing import Optional
"""
API Endpoints für Saatgut-Verwaltung
"""
from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.deps import DBSession, Pagination
from app.models.seed import Seed, SeedBatch
from app.schemas.seed import (
    SeedCreate, SeedUpdate, SeedResponse, SeedListResponse,
    SeedBatchCreate, SeedBatchResponse
)

router = APIRouter()


# ============== Seed Endpoints ==============

@router.get("", response_model=SeedListResponse)
async def list_seeds(
    db: DBSession,
    pagination: Pagination,
    aktiv: Optional[bool] = None,
    search: Optional[str] = None
):
    """
    Liste aller Saatgut-Sorten abrufen.

    - **aktiv**: Optional - nur aktive/inaktive Sorten
    - **search**: Optional - Suche nach Name
    """
    query = select(Seed)

    if aktiv is not None:
        query = query.where(Seed.aktiv == aktiv)

    if search:
        query = query.where(Seed.name.ilike(f"%{search}%"))

    # Total Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Paginated Results
    query = query.offset(pagination.offset).limit(pagination.page_size)
    seeds = db.execute(query).scalars().all()

    return SeedListResponse(
        items=[SeedResponse.model_validate(s) for s in seeds],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size
    )


@router.get("/{seed_id}", response_model=SeedResponse)
async def get_seed(seed_id: UUID, db: DBSession):
    """Einzelne Saatgut-Sorte abrufen."""
    seed = db.get(Seed, seed_id)
    if not seed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saatgut-Sorte nicht gefunden"
        )
    return SeedResponse.model_validate(seed)


@router.post("", response_model=SeedResponse, status_code=status.HTTP_201_CREATED)
async def create_seed(seed_data: SeedCreate, db: DBSession):
    """
    Neue Saatgut-Sorte anlegen.

    Validiert automatisch:
    - Erntefenster-Logik (min < optimal < max)
    """
    # Validierung Erntefenster
    if not (seed_data.erntefenster_min_tage <=
            seed_data.erntefenster_optimal_tage <=
            seed_data.erntefenster_max_tage):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Erntefenster ungültig: min <= optimal <= max erforderlich"
        )

    seed = Seed(**seed_data.model_dump())
    db.add(seed)
    db.commit()
    db.refresh(seed)

    return SeedResponse.model_validate(seed)


@router.patch("/{seed_id}", response_model=SeedResponse)
async def update_seed(seed_id: UUID, seed_data: SeedUpdate, db: DBSession):
    """Saatgut-Sorte aktualisieren."""
    seed = db.get(Seed, seed_id)
    if not seed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saatgut-Sorte nicht gefunden"
        )

    update_data = seed_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(seed, field, value)

    db.commit()
    db.refresh(seed)

    return SeedResponse.model_validate(seed)


@router.delete("/{seed_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_seed(seed_id: UUID, db: DBSession):
    """
    Saatgut-Sorte löschen.

    Hinweis: Kann nicht gelöscht werden, wenn noch Chargen existieren.
    Alternativ auf inaktiv setzen.
    """
    seed = db.get(Seed, seed_id)
    if not seed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saatgut-Sorte nicht gefunden"
        )

    # Prüfen ob Chargen existieren
    batch_count = db.execute(
        select(func.count()).where(SeedBatch.seed_id == seed_id)
    ).scalar()

    if batch_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kann nicht gelöscht werden: {batch_count} Chargen vorhanden. "
                   "Bitte stattdessen deaktivieren."
        )

    db.delete(seed)
    db.commit()


# ============== Seed Batch Endpoints ==============

@router.get("/{seed_id}/batches", response_model=list[SeedBatchResponse])
async def list_seed_batches(seed_id: UUID, db: DBSession):
    """Alle Chargen einer Saatgut-Sorte abrufen."""
    seed = db.get(Seed, seed_id)
    if not seed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saatgut-Sorte nicht gefunden"
        )

    batches = db.execute(
        select(SeedBatch)
        .where(SeedBatch.seed_id == seed_id)
        .order_by(SeedBatch.created_at.desc())
    ).scalars().all()

    return [SeedBatchResponse.model_validate(b) for b in batches]


@router.post("/batches", response_model=SeedBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_seed_batch(batch_data: SeedBatchCreate, db: DBSession):
    """
    Neue Saatgut-Charge anlegen.

    Wird bei Wareneingang verwendet.
    """
    # Prüfen ob Seed existiert
    seed = db.get(Seed, batch_data.seed_id)
    if not seed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saatgut-Sorte nicht gefunden"
        )

    batch = SeedBatch(
        **batch_data.model_dump(),
        verbleibend_gramm=batch_data.menge_gramm  # Initial = Gesamtmenge
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    return SeedBatchResponse.model_validate(batch)


@router.get("/batches/{batch_id}", response_model=SeedBatchResponse)
async def get_seed_batch(batch_id: UUID, db: DBSession):
    """Einzelne Saatgut-Charge abrufen."""
    batch = db.get(SeedBatch, batch_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saatgut-Charge nicht gefunden"
        )
    return SeedBatchResponse.model_validate(batch)
