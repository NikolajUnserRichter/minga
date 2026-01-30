from datetime import date
from typing import List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.api.deps import DBSession
from app.models.order import Order, OrderLine, OrderStatus

router = APIRouter(tags=["Produktion"])

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
