"""Pricing-Lookup: Customer-spezifischer Preis vor Default-Preis.

Aufruf-Beispiel (in sales.create_order):
    price = resolve_unit_price(
        db, customer_id=order.customer_id, product_id=line.product_id,
        default=product.base_price, on_date=date.today()
    )
"""
from __future__ import annotations

from datetime import date as _date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session

from app.models.customer_price import CustomerPrice


def get_customer_price(
    db: Session,
    customer_id: UUID,
    product_id: UUID,
    on_date: Optional[_date] = None,
) -> Optional[CustomerPrice]:
    """Liefert den aktuell gültigen Customer-Price oder None."""
    if on_date is None:
        on_date = _date.today()
    row = db.execute(
        select(CustomerPrice).where(
            CustomerPrice.customer_id == customer_id,
            CustomerPrice.product_id == product_id,
            CustomerPrice.valid_from <= on_date,
            or_(
                CustomerPrice.valid_until.is_(None),
                CustomerPrice.valid_until >= on_date,
            ),
        )
        .order_by(CustomerPrice.valid_from.desc())
        .limit(1)
    ).scalar_one_or_none()
    return row


def resolve_unit_price(
    db: Session,
    customer_id: UUID,
    product_id: UUID,
    default: Optional[Decimal],
    on_date: Optional[_date] = None,
) -> tuple[Decimal, bool]:
    """Gibt (preis, ist_customer_specific) zurück. Default-Preis wird genutzt,
    wenn kein Customer-Eintrag existiert."""
    cp = get_customer_price(db, customer_id, product_id, on_date)
    if cp is not None:
        return cp.unit_price, True
    return (default or Decimal("0")), False
