"""
Pydantic Schemas für Bestellungen
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from app.models.order import OrderStatus


class OrderItemBase(BaseModel):
    """Basis-Schema für Bestellposition"""
    menge: Decimal = Field(..., gt=0, description="Bestellmenge")
    einheit: str = Field(..., description="Einheit (GRAMM, BUND, SCHALE)")
    preis_pro_einheit: Decimal | None = Field(None, ge=0, description="Stückpreis")


class OrderItemCreate(OrderItemBase):
    """Schema zum Erstellen einer Bestellposition"""
    seed_id: UUID = Field(..., description="Produkt-ID")


class OrderItemResponse(OrderItemBase):
    """Schema für Bestellposition-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    seed_id: UUID
    harvest_id: UUID | None
    created_at: datetime

    # Berechnete Felder
    positionswert: Decimal

    # Expandierte Felder
    seed_name: str | None = None


class OrderBase(BaseModel):
    """Basis-Schema für Bestellung"""
    liefer_datum: date = Field(..., description="Gewünschtes Lieferdatum")
    notizen: str | None = Field(None, description="Zusätzliche Notizen")


class OrderCreate(OrderBase):
    """Schema zum Erstellen einer Bestellung"""
    kunde_id: UUID = Field(..., description="Kunden-ID")
    positionen: list[OrderItemCreate] = Field(..., min_length=1, description="Bestellpositionen")


class OrderUpdate(BaseModel):
    """Schema zum Aktualisieren einer Bestellung"""
    liefer_datum: date | None = None
    status: OrderStatus | None = None
    notizen: str | None = None


class OrderResponse(OrderBase):
    """Schema für Bestell-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kunde_id: UUID
    bestell_datum: datetime
    status: OrderStatus
    created_at: datetime
    updated_at: datetime

    # Berechnete Felder
    gesamtwert: Decimal

    # Expandierte Felder
    kunde_name: str | None = None
    positionen: list[OrderItemResponse] = []


class OrderListResponse(BaseModel):
    """Schema für Bestell-Liste"""
    items: list[OrderResponse]
    total: int
