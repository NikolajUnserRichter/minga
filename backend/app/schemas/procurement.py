"""Pydantic-Schemas für Einkauf/Wareneingang (Procurement)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.invoice import TaxRate
from app.models.procurement import PurchaseOrderStatus


# ---------- Positionen ----------

class PurchaseOrderLineCreate(BaseModel):
    product_id: Optional[UUID] = None
    product_sku: Optional[str] = None
    beschreibung: Optional[str] = None
    quantity: Decimal = Field(..., gt=0)
    unit: str
    unit_price: Decimal = Field(..., ge=0)
    tax_rate: TaxRate = TaxRate.STANDARD
    discount_percent: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)


class PurchaseOrderLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    product_id: Optional[UUID]
    product_sku: Optional[str]
    beschreibung: Optional[str]
    quantity: Decimal
    unit: str
    quantity_received: Decimal
    quantity_open: Decimal
    is_fully_received: bool
    unit_price: Decimal
    tax_rate: TaxRate
    discount_percent: Decimal
    line_net: Decimal
    line_vat: Decimal
    line_gross: Decimal
    # Marge gegen den Verkaufspreis des Produkts (falls verknüpft)
    margin_per_unit: Optional[Decimal] = None
    margin_percent: Optional[Decimal] = None


# ---------- Kopf ----------

class PurchaseOrderCreate(BaseModel):
    supplier_id: UUID
    supplier_reference: Optional[str] = None
    requested_delivery_date: Optional[date] = None
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    discount_percent: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    currency: str = "EUR"
    lines: list[PurchaseOrderLineCreate] = Field(default_factory=list)


class PurchaseOrderUpdate(BaseModel):
    supplier_reference: Optional[str] = None
    requested_delivery_date: Optional[date] = None
    confirmed_delivery_date: Optional[date] = None
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    status: Optional[PurchaseOrderStatus] = None


class PurchaseOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    po_number: str
    supplier_id: UUID
    supplier_name: Optional[str] = None
    supplier_reference: Optional[str]
    status: PurchaseOrderStatus
    order_date: datetime
    requested_delivery_date: Optional[date]
    confirmed_delivery_date: Optional[date]
    total_net: Decimal
    total_vat: Decimal
    total_gross: Decimal
    discount_percent: Decimal
    discount_amount: Decimal
    currency: str
    notes: Optional[str]
    internal_notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    lines: list[PurchaseOrderLineResponse] = Field(default_factory=list)


class PurchaseOrderListItem(BaseModel):
    """Schlanke Listenansicht ohne Positionen."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    po_number: str
    supplier_id: UUID
    supplier_name: Optional[str] = None
    status: PurchaseOrderStatus
    order_date: datetime
    requested_delivery_date: Optional[date]
    total_gross: Decimal
    currency: str


class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderListItem]
    total: int


# ---------- Wareneingang ----------

class GoodsReceiptLine(BaseModel):
    line_id: UUID
    quantity: Decimal = Field(..., gt=0)


class GoodsReceiptRequest(BaseModel):
    receipts: list[GoodsReceiptLine] = Field(..., min_length=1)


# ---------- Handelsware-Bestand ----------

class TradeGoodsStockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    sku: Optional[str]
    name: Optional[str]
    quantity_on_hand: Decimal
    unit: str
    last_purchase_price: Optional[Decimal]
    stock_value: Optional[Decimal] = None
    updated_at: datetime


class TradeGoodsStockListResponse(BaseModel):
    items: list[TradeGoodsStockResponse]
    total: int
