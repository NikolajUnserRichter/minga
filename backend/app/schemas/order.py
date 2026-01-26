"""
Pydantic Schemas für Bestellungen (Header-Line Architektur)
Vollständige ERP-konforme Implementierung.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional

from app.models.enums import OrderStatus, TaxRate


# ==================== ADDRESS SCHEMAS ====================

class AddressSchema(BaseModel):
    """Schema für Adressdaten"""
    name: Optional[str] = None
    strasse: str
    hausnummer: Optional[str] = None
    adresszusatz: Optional[str] = None
    plz: str
    ort: str
    land: str = "DE"


# ==================== ORDER LINE SCHEMAS ====================

class OrderLineBase(BaseModel):
    """Basis-Schema für Bestellposition"""
    product_name: str = Field(..., description="Produktbezeichnung")
    quantity: Decimal = Field(..., gt=0, description="Menge")
    unit: str = Field(..., description="Einheit (G, KG, STK, SCHALE)")
    unit_price: Decimal = Field(..., ge=0, description="Einzelpreis")
    tax_rate: TaxRate = Field(default=TaxRate.REDUZIERT, description="Steuersatz")
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Rabatt %")


class OrderLineCreate(OrderLineBase):
    """Schema zum Erstellen einer Bestellposition"""
    product_id: Optional[UUID] = Field(None, description="Produkt-ID")
    seed_id: Optional[UUID] = Field(None, description="Saatgut-ID (Legacy)")
    product_sku: Optional[str] = Field(None, description="Artikelnummer")
    product_description: Optional[str] = Field(None, description="Produktbeschreibung")
    requested_delivery_date: Optional[date] = Field(None, description="Abweichendes Lieferdatum")


class OrderLineUpdate(BaseModel):
    """Schema zum Aktualisieren einer Bestellposition"""
    product_name: Optional[str] = None
    quantity: Optional[Decimal] = Field(None, gt=0)
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = Field(None, ge=0)
    tax_rate: Optional[TaxRate] = None
    discount_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    requested_delivery_date: Optional[date] = None


class OrderLineResponse(BaseModel):
    """Schema für Bestellposition-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    position: int

    # Produkt
    product_id: Optional[UUID]
    seed_id: Optional[UUID]
    product_sku: Optional[str]
    product_name: str
    product_description: Optional[str]

    # Mengen & Preise
    quantity: Decimal
    unit: str
    unit_price: Decimal
    discount_percent: Decimal

    # Berechnete Beträge
    line_net: Decimal
    tax_rate: TaxRate
    line_vat: Decimal
    line_gross: Decimal

    # Lieferung
    requested_delivery_date: Optional[date]

    # Rückverfolgbarkeit
    harvest_id: Optional[UUID]
    batch_number: Optional[str]

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Legacy-Aliase für Rückwärtskompatibilität
    @property
    def menge(self) -> Decimal:
        return self.quantity

    @property
    def einheit(self) -> str:
        return self.unit

    @property
    def preis_pro_einheit(self) -> Decimal:
        return self.unit_price

    @property
    def positionswert(self) -> Decimal:
        return self.line_gross


# ==================== ORDER HEADER SCHEMAS ====================

class OrderBase(BaseModel):
    """Basis-Schema für Bestellung (Header)"""
    requested_delivery_date: date = Field(..., description="Gewünschtes Lieferdatum")
    customer_reference: Optional[str] = Field(None, description="Kundenbestellnummer")
    notes: Optional[str] = Field(None, description="Notizen")
    internal_notes: Optional[str] = Field(None, description="Interne Notizen")
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Gesamtrabatt %")
    confirmed_delivery_date: Optional[date] = Field(None, description="Bestätigtes Lieferdatum")


class OrderCreate(OrderBase):
    """Schema zum Erstellen einer Bestellung"""
    customer_id: UUID = Field(..., description="Kunden-ID")
    billing_address: Optional[AddressSchema] = Field(None, description="Rechnungsadresse")
    delivery_address: Optional[AddressSchema] = Field(None, description="Lieferadresse")
    currency: str = Field(default="EUR", description="Währung")
    lines: list[OrderLineCreate] = Field(default=[], description="Bestellpositionen")

    @field_validator('lines')
    @classmethod
    def validate_lines(cls, v):
        # Beim Erstellen sind Positionen optional, können später hinzugefügt werden
        return v


class OrderUpdate(BaseModel):
    """Schema zum Aktualisieren einer Bestellung"""
    requested_delivery_date: Optional[date] = None
    customer_reference: Optional[str] = None
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    discount_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    confirmed_delivery_date: Optional[date] = None
    billing_address: Optional[AddressSchema] = None
    delivery_address: Optional[AddressSchema] = None


class OrderStatusUpdate(BaseModel):
    """Schema für Statusänderung"""
    status: OrderStatus
    reason: Optional[str] = Field(None, description="Grund für Statusänderung")


class OrderResponse(BaseModel):
    """Schema für Bestell-Antwort (Header)"""
    model_config = ConfigDict(from_attributes=True)

    # Identifikation
    id: UUID
    order_number: str
    customer_id: UUID
    customer_reference: Optional[str]

    # Adressen
    billing_address: Optional[dict]
    delivery_address: Optional[dict]

    # Datum
    order_date: datetime
    requested_delivery_date: date
    confirmed_delivery_date: Optional[date] = None
    actual_delivery_date: Optional[date]

    # Status
    status: OrderStatus

    # Beträge
    currency: str
    total_net: Decimal
    total_vat: Decimal
    total_gross: Decimal
    discount_percent: Decimal
    discount_amount: Decimal

    # Notizen
    notes: Optional[str]
    internal_notes: Optional[str]

    # Audit
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID]

    # Rechnung
    invoice_id: Optional[UUID]

    # Positionen
    lines: list[OrderLineResponse] = []

    # Expandierte Felder
    customer_name: Optional[str] = None
    line_count: Optional[int] = None

    # Legacy-Aliase
    @property
    def kunde_id(self) -> UUID:
        return self.customer_id

    @property
    def liefer_datum(self) -> date:
        return self.requested_delivery_date

    @property
    def bestell_datum(self) -> datetime:
        return self.order_date

    @property
    def gesamtwert(self) -> Decimal:
        return self.total_gross

    @property
    def positionen(self) -> list[OrderLineResponse]:
        return self.lines


class OrderDetailResponse(OrderResponse):
    """Erweiterte Antwort mit allen Details"""
    audit_logs: list["OrderAuditLogResponse"] = []


# ==================== ORDER AUDIT LOG SCHEMAS ====================

class OrderAuditLogResponse(BaseModel):
    """Schema für Audit-Log-Einträge"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    action: str
    field_name: Optional[str]
    line_id: Optional[UUID]
    old_values: Optional[dict]
    new_values: Optional[dict]
    user_id: Optional[UUID]
    user_name: Optional[str]
    created_at: datetime
    reason: Optional[str]


# ==================== LIST SCHEMAS ====================

class OrderListResponse(BaseModel):
    """Schema für Bestell-Liste"""
    items: list[OrderResponse]
    total: int


class OrderSummary(BaseModel):
    """Zusammenfassung für Dashboard"""
    total_orders: int
    orders_by_status: dict[str, int]
    total_revenue_net: Decimal
    total_revenue_gross: Decimal
    orders_today: int
    orders_this_week: int


# ==================== BULK OPERATIONS ====================

class BulkStatusUpdate(BaseModel):
    """Schema für Massen-Statusänderung"""
    order_ids: list[UUID]
    status: OrderStatus
    reason: Optional[str] = None


class OrderFromSubscriptionCreate(BaseModel):
    """Schema zum Erstellen einer Bestellung aus Abonnement"""
    subscription_id: UUID
    delivery_date: date


# Forward reference update
OrderDetailResponse.model_rebuild()
