from typing import Optional
"""
Pydantic Schemas für Rechnungen (Invoices)
Mit deutscher MwSt-Berechnung und DATEV-Export
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from app.models.invoice import InvoiceStatus, InvoiceType, TaxRate, PaymentMethod


# ============================================================
# INVOICE LINE SCHEMAS
# ============================================================

class InvoiceLineBase(BaseModel):
    """Basis-Schema für Rechnungsposition"""
    description: str = Field(..., min_length=1, description="Artikelbeschreibung")
    sku: Optional[str] = Field(None, max_length=50, description="Artikelnummer")
    quantity: Decimal = Field(..., gt=0, description="Menge")
    unit: str = Field(..., description="Einheit")
    unit_price: Decimal = Field(..., ge=0, description="Einzelpreis (netto)")
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Rabatt %")
    tax_rate: TaxRate = Field(default=TaxRate.REDUZIERT, description="MwSt-Satz")


class InvoiceLineCreate(InvoiceLineBase):
    """Schema zum Erstellen einer Rechnungsposition"""
    product_id: Optional[UUID] = Field(None, description="Produkt-ID")
    order_item_id: Optional[UUID] = Field(None, description="Bestellposition-ID")
    harvest_batch_ids: Optional[list[UUID]] = Field(None, description="Chargen-IDs für Rückverfolgung")
    buchungskonto: Optional[str] = Field(None, max_length=10, description="Erlöskonto (SKR03)")


class InvoiceLineUpdate(BaseModel):
    """Schema zum Aktualisieren einer Rechnungsposition"""
    description: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None
    discount_percent: Optional[Decimal] = None
    tax_rate: Optional[TaxRate] = None


class InvoiceLineResponse(InvoiceLineBase):
    """Schema für Rechnungsposition-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID
    position: int
    product_id: Optional[UUID]
    line_total: Decimal
    order_item_id: Optional[UUID]
    harvest_batch_ids: Optional[list[UUID]]
    buchungskonto: Optional[str]

    # Berechnete Felder
    tax_amount: Optional[Decimal] = None
    gross_total: Optional[Decimal] = None

    # Expandierte Felder
    product_name: Optional[str] = None


# ============================================================
# PAYMENT SCHEMAS
# ============================================================

class PaymentBase(BaseModel):
    """Basis-Schema für Zahlung"""
    payment_date: date = Field(..., description="Zahlungsdatum")
    amount: Decimal = Field(..., gt=0, description="Betrag")
    payment_method: PaymentMethod = Field(default=PaymentMethod.UEBERWEISUNG, description="Zahlungsart")
    reference: Optional[str] = Field(None, max_length=100, description="Verwendungszweck")
    bank_reference: Optional[str] = Field(None, max_length=100, description="Bank-Referenz")
    notes: Optional[str] = Field(None, description="Notizen")


class PaymentCreate(PaymentBase):
    """Schema zum Erstellen einer Zahlung"""
    invoice_id: UUID = Field(..., description="Rechnungs-ID")


class PaymentResponse(PaymentBase):
    """Schema für Zahlungs-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID
    datev_exported: bool
    created_at: datetime


class PaymentListResponse(BaseModel):
    """Schema für Zahlungen-Liste"""
    items: list[PaymentResponse]
    total: int


# ============================================================
# INVOICE SCHEMAS
# ============================================================

class InvoiceBase(BaseModel):
    """Basis-Schema für Rechnung"""
    invoice_type: InvoiceType = Field(default=InvoiceType.RECHNUNG, description="Rechnungstyp")
    invoice_date: date = Field(..., description="Rechnungsdatum")
    delivery_date: Optional[date] = Field(None, description="Liefer-/Leistungsdatum")
    due_date: Optional[date] = Field(None, description="Fälligkeitsdatum")


class InvoiceCreate(InvoiceBase):
    """Schema zum Erstellen einer Rechnung"""
    customer_id: UUID = Field(..., description="Kunden-ID")
    order_id: Optional[UUID] = Field(None, description="Bestellungs-ID")
    original_invoice_id: Optional[UUID] = Field(None, description="Original-Rechnung (bei Gutschrift)")

    # Adressen (optional, werden sonst vom Kunden übernommen)
    billing_address: Optional[dict] = Field(None, description="Rechnungsadresse")
    shipping_address: Optional[dict] = Field(None, description="Lieferadresse")

    # Rabatt
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Gesamtrabatt %")

    # Texte
    header_text: Optional[str] = Field(None, description="Kopftext")
    footer_text: Optional[str] = Field(None, description="Fußtext")
    internal_notes: Optional[str] = Field(None, description="Interne Notizen")

    # DATEV
    buchungskonto: Optional[str] = Field(None, max_length=10, description="Erlöskonto")

    # Positionen
    lines: list[InvoiceLineCreate] = Field(default=[], description="Rechnungspositionen")


class InvoiceUpdate(BaseModel):
    """Schema zum Aktualisieren einer Rechnung"""
    invoice_date: Optional[date] = None
    delivery_date: Optional[date] = None
    due_date: Optional[date] = None
    status: Optional[InvoiceStatus] = None
    discount_percent: Optional[Decimal] = None
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    internal_notes: Optional[str] = None
    buchungskonto: Optional[str] = None


class InvoiceResponse(InvoiceBase):
    """Schema für Rechnungs-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_number: str
    customer_id: UUID
    order_id: Optional[UUID]
    original_invoice_id: Optional[UUID]
    status: InvoiceStatus

    # Adressen
    billing_address: Optional[dict]
    shipping_address: Optional[dict]

    # Beträge
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    discount_percent: Decimal
    discount_amount: Decimal
    paid_amount: Decimal
    currency: str

    # DATEV
    datev_exported: bool
    datev_export_date: Optional[datetime]
    buchungskonto: Optional[str]

    # Texte
    header_text: Optional[str]
    footer_text: Optional[str]
    internal_notes: Optional[str]

    # Timestamps
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime]

    # Berechnete Felder
    remaining_amount: Optional[Decimal] = None
    is_paid: Optional[bool] = None
    is_overdue: Optional[bool] = None

    # Expandierte Felder
    customer_name: Optional[str] = None
    customer_number: Optional[str] = None


class InvoiceDetailResponse(InvoiceResponse):
    """Detailliertes Rechnungs-Schema mit Positionen und Zahlungen"""
    lines: list[InvoiceLineResponse] = []
    payments: list[PaymentResponse] = []
    tax_summary: Optional[list[dict]] = None


class InvoiceListResponse(BaseModel):
    """Schema für Rechnungs-Liste"""
    items: list[InvoiceResponse]
    total: int
    total_amount: Optional[Decimal] = None
    total_paid: Optional[Decimal] = None
    total_open: Optional[Decimal] = None


# ============================================================
# INVOICE ACTIONS
# ============================================================

class InvoiceSendRequest(BaseModel):
    """Request zum Versenden einer Rechnung"""
    send_email: bool = Field(default=True, description="Per E-Mail senden?")
    email_to: Optional[str] = Field(None, description="Empfänger-E-Mail (optional)")
    email_cc: Optional[list[str]] = Field(None, description="CC-Empfänger")
    email_subject: Optional[str] = Field(None, description="Betreff (optional)")
    email_body: Optional[str] = Field(None, description="E-Mail-Text (optional)")


class InvoiceCancelRequest(BaseModel):
    """Request zum Stornieren einer Rechnung"""
    reason: str = Field(..., min_length=1, description="Stornogrund")
    create_credit_note: bool = Field(default=True, description="Gutschrift erstellen?")


class DatevExportRequest(BaseModel):
    """Request für DATEV-Export"""
    from_date: date = Field(..., description="Von Datum")
    to_date: date = Field(..., description="Bis Datum")
    include_payments: bool = Field(default=True, description="Zahlungen einschließen?")


class DatevExportResponse(BaseModel):
    """Response für DATEV-Export"""
    filename: str
    record_count: int
    total_amount: Decimal
    export_date: datetime
    csv_content: Optional[str] = None  # Optional, für direkten Download
