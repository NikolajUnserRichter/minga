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
    sku: str | None = Field(None, max_length=50, description="Artikelnummer")
    quantity: Decimal = Field(..., gt=0, description="Menge")
    unit: str = Field(..., description="Einheit")
    unit_price: Decimal = Field(..., ge=0, description="Einzelpreis (netto)")
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Rabatt %")
    tax_rate: TaxRate = Field(default=TaxRate.REDUZIERT, description="MwSt-Satz")


class InvoiceLineCreate(InvoiceLineBase):
    """Schema zum Erstellen einer Rechnungsposition"""
    product_id: UUID | None = Field(None, description="Produkt-ID")
    order_item_id: UUID | None = Field(None, description="Bestellposition-ID")
    harvest_batch_ids: list[UUID] | None = Field(None, description="Chargen-IDs für Rückverfolgung")
    buchungskonto: str | None = Field(None, max_length=10, description="Erlöskonto (SKR03)")


class InvoiceLineUpdate(BaseModel):
    """Schema zum Aktualisieren einer Rechnungsposition"""
    description: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    discount_percent: Decimal | None = None
    tax_rate: TaxRate | None = None


class InvoiceLineResponse(InvoiceLineBase):
    """Schema für Rechnungsposition-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID
    position: int
    product_id: UUID | None
    line_total: Decimal
    order_item_id: UUID | None
    harvest_batch_ids: list[UUID] | None
    buchungskonto: str | None

    # Berechnete Felder
    tax_amount: Decimal | None = None
    gross_total: Decimal | None = None

    # Expandierte Felder
    product_name: str | None = None


# ============================================================
# PAYMENT SCHEMAS
# ============================================================

class PaymentBase(BaseModel):
    """Basis-Schema für Zahlung"""
    payment_date: date = Field(..., description="Zahlungsdatum")
    amount: Decimal = Field(..., gt=0, description="Betrag")
    payment_method: PaymentMethod = Field(default=PaymentMethod.UEBERWEISUNG, description="Zahlungsart")
    reference: str | None = Field(None, max_length=100, description="Verwendungszweck")
    bank_reference: str | None = Field(None, max_length=100, description="Bank-Referenz")
    notes: str | None = Field(None, description="Notizen")


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
    delivery_date: date | None = Field(None, description="Liefer-/Leistungsdatum")
    due_date: date = Field(..., description="Fälligkeitsdatum")


class InvoiceCreate(InvoiceBase):
    """Schema zum Erstellen einer Rechnung"""
    customer_id: UUID = Field(..., description="Kunden-ID")
    order_id: UUID | None = Field(None, description="Bestellungs-ID")
    original_invoice_id: UUID | None = Field(None, description="Original-Rechnung (bei Gutschrift)")

    # Adressen (optional, werden sonst vom Kunden übernommen)
    billing_address: dict | None = Field(None, description="Rechnungsadresse")
    shipping_address: dict | None = Field(None, description="Lieferadresse")

    # Rabatt
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Gesamtrabatt %")

    # Texte
    header_text: str | None = Field(None, description="Kopftext")
    footer_text: str | None = Field(None, description="Fußtext")
    internal_notes: str | None = Field(None, description="Interne Notizen")

    # DATEV
    buchungskonto: str | None = Field(None, max_length=10, description="Erlöskonto")

    # Positionen
    lines: list[InvoiceLineCreate] = Field(default=[], description="Rechnungspositionen")


class InvoiceUpdate(BaseModel):
    """Schema zum Aktualisieren einer Rechnung"""
    invoice_date: date | None = None
    delivery_date: date | None = None
    due_date: date | None = None
    status: InvoiceStatus | None = None
    discount_percent: Decimal | None = None
    header_text: str | None = None
    footer_text: str | None = None
    internal_notes: str | None = None
    buchungskonto: str | None = None


class InvoiceResponse(InvoiceBase):
    """Schema für Rechnungs-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_number: str
    customer_id: UUID
    order_id: UUID | None
    original_invoice_id: UUID | None
    status: InvoiceStatus

    # Adressen
    billing_address: dict | None
    shipping_address: dict | None

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
    datev_export_date: datetime | None
    buchungskonto: str | None

    # Texte
    header_text: str | None
    footer_text: str | None
    internal_notes: str | None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None

    # Berechnete Felder
    remaining_amount: Decimal | None = None
    is_paid: bool | None = None
    is_overdue: bool | None = None

    # Expandierte Felder
    customer_name: str | None = None
    customer_number: str | None = None


class InvoiceDetailResponse(InvoiceResponse):
    """Detailliertes Rechnungs-Schema mit Positionen und Zahlungen"""
    lines: list[InvoiceLineResponse] = []
    payments: list[PaymentResponse] = []
    tax_summary: list[dict] | None = None


class InvoiceListResponse(BaseModel):
    """Schema für Rechnungs-Liste"""
    items: list[InvoiceResponse]
    total: int
    total_amount: Decimal | None = None
    total_paid: Decimal | None = None
    total_open: Decimal | None = None


# ============================================================
# INVOICE ACTIONS
# ============================================================

class InvoiceSendRequest(BaseModel):
    """Request zum Versenden einer Rechnung"""
    send_email: bool = Field(default=True, description="Per E-Mail senden?")
    email_to: str | None = Field(None, description="Empfänger-E-Mail (optional)")
    email_cc: list[str] | None = Field(None, description="CC-Empfänger")
    email_subject: str | None = Field(None, description="Betreff (optional)")
    email_body: str | None = Field(None, description="E-Mail-Text (optional)")


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
    csv_content: str | None = None  # Optional, für direkten Download
