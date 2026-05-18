"""Pydantic-Schemas für die Belegkette."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ConfirmationStatus, DeliveryNoteStatus


# ==================== AUFTRAGSBESTÄTIGUNG ====================

class OrderConfirmationCreate(BaseModel):
    notes: Optional[str] = None


class OrderConfirmationSend(BaseModel):
    sent_to_email: Optional[str] = Field(None, description="Empfänger-Email (falls per Email versendet)")


class OrderConfirmationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    confirmation_number: str
    status: ConfirmationStatus
    issued_at: datetime
    sent_at: Optional[datetime]
    sent_to_email: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


# ==================== LIEFERSCHEIN ====================

class PackingListItemCreate(BaseModel):
    order_line_id: Optional[UUID] = None
    product_name: str
    quantity: Decimal = Field(..., gt=0)
    unit: str
    batch_number: Optional[str] = None
    harvest_id: Optional[UUID] = None
    is_returnable_container: bool = False
    container_type: Optional[str] = None
    container_count: Optional[int] = Field(None, ge=1)
    sort_order: int = 0


class PackingListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_line_id: Optional[UUID]
    sort_order: int
    product_name: str
    quantity: Decimal
    unit: str
    batch_number: Optional[str]
    harvest_id: Optional[UUID]
    is_returnable_container: bool
    container_type: Optional[str]
    container_count: Optional[int]


class PackingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    delivery_note_id: UUID
    packing_list_number: str
    total_weight_g: Optional[Decimal]
    total_packages: Optional[int]
    notes: Optional[str]
    items: list[PackingListItemResponse] = []
    created_at: datetime
    updated_at: datetime


class DeliveryNoteCreate(BaseModel):
    """Anlage eines Lieferscheins.

    Falls keine packing_items angegeben werden, werden automatisch aus
    den Order-Lines übernommen (1:1, ohne Pfand-Erweiterungen)."""
    notes: Optional[str] = None
    packing_items: Optional[list[PackingListItemCreate]] = None
    total_weight_g: Optional[Decimal] = None
    total_packages: Optional[int] = None


class DeliveryNoteMarkDelivered(BaseModel):
    signed_by: Optional[str] = None
    actual_delivery_date: Optional[date] = None


class DeliveryNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    delivery_note_number: str
    status: DeliveryNoteStatus
    issued_at: datetime
    delivered_at: Optional[datetime]
    signed_by: Optional[str]
    actual_delivery_date: Optional[date]
    notes: Optional[str]
    packing_list: Optional[PackingListResponse] = None
    created_at: datetime
    updated_at: datetime
