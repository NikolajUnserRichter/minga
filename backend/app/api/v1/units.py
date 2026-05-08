"""API-Endpoints für Maßeinheiten (Stammdaten, read-only für jetzt)."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DBSession
from app.models.unit import UnitOfMeasure, UnitCategory


router = APIRouter(prefix="/units", tags=["Einheiten"])


@router.get("")
async def list_units(
    db: DBSession,
    category: Optional[UnitCategory] = None,
    is_active: bool = True,
):
    """Liste der Maßeinheiten."""
    query = select(UnitOfMeasure).where(UnitOfMeasure.is_active == is_active)
    if category:
        query = query.where(UnitOfMeasure.category == category)
    query = query.order_by(UnitOfMeasure.sort_order, UnitOfMeasure.code)
    units = db.execute(query).scalars().all()
    return [
        {
            "id": str(u.id),
            "code": u.code,
            "name": u.name,
            "symbol": u.symbol,
            "category": u.category.value,
            "is_base_unit": u.is_base_unit,
            "is_active": u.is_active,
        }
        for u in units
    ]


@router.get("/{unit_id}")
async def get_unit(unit_id: UUID, db: DBSession):
    unit = db.get(UnitOfMeasure, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Einheit nicht gefunden")
    return {
        "id": str(unit.id),
        "code": unit.code,
        "name": unit.name,
        "symbol": unit.symbol,
        "category": unit.category.value,
        "is_base_unit": unit.is_base_unit,
        "is_active": unit.is_active,
    }
