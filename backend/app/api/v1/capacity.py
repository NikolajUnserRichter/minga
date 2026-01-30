from typing import List
from uuid import UUID
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DBSession
from app.models.capacity import Capacity
from app.schemas.capacity import CapacityCreate, CapacityUpdate, Capacity as CapacitySchema

router = APIRouter(tags=["Kapazität"])

@router.get("/capacity", response_model=List[CapacitySchema])
def list_capacities(db: DBSession):
    """Listet alle Kapazitäts-Ressourcen auf."""
    stmt = select(Capacity).order_by(Capacity.ressource_typ, Capacity.name)
    return db.execute(stmt).scalars().all()

@router.post("/capacity", response_model=CapacitySchema, status_code=201)
def create_capacity(data: CapacityCreate, db: DBSession):
    """Erstellt eine neue Ressource."""
    capacity = Capacity(**data.model_dump())
    db.add(capacity)
    db.commit()
    db.refresh(capacity)
    return capacity

@router.get("/capacity/{id}", response_model=CapacitySchema)
def get_capacity(id: UUID, db: DBSession):
    """Holt eine spezifische Ressource."""
    capacity = db.get(Capacity, id)
    if not capacity:
        raise HTTPException(status_code=404, detail="Ressource nicht gefunden")
    return capacity

@router.patch("/capacity/{id}", response_model=CapacitySchema)
def update_capacity(id: UUID, data: CapacityUpdate, db: DBSession):
    """Aktualisiert eine Ressource."""
    capacity = db.get(Capacity, id)
    if not capacity:
        raise HTTPException(status_code=404, detail="Ressource nicht gefunden")
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(capacity, field, value)
        
    db.commit()
    db.refresh(capacity)
    return capacity

@router.delete("/capacity/{id}")
def delete_capacity(id: UUID, db: DBSession):
    """Löscht eine Ressource."""
    capacity = db.get(Capacity, id)
    if not capacity:
        raise HTTPException(status_code=404, detail="Ressource nicht gefunden")
        
    db.delete(capacity)
    db.commit()
    return {"ok": True}

@router.get("/capacity/summary/overview")
def get_capacity_summary(db: DBSession):
    """Gibt eine Zusammenfassung der Auslastung pro Typ."""
    # TODO: Aggregierte Stats wenn gewünscht
    return {"message": "Not implemented yet"}
