from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case

from app.api.deps import DBSession
from app.models.invoice import Invoice, InvoiceStatus
from app.models.customer import Customer, CustomerType
from app.models.production import GrowBatch, Harvest, GrowBatchStatus
from app.models.seed import Seed, SeedBatch

router = APIRouter(tags=["Analytics"])

@router.get("/revenue")
def get_revenue_stats(db: DBSession, months: int = 12) -> List[Dict[str, Any]]:
    """
    Returns monthly revenue aggregation by customer type (Netto).
    """
    # Start date
    start_date = date.today().replace(day=1) - timedelta(days=months*30)
    
    # Query
    results = db.execute(
        select(
            func.to_char(Invoice.invoice_date, 'YYYY-MM').label("month"),
            Customer.typ.label("customer_type"),
            func.sum(Invoice.subtotal).label("revenue")
        )
        .join(Customer, Invoice.customer_id == Customer.id)
        .where(
            Invoice.invoice_date >= start_date,
            Invoice.status.in_([InvoiceStatus.OFFEN, InvoiceStatus.BEZAHLT])
        )
        .group_by("month", Customer.typ)
        .order_by("month")
    ).all()
    
    # Transform to list of dicts
    data = []
    for row in results:
        data.append({
            "month": row.month,
            "customer_type": row.customer_type,
            "revenue": row.revenue
        })
        
    return data

@router.get("/yield")
def get_yield_stats(db: DBSession) -> List[Dict[str, Any]]:
    """
    Returns yield efficiency per seed variety.
    Efficiency = (Actual Harvest per Tray / Expected Harvest per Tray) * 100
    """
    # 1. Total Harvest per Variety
    # Join Harvest -> GrowBatch -> SeedBatch -> Seed
    
    results = db.execute(
        select(
            Seed.name,
            func.sum(Harvest.menge_gramm).label("total_harvest"),
            func.sum(GrowBatch.tray_anzahl).label("total_trays"),
            func.avg(Seed.ertrag_gramm_pro_tray).label("expected_per_tray")
        )
        .join(GrowBatch, Harvest.grow_batch_id == GrowBatch.id)
        .join(SeedBatch, GrowBatch.seed_batch_id == SeedBatch.id)
        .join(Seed, SeedBatch.seed_id == Seed.id)
        .group_by(Seed.id, Seed.name)
    ).all()
    
    data = []
    for row in results:
        if row.total_trays > 0 and row.expected_per_tray > 0:
            actual_per_tray = row.total_harvest / row.total_trays
            efficiency = (actual_per_tray / row.expected_per_tray) * 100
            
            data.append({
                "variety": row.name,
                "total_harvest_kg": round(row.total_harvest / 1000, 2),
                "avg_yield_per_tray": round(actual_per_tray, 2),
                "expected_yield": round(row.expected_per_tray, 2),
                "efficiency_percent": round(efficiency, 1)
            })
            
    return data
