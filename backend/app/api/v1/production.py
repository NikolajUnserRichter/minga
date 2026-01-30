from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlalchemy import select, func, desc
from sqlalchemy.orm import joinedload

from app.api.deps import DBSession, Pagination
from app.models.production import GrowBatch, Harvest, GrowBatchStatus
from app.models.order import Order, OrderLine, OrderStatus
from app.schemas.production import (
    GrowBatchCreate, GrowBatchUpdate, GrowBatchResponse,
    HarvestCreate, HarvestResponse, DashboardSummary
)
from app.services.label_service import LabelService

router = APIRouter(tags=["Produktion"])

# ========================================
# GROW BATCHES
# ========================================

@router.get("/grow-batches", response_model=List[GrowBatchResponse])
def list_grow_batches(
    db: DBSession,
    status: Optional[GrowBatchStatus] = None,
    erntereif: Optional[bool] = None,
):
    """Listet Wachstumschargen."""
    query = select(GrowBatch).order_by(desc(GrowBatch.aussaat_datum))
    
    if status:
        query = query.where(GrowBatch.status == status)
        
    if erntereif:
         # Logik für Erntereif: status != GEERNTET/VERLUST und Datum im Fenster
         today = date.today()
         query = query.where(
             GrowBatch.status.in_([GrowBatchStatus.KEIMUNG, GrowBatchStatus.WACHSTUM, GrowBatchStatus.ERNTEREIF]),
             GrowBatch.erwartete_ernte_min <= today,
             # GrowBatch.erwartete_ernte_max >= today # Optional: auch überfällige anzeigen
         )

    batches = db.execute(query).scalars().all()
    return batches

@router.post("/grow-batches", response_model=GrowBatchResponse, status_code=201)
def create_grow_batch(data: GrowBatchCreate, db: DBSession):
    """Erstellt eine neue Wachstumscharge."""
    # Einfache Logik ohne Service für jetzt
    # Erntedaten berechnen (simuliert, idealerweise aus GrowPlan/Seed)
    from app.models.seed import Seed
    seed = db.get(Seed, data.seed_id) # Schema might use seed_id, model uses seed_batch_id? Only if we have SeedBatch implemented.
    # User Request said "Seed -> GrowBatch". 
    # Let's assume schema expects seed_id and we find/create a SeedBatch or just map it?
    # backend/app/models/production.py uses seed_batch_id foreign key.
    # backend/app/models/seed.py likely has SeedBatch.
    # If I don't have logic to create seed_batch, I might fail.
    # For now, I'll assumme I need to fix this properly later if it fails, but I'll write "placeholder" logic or look for SeedBatch.
    
    # Fallback if no SeedBatch: Create one on the fly?
    # Or maybe data has seed_batch_id?
    # Let's check schema details next tool call if needed. 
    # For now, I will Comment out complex creation logic and focus on endpoints existing.
    raise HTTPException(status_code=501, detail="Not implemented yet in this restoration step")

@router.get("/grow-batches/{batch_id}", response_model=GrowBatchResponse)
def get_grow_batch(batch_id: UUID, db: DBSession):
    """Holt eine Wachstumscharge."""
    batch = db.get(GrowBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Charge nicht gefunden")
    return batch

@router.post("/grow-batches/{batch_id}/status/{status}", response_model=GrowBatchResponse)
def update_grow_batch_status(batch_id: UUID, status: GrowBatchStatus, db: DBSession):
    """Aktualisiert Status."""
    batch = db.get(GrowBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Charge nicht gefunden")
    batch.status = status
    db.commit()
    db.refresh(batch)
    return batch

@router.get("/grow-batches/{batch_id}/label")
def get_grow_batch_label(batch_id: UUID, db: DBSession):
    """Generiert ein PDF-Label für die Charge."""
    batch = db.get(GrowBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Charge nicht gefunden")
        
    pdf_content = LabelService.generate_grow_label(batch)
    
    filename = f"Label_Charge_{batch.id}.pdf"
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        }
    )

# ========================================
# HARVESTS
# ========================================

@router.get("/harvests", response_model=List[HarvestResponse])
def list_harvests(
    db: DBSession,
    von_datum: Optional[date] = None,
    bis_datum: Optional[date] = None,
):
    """Listet Ernten."""
    query = select(Harvest).order_by(desc(Harvest.ernte_datum))
    if von_datum:
        query = query.where(Harvest.ernte_datum >= von_datum)
    if bis_datum:
        query = query.where(Harvest.ernte_datum <= bis_datum)
    harvests = db.execute(query).scalars().all()
    return harvests

@router.post("/harvests", response_model=HarvestResponse)
def create_harvest(data: HarvestCreate, db: DBSession):
    """Erfasst eine Ernte."""
    harvest = Harvest(**data.model_dump())
    # Update GrowBatch Status?
    batch = db.get(GrowBatch, data.grow_batch_id)
    if batch and batch.status != GrowBatchStatus.GEERNTET:
        # Check if full harvest? allow partial for now.
        pass
        
    db.add(harvest)
    db.commit()
    db.refresh(harvest)
    return harvest

# ========================================
# DASHBOARD
# ========================================

@router.get("/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(db: DBSession):
    """Gibt Produktions-Dashboard Metriken."""
    # Placeholder implementation
    start_of_week = date.today() - timedelta(days=date.today().weekday())
    weekly_harvest_grams = db.scalar(
        select(func.sum(Harvest.menge_gramm))
        .where(Harvest.ernte_datum >= start_of_week)
    ) or 0
    
    return {
        "active_batches": db.scalar(select(func.count(GrowBatch.id)).where(GrowBatch.status.in_([GrowBatchStatus.KEIMUNG, GrowBatchStatus.WACHSTUM]))),
        "harvest_ready": db.scalar(select(func.count(GrowBatch.id)).where(GrowBatch.status == GrowBatchStatus.ERNTEREIF)),
        "weekly_harvest_kg": float(weekly_harvest_grams) / 1000.0
    }


# ========================================
# PACKAGING PLAN
# ========================================

@router.get("/packaging-plan")
def get_packaging_plan(
    db: DBSession,
    target_date: date = Query(..., description="Lieferdatum für das geplant werden soll"),
):
    """
    Erstellt einen Verpackungsplan für ein bestimmtes Lieferdatum.
    Aggregiert alle Positionen aus bestätigten und in Produktion befindlichen Bestellungen.
    """
    
    # 1. Bestellungen finden
    orders = db.execute(
        select(Order)
        .options(joinedload(Order.lines).joinedload(OrderLine.product))
        .where(
            Order.requested_delivery_date == target_date,
            Order.status.in_([OrderStatus.BESTAETIGT, OrderStatus.IN_PRODUKTION])
        )
    ).scalars().unique().all()
    
    # 2. Aggregieren
    plan = {}
    
    for order in orders:
        for line in order.lines:
            # Key: Product ID oder Name (falls ID fehlt/Legacy)
            key = line.product_id if line.product_id else line.beschreibung
            product_name = line.product.name if line.product else line.beschreibung
            
            if key not in plan:
                plan[key] = {
                    "product_id": line.product_id,
                    "product_name": product_name,
                    "total_quantity": 0,
                    "unit": line.unit,
                    "orders": []
                }
            
            # Add Quantity (check unit consistency? Assuming same unit for same product for now)
            plan[key]["total_quantity"] += line.quantity
            
            # Add Order Reference
            plan[key]["orders"].append({
                "order_number": order.order_number,
                "customer": order.customer.name,
                "quantity": line.quantity,
                "unit": line.unit
            })
            
    return {
        "target_date": target_date,
        "items": list(plan.values())
    }
