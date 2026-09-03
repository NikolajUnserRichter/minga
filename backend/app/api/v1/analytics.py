from collections import defaultdict
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

    # Nach Monat gruppiert wird in Python, nicht in SQL: to_char() gibt es nur
    # in Postgres, jeder Mandant läuft aber auf SQLite — die Auswertung lief
    # deshalb immer in einen 500er. Die Rechnungsmengen sind klein genug, dass
    # sich eine dialektabhängige Datumsfunktion nicht lohnt.
    rows = db.execute(
        select(
            Invoice.invoice_date,
            Customer.typ.label("customer_type"),
            Invoice.subtotal,
        )
        .join(Customer, Invoice.customer_id == Customer.id)
        .where(
            Invoice.invoice_date >= start_date,
            Invoice.status.in_([InvoiceStatus.OFFEN, InvoiceStatus.BEZAHLT])
        )
    ).all()

    summen: Dict[tuple, Decimal] = defaultdict(Decimal)
    for invoice_date, customer_type, subtotal in rows:
        monat = invoice_date.strftime("%Y-%m")
        typ = customer_type.value if hasattr(customer_type, "value") else customer_type
        summen[(monat, typ)] += Decimal(str(subtotal or 0))

    # Aufsteigend nach Monat — das Diagramm zeichnet in dieser Reihenfolge.
    return [
        {"month": monat, "customer_type": typ, "revenue": betrag}
        for (monat, typ), betrag in sorted(summen.items())
    ]

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
        # Stück-Ernten haben kein Gewicht (menge_gramm=0) und würden die
        # g-basierte Effizienz fälschlich gegen 0 ziehen
        .where(Harvest.einheit == "G")
        .group_by(Seed.id, Seed.name)
    ).all()

    data = []
    for row in results:
        if row.total_harvest and row.total_trays > 0 and row.expected_per_tray > 0:
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
