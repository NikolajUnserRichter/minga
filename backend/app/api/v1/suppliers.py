"""API-Endpoints für Saatgut-Lieferanten."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, func

from app.api.deps import DBSession, Pagination
from app.models.seed import Supplier
from app.schemas.supplier import (
    SupplierCreate,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdate,
)

router = APIRouter(prefix="/suppliers", tags=["Lieferanten"])


@router.get("", response_model=SupplierListResponse)
async def list_suppliers(
    db: DBSession,
    pagination: Pagination,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
):
    """Liste der Lieferanten mit optionalen Filtern."""
    query = select(Supplier)
    if is_active is not None:
        query = query.where(Supplier.is_active == is_active)
    if search:
        safe = search.replace("%", "\\%").replace("_", "\\_")
        query = query.where(Supplier.name.ilike(f"%{safe}%"))

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0

    query = query.order_by(Supplier.name).offset(pagination.offset).limit(pagination.page_size)
    items = db.execute(query).scalars().all()

    return SupplierListResponse(
        items=[SupplierResponse.model_validate(s) for s in items],
        total=total,
    )


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(data: SupplierCreate, db: DBSession):
    """Neuen Lieferanten anlegen."""
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return SupplierResponse.model_validate(supplier)


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(supplier_id: UUID, db: DBSession):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Lieferant nicht gefunden")
    return SupplierResponse.model_validate(supplier)


@router.patch("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(supplier_id: UUID, data: SupplierUpdate, db: DBSession):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Lieferant nicht gefunden")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return SupplierResponse.model_validate(supplier)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_supplier(supplier_id: UUID, db: DBSession):
    """Soft-Delete: deaktiviert den Lieferanten."""
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Lieferant nicht gefunden")
    supplier.is_active = False
    db.commit()
