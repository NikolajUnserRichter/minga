"""Pydantic-Schemas für Customer-Pricing."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerPriceBase(BaseModel):
    product_id: UUID
    unit_price: Decimal = Field(..., ge=0)
    currency: str = "EUR"
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    notes: Optional[str] = None


class CustomerPriceCreate(CustomerPriceBase):
    pass


class CustomerPriceUpdate(BaseModel):
    unit_price: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    notes: Optional[str] = None


class CustomerPriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    product_id: UUID
    unit_price: Decimal
    currency: str
    valid_from: date
    valid_until: Optional[date]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    # Expandierte Felder (vom Endpoint angehängt)
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
