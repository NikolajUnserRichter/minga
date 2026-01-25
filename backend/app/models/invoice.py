"""
Rechnungs-Models: Invoice, InvoiceLine und Payment
Mit deutscher MwSt-Berechnung und DATEV-Export-Feldern
"""
import uuid
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional
from sqlalchemy import String, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class InvoiceStatus(str, Enum):
    """Rechnungsstatus"""
    ENTWURF = "ENTWURF"           # Noch nicht gesendet
    OFFEN = "OFFEN"               # Gesendet, wartet auf Zahlung
    TEILBEZAHLT = "TEILBEZAHLT"   # Teilweise bezahlt
    BEZAHLT = "BEZAHLT"           # Vollständig bezahlt
    UEBERFAELLIG = "UEBERFAELLIG" # Zahlungsziel überschritten
    STORNIERT = "STORNIERT"       # Storniert/Gutschrift
    MAHNVERFAHREN = "MAHNVERFAHREN"  # Im Mahnverfahren


class InvoiceType(str, Enum):
    """Rechnungstyp"""
    RECHNUNG = "RECHNUNG"         # Normale Rechnung
    GUTSCHRIFT = "GUTSCHRIFT"     # Gutschrift/Stornorechnung
    PROFORMA = "PROFORMA"         # Proforma-Rechnung
    ABSCHLAG = "ABSCHLAG"         # Abschlagsrechnung


class TaxRate(str, Enum):
    """Deutsche MwSt-Sätze"""
    STANDARD = "STANDARD"         # 19%
    REDUZIERT = "REDUZIERT"       # 7% (Lebensmittel)
    STEUERFREI = "STEUERFREI"     # 0% (z.B. EU-Lieferungen)

    @property
    def rate(self) -> Decimal:
        """Steuersatz als Dezimalzahl"""
        rates = {
            TaxRate.STANDARD: Decimal("0.19"),
            TaxRate.REDUZIERT: Decimal("0.07"),
            TaxRate.STEUERFREI: Decimal("0.00"),
        }
        return rates.get(self, Decimal("0.19"))

    @property
    def percent(self) -> int:
        """Steuersatz als Prozent"""
        percents = {
            TaxRate.STANDARD: 19,
            TaxRate.REDUZIERT: 7,
            TaxRate.STEUERFREI: 0,
        }
        return percents.get(self, 19)


class PaymentMethod(str, Enum):
    """Zahlungsmethode"""
    UEBERWEISUNG = "UEBERWEISUNG"  # Banküberweisung
    BAR = "BAR"                    # Barzahlung
    EC = "EC"                      # EC-Karte
    KREDITKARTE = "KREDITKARTE"   # Kreditkarte
    PAYPAL = "PAYPAL"             # PayPal
    LASTSCHRIFT = "LASTSCHRIFT"   # SEPA-Lastschrift


class Invoice(Base):
    """
    Rechnung - Vollständige deutsche Rechnung mit MwSt und DATEV-Feldern
    """
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Rechnungsnummer (fortlaufend, Format: RE-2026-00001)
    invoice_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )

    # Rechnungstyp
    invoice_type: Mapped[InvoiceType] = mapped_column(
        SQLEnum(InvoiceType), default=InvoiceType.RECHNUNG
    )

    # Referenz auf Originalrechnung (bei Gutschrift)
    original_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL")
    )

    # Kunde
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )

    # Bestellung (optional, Rechnung kann auch ohne Bestellung erstellt werden)
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL")
    )

    # Datum
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    delivery_date: Mapped[date | None] = mapped_column(Date)  # Liefer-/Leistungsdatum
    due_date: Mapped[date] = mapped_column(Date, nullable=False)  # Fälligkeitsdatum

    # Status
    status: Mapped[InvoiceStatus] = mapped_column(
        SQLEnum(InvoiceStatus), default=InvoiceStatus.ENTWURF
    )

    # Adressen (als Snapshot zum Rechnungszeitpunkt)
    billing_address: Mapped[dict | None] = mapped_column(JSONB)
    shipping_address: Mapped[dict | None] = mapped_column(JSONB)

    # Beträge (werden bei Speichern berechnet)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))  # Netto
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))  # MwSt
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))  # Brutto

    # Rabatt auf Gesamtrechnung
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    # Bezahlt
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    # Währung
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    # DATEV-Felder
    datev_exported: Mapped[bool] = mapped_column(Boolean, default=False)
    datev_export_date: Mapped[datetime | None] = mapped_column(DateTime)
    buchungskonto: Mapped[str | None] = mapped_column(String(10))  # Erlöskonto (z.B. 8400)

    # Notizen
    header_text: Mapped[str | None] = mapped_column(Text)  # Text vor Positionen
    footer_text: Mapped[str | None] = mapped_column(Text)  # Text nach Positionen
    internal_notes: Mapped[str | None] = mapped_column(Text)  # Interne Notizen

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)  # Wann versendet

    # Beziehungen
    customer: Mapped["Customer"] = relationship("Customer", back_populates="invoices")
    order: Mapped[Optional["Order"]] = relationship("Order")
    original_invoice: Mapped[Optional["Invoice"]] = relationship(
        "Invoice", remote_side=[id], foreign_keys=[original_invoice_id]
    )
    lines: Mapped[list["InvoiceLine"]] = relationship(
        "InvoiceLine", back_populates="invoice", cascade="all, delete-orphan",
        order_by="InvoiceLine.position"
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="invoice", cascade="all, delete-orphan"
    )

    def calculate_totals(self) -> None:
        """Berechnet Zwischensumme, MwSt und Gesamtbetrag"""
        subtotal = Decimal("0")
        tax_by_rate: dict[TaxRate, Decimal] = {}

        for line in self.lines:
            line_total = line.calculate_line_total()
            subtotal += line_total

            # MwSt nach Satz gruppieren
            tax_rate = line.tax_rate
            if tax_rate not in tax_by_rate:
                tax_by_rate[tax_rate] = Decimal("0")
            tax_by_rate[tax_rate] += line_total

        # Rabatt anwenden
        if self.discount_percent > 0:
            self.discount_amount = (subtotal * self.discount_percent / 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            subtotal -= self.discount_amount

        self.subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # MwSt berechnen (nach Rabatt)
        total_tax = Decimal("0")
        for tax_rate, base_amount in tax_by_rate.items():
            # Rabatt proportional verteilen
            if self.discount_percent > 0:
                base_amount -= base_amount * self.discount_percent / 100
            tax = base_amount * tax_rate.rate
            total_tax += tax

        self.tax_amount = total_tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.total = (self.subtotal + self.tax_amount).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def remaining_amount(self) -> Decimal:
        """Offener Betrag"""
        return (self.total - self.paid_amount).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def is_paid(self) -> bool:
        """Rechnung vollständig bezahlt?"""
        return self.paid_amount >= self.total

    @property
    def is_overdue(self) -> bool:
        """Rechnung überfällig?"""
        if self.status in (InvoiceStatus.BEZAHLT, InvoiceStatus.STORNIERT):
            return False
        return date.today() > self.due_date

    def get_tax_summary(self) -> list[dict]:
        """MwSt-Zusammenfassung für Rechnung"""
        tax_by_rate: dict[TaxRate, dict] = {}

        for line in self.lines:
            line_total = line.calculate_line_total()
            rate = line.tax_rate

            if rate not in tax_by_rate:
                tax_by_rate[rate] = {
                    "rate": rate,
                    "percent": rate.percent,
                    "base": Decimal("0"),
                    "tax": Decimal("0"),
                }

            # Rabatt proportional
            if self.discount_percent > 0:
                line_total -= line_total * self.discount_percent / 100

            tax_by_rate[rate]["base"] += line_total
            tax_by_rate[rate]["tax"] += line_total * rate.rate

        # Runden
        result = []
        for data in tax_by_rate.values():
            data["base"] = data["base"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            data["tax"] = data["tax"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            result.append(data)

        return result

    def __repr__(self) -> str:
        return f"<Invoice(number='{self.invoice_number}', total={self.total})>"


class InvoiceLine(Base):
    """
    Rechnungsposition - Einzelne Zeile auf der Rechnung
    """
    __tablename__ = "invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )

    # Position auf der Rechnung
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Produkt (optional, kann auch Freitext sein)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL")
    )

    # Artikelbeschreibung (Snapshot oder Freitext)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[str | None] = mapped_column(String(50))  # Artikelnummer

    # Menge und Einheit
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # kg, Stk, Schale

    # Preise
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)  # Einzelpreis netto
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))

    # MwSt
    tax_rate: Mapped[TaxRate] = mapped_column(
        SQLEnum(TaxRate), default=TaxRate.REDUZIERT  # Lebensmittel = 7%
    )

    # Berechneter Zeilenbetrag (netto, nach Rabatt)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    # Referenz auf Order-Item (für Rückverfolgung)
    order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("order_items.id", ondelete="SET NULL")
    )

    # Chargen-Referenz (für Rückverfolgbarkeit)
    harvest_batch_ids: Mapped[list | None] = mapped_column(JSONB)  # Liste von Harvest-IDs

    # DATEV
    buchungskonto: Mapped[str | None] = mapped_column(String(10))  # Erlöskonto

    # Beziehungen
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="lines")
    product: Mapped[Optional["Product"]] = relationship("Product")

    def calculate_line_total(self) -> Decimal:
        """Berechnet Zeilenbetrag (netto, nach Positionsrabatt)"""
        total = self.quantity * self.unit_price
        if self.discount_percent > 0:
            total -= total * self.discount_percent / 100
        self.line_total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return self.line_total

    @property
    def tax_amount(self) -> Decimal:
        """MwSt-Betrag dieser Position"""
        return (self.line_total * self.tax_rate.rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def gross_total(self) -> Decimal:
        """Brutto-Zeilenbetrag"""
        return self.line_total + self.tax_amount

    def __repr__(self) -> str:
        return f"<InvoiceLine(pos={self.position}, desc='{self.description[:30]}...')>"


class Payment(Base):
    """
    Zahlung - Zahlungseingänge zu Rechnungen
    """
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )

    # Zahlungsdaten
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        SQLEnum(PaymentMethod), default=PaymentMethod.UEBERWEISUNG
    )

    # Referenz
    reference: Mapped[str | None] = mapped_column(String(100))  # Überweisungsreferenz
    bank_reference: Mapped[str | None] = mapped_column(String(100))  # Bank-Transaktions-ID

    # Notizen
    notes: Mapped[str | None] = mapped_column(Text)

    # DATEV
    datev_exported: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Beziehungen
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")

    def __repr__(self) -> str:
        return f"<Payment(amount={self.amount}, date={self.payment_date})>"


# Hilfsfunktion für Rechnungsnummer-Generierung
def generate_invoice_number(year: int, sequence: int, prefix: str = "RE") -> str:
    """
    Generiert eine fortlaufende Rechnungsnummer.
    Format: RE-2026-00001
    """
    return f"{prefix}-{year}-{sequence:05d}"


# Standard-Buchungskonten (SKR03)
STANDARD_ACCOUNTS = {
    "erloes_7": "8300",      # Erlöse 7% USt
    "erloes_19": "8400",     # Erlöse 19% USt
    "erloes_steuerfrei": "8100",  # Steuerfreie Erlöse
    "forderungen": "1400",   # Forderungen aus L+L
    "bank": "1200",          # Bank
    "kasse": "1000",         # Kasse
}


# Imports für Type Hints
from app.models.customer import Customer
from app.models.order import Order
from app.models.product import Product
