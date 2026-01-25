"""
Lager-API - Endpoints für Bestandsverwaltung und Rückverfolgbarkeit
"""
from datetime import date
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import DBSession, PaginationParams
from app.models.inventory import (
    InventoryLocation, SeedInventory, FinishedGoodsInventory,
    PackagingInventory, InventoryMovement, InventoryCount,
    InventoryCountItem, LocationType, MovementType, ArticleType
)
from app.schemas.inventory import (
    InventoryLocationCreate, InventoryLocationUpdate, InventoryLocationResponse,
    SeedInventoryCreate, SeedInventoryUpdate, SeedInventoryResponse,
    FinishedGoodsInventoryCreate, FinishedGoodsInventoryUpdate, FinishedGoodsInventoryResponse,
    PackagingInventoryCreate, PackagingInventoryUpdate, PackagingInventoryResponse,
    InventoryMovementCreate, InventoryMovementResponse,
    InventoryCountCreate, InventoryCountResponse, InventoryCountItemCreate,
    StockOverviewItem, TraceabilityResponse,
)
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Lager"])


# ========================================
# LOCATIONS
# ========================================

@router.get("/locations", response_model=list[InventoryLocationResponse])
def list_locations(
    db: Session = Depends(DBSession),
    location_type: LocationType | None = None,
    is_active: bool = True,
):
    """Listet alle Lagerorte."""
    query = select(InventoryLocation).where(InventoryLocation.is_active == is_active)

    if location_type:
        query = query.where(InventoryLocation.location_type == location_type)

    locations = db.execute(query).scalars().all()
    return locations


@router.get("/locations/{location_id}", response_model=InventoryLocationResponse)
def get_location(location_id: UUID, db: Session = Depends(DBSession)):
    """Gibt einen Lagerort zurück."""
    location = db.get(InventoryLocation, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")
    return location


@router.post("/locations", response_model=InventoryLocationResponse, status_code=201)
def create_location(data: InventoryLocationCreate, db: Session = Depends(DBSession)):
    """Erstellt einen neuen Lagerort."""
    location = InventoryLocation(**data.model_dump())
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.patch("/locations/{location_id}", response_model=InventoryLocationResponse)
def update_location(
    location_id: UUID,
    data: InventoryLocationUpdate,
    db: Session = Depends(DBSession),
):
    """Aktualisiert einen Lagerort."""
    location = db.get(InventoryLocation, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(location, field, value)

    db.commit()
    db.refresh(location)
    return location


# ========================================
# SEED INVENTORY
# ========================================

@router.get("/seeds", response_model=list[SeedInventoryResponse])
def list_seed_inventory(
    db: Session = Depends(DBSession),
    pagination: PaginationParams = Depends(),
    seed_id: UUID | None = None,
    location_id: UUID | None = None,
    low_stock_only: bool = False,
):
    """Listet Saatgut-Bestände."""
    query = select(SeedInventory).where(SeedInventory.is_active == True)

    if seed_id:
        query = query.where(SeedInventory.seed_id == seed_id)

    if location_id:
        query = query.where(SeedInventory.location_id == location_id)

    if low_stock_only:
        query = query.where(SeedInventory.current_quantity <= SeedInventory.min_quantity)

    query = query.offset(pagination.skip).limit(pagination.limit)
    inventory = db.execute(query).scalars().all()
    return inventory


@router.get("/seeds/{inventory_id}", response_model=SeedInventoryResponse)
def get_seed_inventory(inventory_id: UUID, db: Session = Depends(DBSession)):
    """Gibt einen Saatgut-Bestand zurück."""
    inventory = db.get(SeedInventory, inventory_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Saatgut-Bestand nicht gefunden")
    return inventory


@router.post("/seeds/receive", response_model=SeedInventoryResponse, status_code=201)
def receive_seed_batch(
    seed_id: UUID,
    batch_number: str,
    quantity: Decimal,
    unit: str,
    location_id: UUID,
    supplier: str | None = None,
    mhd: date | None = None,
    purchase_price: Decimal | None = None,
    is_organic: bool = False,
    organic_certification: str | None = None,
    notes: str | None = None,
    db: Session = Depends(DBSession),
):
    """Erfasst einen neuen Saatgut-Wareneingang."""
    service = InventoryService(db)
    try:
        inventory = service.receive_seed_batch(
            seed_id=seed_id,
            batch_number=batch_number,
            quantity=quantity,
            unit=unit,
            location_id=location_id,
            supplier=supplier,
            mhd=mhd,
            purchase_price=purchase_price,
            is_organic=is_organic,
            organic_certification=organic_certification,
            notes=notes,
        )
        db.commit()
        db.refresh(inventory)
        return inventory
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/seeds/{inventory_id}/consume")
def consume_seed_for_sowing(
    inventory_id: UUID,
    quantity: Decimal,
    grow_batch_id: UUID | None = None,
    notes: str | None = None,
    db: Session = Depends(DBSession),
):
    """Verbraucht Saatgut für Aussaat."""
    service = InventoryService(db)
    try:
        inventory, movement = service.consume_seed_for_sowing(
            seed_inventory_id=inventory_id,
            quantity=quantity,
            grow_batch_id=grow_batch_id,
            notes=notes,
        )
        db.commit()
        return {
            "inventory": SeedInventoryResponse.model_validate(inventory),
            "movement": InventoryMovementResponse.model_validate(movement),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========================================
# FINISHED GOODS INVENTORY
# ========================================

@router.get("/finished-goods", response_model=list[FinishedGoodsInventoryResponse])
def list_finished_goods(
    db: Session = Depends(DBSession),
    pagination: PaginationParams = Depends(),
    product_id: UUID | None = None,
    location_id: UUID | None = None,
    available_only: bool = True,
):
    """Listet Fertigwaren-Bestände."""
    query = select(FinishedGoodsInventory).where(FinishedGoodsInventory.is_active == True)

    if product_id:
        query = query.where(FinishedGoodsInventory.product_id == product_id)

    if location_id:
        query = query.where(FinishedGoodsInventory.location_id == location_id)

    if available_only:
        query = query.where(FinishedGoodsInventory.available_quantity > 0)

    query = query.order_by(FinishedGoodsInventory.mhd.asc())
    query = query.offset(pagination.skip).limit(pagination.limit)

    inventory = db.execute(query).scalars().all()
    return inventory


@router.get("/finished-goods/{inventory_id}", response_model=FinishedGoodsInventoryResponse)
def get_finished_goods(inventory_id: UUID, db: Session = Depends(DBSession)):
    """Gibt einen Fertigwaren-Bestand zurück."""
    inventory = db.get(FinishedGoodsInventory, inventory_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Fertigwaren-Bestand nicht gefunden")
    return inventory


@router.post("/finished-goods/receive-harvest", response_model=FinishedGoodsInventoryResponse, status_code=201)
def receive_harvest(
    harvest_id: UUID,
    product_id: UUID,
    location_id: UUID,
    quantity: Decimal,
    unit: str,
    shelf_life_days: int = 7,
    notes: str | None = None,
    db: Session = Depends(DBSession),
):
    """Erfasst geerntete Ware im Lager."""
    service = InventoryService(db)
    try:
        inventory = service.receive_harvest(
            harvest_id=harvest_id,
            product_id=product_id,
            location_id=location_id,
            quantity=quantity,
            unit=unit,
            shelf_life_days=shelf_life_days,
            notes=notes,
        )
        db.commit()
        db.refresh(inventory)
        return inventory
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/finished-goods/ship")
def ship_goods(
    product_id: UUID,
    quantity: Decimal,
    order_id: UUID | None = None,
    customer_id: UUID | None = None,
    notes: str | None = None,
    db: Session = Depends(DBSession),
):
    """Bucht Warenausgang (Lieferung an Kunden)."""
    service = InventoryService(db)
    try:
        movements, remaining = service.ship_goods(
            product_id=product_id,
            quantity=quantity,
            order_id=order_id,
            customer_id=customer_id,
            notes=notes,
        )
        db.commit()
        return {
            "shipped_quantity": quantity - remaining,
            "remaining_quantity": remaining,
            "movements": [InventoryMovementResponse.model_validate(m) for m in movements],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/finished-goods/{inventory_id}/loss")
def record_loss(
    inventory_id: UUID,
    quantity: Decimal,
    reason: str,
    db: Session = Depends(DBSession),
):
    """Erfasst Verlust/Verderb."""
    service = InventoryService(db)
    try:
        inventory, movement = service.record_loss(
            inventory_id=inventory_id,
            quantity=quantity,
            reason=reason,
        )
        db.commit()
        return {
            "inventory": FinishedGoodsInventoryResponse.model_validate(inventory),
            "movement": InventoryMovementResponse.model_validate(movement),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========================================
# PACKAGING INVENTORY
# ========================================

@router.get("/packaging", response_model=list[PackagingInventoryResponse])
def list_packaging(
    db: Session = Depends(DBSession),
    pagination: PaginationParams = Depends(),
    location_id: UUID | None = None,
    low_stock_only: bool = False,
):
    """Listet Verpackungsmaterial-Bestände."""
    query = select(PackagingInventory).where(PackagingInventory.is_active == True)

    if location_id:
        query = query.where(PackagingInventory.location_id == location_id)

    if low_stock_only:
        query = query.where(PackagingInventory.current_quantity <= PackagingInventory.min_quantity)

    query = query.offset(pagination.skip).limit(pagination.limit)
    inventory = db.execute(query).scalars().all()
    return inventory


@router.post("/packaging", response_model=PackagingInventoryResponse, status_code=201)
def create_packaging_inventory(
    data: PackagingInventoryCreate,
    db: Session = Depends(DBSession),
):
    """Erstellt einen neuen Verpackungsmaterial-Bestand."""
    inventory = PackagingInventory(**data.model_dump())
    db.add(inventory)
    db.commit()
    db.refresh(inventory)
    return inventory


@router.patch("/packaging/{inventory_id}", response_model=PackagingInventoryResponse)
def update_packaging(
    inventory_id: UUID,
    data: PackagingInventoryUpdate,
    db: Session = Depends(DBSession),
):
    """Aktualisiert Verpackungsmaterial-Bestand."""
    inventory = db.get(PackagingInventory, inventory_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Verpackungsmaterial nicht gefunden")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(inventory, field, value)

    db.commit()
    db.refresh(inventory)
    return inventory


# ========================================
# MOVEMENTS
# ========================================

@router.get("/movements", response_model=list[InventoryMovementResponse])
def list_movements(
    db: Session = Depends(DBSession),
    pagination: PaginationParams = Depends(),
    article_type: ArticleType | None = None,
    movement_type: MovementType | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
):
    """Listet Lagerbewegungen."""
    query = select(InventoryMovement)

    if article_type:
        query = query.where(InventoryMovement.article_type == article_type)

    if movement_type:
        query = query.where(InventoryMovement.movement_type == movement_type)

    if from_date:
        query = query.where(InventoryMovement.movement_date >= from_date)

    if to_date:
        query = query.where(InventoryMovement.movement_date <= to_date)

    query = query.order_by(InventoryMovement.created_at.desc())
    query = query.offset(pagination.skip).limit(pagination.limit)

    movements = db.execute(query).scalars().all()
    return movements


@router.post("/movements", response_model=InventoryMovementResponse, status_code=201)
def create_movement(
    data: InventoryMovementCreate,
    db: Session = Depends(DBSession),
):
    """Erstellt eine manuelle Lagerbewegung."""
    movement = InventoryMovement(**data.model_dump())
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement


# ========================================
# INVENTORY COUNTS
# ========================================

@router.get("/counts", response_model=list[InventoryCountResponse])
def list_inventory_counts(
    db: Session = Depends(DBSession),
    pagination: PaginationParams = Depends(),
    location_id: UUID | None = None,
    is_finalized: bool | None = None,
):
    """Listet Inventuren."""
    query = select(InventoryCount)

    if location_id:
        query = query.where(InventoryCount.location_id == location_id)

    if is_finalized is not None:
        query = query.where(InventoryCount.is_finalized == is_finalized)

    query = query.order_by(InventoryCount.count_date.desc())
    query = query.offset(pagination.skip).limit(pagination.limit)

    counts = db.execute(query).scalars().all()
    return counts


@router.get("/counts/{count_id}", response_model=InventoryCountResponse)
def get_inventory_count(count_id: UUID, db: Session = Depends(DBSession)):
    """Gibt eine Inventur mit allen Positionen zurück."""
    count = db.get(InventoryCount, count_id)
    if not count:
        raise HTTPException(status_code=404, detail="Inventur nicht gefunden")
    return count


@router.post("/counts", response_model=InventoryCountResponse, status_code=201)
def create_inventory_count(
    location_id: UUID,
    article_type: ArticleType,
    count_date: date | None = None,
    notes: str | None = None,
    db: Session = Depends(DBSession),
):
    """Startet eine neue Inventur."""
    service = InventoryService(db)
    try:
        count = service.create_inventory_count(
            location_id=location_id,
            article_type=article_type,
            count_date=count_date,
            notes=notes,
        )
        db.commit()
        db.refresh(count)
        return count
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/counts/{count_id}/items")
def add_count_item(
    count_id: UUID,
    data: InventoryCountItemCreate,
    db: Session = Depends(DBSession),
):
    """Fügt eine gezählte Position zur Inventur hinzu."""
    count = db.get(InventoryCount, count_id)
    if not count:
        raise HTTPException(status_code=404, detail="Inventur nicht gefunden")

    if count.is_finalized:
        raise HTTPException(status_code=400, detail="Inventur ist bereits abgeschlossen")

    item = InventoryCountItem(
        inventory_count_id=count_id,
        **data.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return item


@router.post("/counts/{count_id}/finalize", response_model=InventoryCountResponse)
def finalize_inventory_count(
    count_id: UUID,
    apply_corrections: bool = True,
    db: Session = Depends(DBSession),
):
    """Schließt eine Inventur ab und wendet optional Korrekturen an."""
    service = InventoryService(db)
    try:
        count = service.finalize_inventory_count(
            count_id=count_id,
            apply_corrections=apply_corrections,
        )
        db.commit()
        db.refresh(count)
        return count
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========================================
# STOCK OVERVIEW & TRACEABILITY
# ========================================

@router.get("/stock-overview", response_model=list[StockOverviewItem])
def get_stock_overview(
    db: Session = Depends(DBSession),
    article_type: ArticleType | None = None,
):
    """Gibt Bestandsübersicht zurück."""
    service = InventoryService(db)
    return service.get_stock_overview(article_type=article_type)


@router.get("/low-stock-alerts")
def get_low_stock_alerts(db: Session = Depends(DBSession)):
    """Gibt Artikel mit niedrigem Bestand zurück."""
    service = InventoryService(db)
    return service.get_low_stock_alerts()


@router.get("/traceability/{finished_goods_id}", response_model=TraceabilityResponse)
def get_traceability(
    finished_goods_id: UUID,
    db: Session = Depends(DBSession),
):
    """Gibt vollständige Rückverfolgbarkeit für Fertigware zurück."""
    service = InventoryService(db)
    try:
        return service.get_traceability(finished_goods_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
