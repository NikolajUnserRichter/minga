from typing import Optional
"""
Bestell-Models: Order (Header) und OrderLine (Positionen)
Implementiert nach ERP-Standard mit vollständiger Header-Line Architektur.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from sqlalchemy import String, Integer, Numeric, DateTime, Date, ForeignKey, Text, Enum as SQLEnum, Boolean, event
from sqlalchemy.types import Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates


from app.database import Base


from app.models.enums import OrderStatus, TaxRate


class Order(Base):
    """
    Bestellung (Header) - Kundenauftrag mit allen ERP-Pflichtfeldern.

    Geschäftsregeln:
    - Eine Bestellung benötigt mindestens eine Position
    - Bestätigte Bestellungen werden auditiert
    - Löschen einer Bestellung löscht alle Positionen (Cascade)
    """
    __tablename__ = "orders"

    # ==================== IDENTIFIKATION ====================
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # Human-readable, sequentielle Bestellnummer (z.B. "ORD-2026-00001")
    order_number: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )

    # ==================== KUNDENREFERENZ ====================
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id"), nullable=False, index=True
    )

    # Kundenbestellnummer (externe Referenz vom Kunden)
    customer_reference: Mapped[Optional[str]] = mapped_column(String(100))

    # ==================== ADRESSEN (Snapshot bei Bestellung) ====================
    # Rechnungsadresse (JSON für Flexibilität)
    billing_address: Mapped[Optional[dict]] = mapped_column(JSON)
    # Lieferadresse
    delivery_address: Mapped[Optional[dict]] = mapped_column(JSON)

    # ==================== DATUM ====================
    order_date: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    requested_delivery_date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True
    )
    confirmed_delivery_date: Mapped[Optional[date]] = mapped_column(Date)
    actual_delivery_date: Mapped[Optional[date]] = mapped_column(Date)

    # ==================== STATUS ====================
    status: Mapped[OrderStatus] = mapped_column(
        SQLEnum(OrderStatus), default=OrderStatus.ENTWURF, index=True
    )

    # ==================== BETRÄGE ====================
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)

    # Netto (Summe aller Positionen ohne MwSt)
    total_net: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    # Mehrwertsteuer
    total_vat: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    # Brutto (Netto + MwSt)
    total_gross: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    # Rabatt auf Gesamtbestellung
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00")
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00")
    )

    # ==================== NOTIZEN ====================
    notes: Mapped[Optional[str]] = mapped_column(Text)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text)

    # ==================== AUDIT FIELDS ====================
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    # Verknüpfung zur Rechnung
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("invoices.id", ondelete="SET NULL", use_alter=True)
    )

    # ==================== BEZIEHUNGEN ====================
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    lines: Mapped[list["OrderLine"]] = relationship(
        "OrderLine",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderLine.position"
    )
    invoice: Mapped[Optional["Invoice"]] = relationship("Invoice", foreign_keys=[invoice_id])
    audit_logs: Mapped[list["OrderAuditLog"]] = relationship(
        "OrderAuditLog",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderAuditLog.created_at.desc()"
    )

    # Legacy-Beziehung für Kompatibilität
    @property
    def positionen(self) -> list["OrderLine"]:
        """Legacy-Alias für lines"""
        return self.lines

    @property
    def kunde(self) -> "Customer":
        """Legacy-Alias für customer"""
        return self.customer

    def calculate_totals(self) -> None:
        """
        Berechnet alle Summen aus den Positionen.
        Muss nach jeder Änderung an Positionen aufgerufen werden.
        """
        total_net = Decimal("0.00")
        total_vat = Decimal("0.00")

        for line in self.lines:
            total_net += line.line_net
            total_vat += line.line_vat

        # Rabatt anwenden
        if self.discount_percent > 0:
            self.discount_amount = (total_net * self.discount_percent / 100).quantize(Decimal("0.01"))
            total_net -= self.discount_amount
            total_vat = sum(
                (line.line_net * (1 - self.discount_percent / 100) * line.tax_rate.rate).quantize(Decimal("0.01"))
                for line in self.lines
            )

        self.total_net = total_net.quantize(Decimal("0.01"))
        self.total_vat = total_vat.quantize(Decimal("0.01"))
        self.total_gross = (self.total_net + self.total_vat).quantize(Decimal("0.01"))

    def can_be_modified(self) -> bool:
        """Prüft ob Bestellung noch bearbeitet werden kann"""
        return self.status == OrderStatus.ENTWURF

    def can_be_confirmed(self) -> bool:
        """Prüft ob Bestellung bestätigt werden kann"""
        return self.status == OrderStatus.ENTWURF and len(self.lines) > 0

    def can_be_cancelled(self) -> bool:
        """Prüft ob Bestellung storniert werden kann"""
        return self.status not in (OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT, OrderStatus.STORNIERT)

    def __repr__(self) -> str:
        return f"<Order(number='{self.order_number}', status={self.status.value})>"


class OrderLine(Base):
    """
    Bestellposition (Line) - Einzelne Zeile in einer Bestellung.

    Geschäftsregeln:
    - Positionen können nicht ohne Order existieren
    - Bei Änderung werden Summen automatisch berechnet
    """
    __tablename__ = "order_lines"

    # ==================== IDENTIFIKATION ====================
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )

    # Positionsnummer innerhalb der Bestellung (1, 2, 3, ...)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # ==================== PRODUKTREFERENZ ====================
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL")
    )
    # Legacy: seed_id für Rückwärtskompatibilität
    seed_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("seeds.id", ondelete="SET NULL")
    )

    # Produktbeschreibung (Snapshot bei Bestellung)
    product_sku: Mapped[Optional[str]] = mapped_column(String(50))
    beschreibung: Mapped[Optional[str]] = mapped_column(Text)  # Product description

    # ==================== MENGE & EINHEIT ====================
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # G, KG, STK, SCHALE, etc.

    # ==================== PREISE ====================
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    # Netto-Betrag (Menge * Einzelpreis)
    line_net: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # MwSt
    tax_rate: Mapped[TaxRate] = mapped_column(
        SQLEnum(TaxRate), default=TaxRate.REDUZIERT, nullable=False
    )
    line_vat: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Brutto-Betrag
    line_gross: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Positions-Rabatt
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00")
    )

    # ==================== LIEFERUNG ====================
    # Abweichendes Lieferdatum auf Positionsebene
    requested_delivery_date: Mapped[Optional[date]] = mapped_column(Date)

    # ==================== RÜCKVERFOLGBARKEIT ====================
    harvest_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("harvests.id", ondelete="SET NULL")
    )
    batch_number: Mapped[Optional[str]] = mapped_column(String(50))

    # ==================== AUDIT ====================
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ==================== BEZIEHUNGEN ====================
    order: Mapped["Order"] = relationship("Order", back_populates="lines")
    product: Mapped[Optional["Product"]] = relationship("Product")
    seed: Mapped[Optional["Seed"]] = relationship("Seed")
    harvest: Mapped[Optional["Harvest"]] = relationship("Harvest")

    def calculate_line_totals(self) -> None:
        """Berechnet Netto, MwSt und Brutto für diese Position"""
        # Netto = Menge * Preis * (1 - Rabatt%)
        net = self.quantity * self.unit_price
        if self.discount_percent > 0:
            net = net * (1 - self.discount_percent / 100)
        self.line_net = net.quantize(Decimal("0.01"))

        # MwSt
        vat_rate = self.tax_rate.rate
        self.line_vat = (self.line_net * vat_rate).quantize(Decimal("0.01"))

        # Brutto
        self.line_gross = (self.line_net + self.line_vat).quantize(Decimal("0.01"))

    @validates('quantity', 'unit_price', 'discount_percent', 'tax_rate')
    def validate_and_recalculate(self, key, value):
        """Automatische Neuberechnung bei Wertänderung"""
        return value

    # Legacy-Aliase
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

    def __repr__(self) -> str:
        return f"<OrderLine(pos={self.position}, product='{self.product_name}', qty={self.quantity})>"


class OrderAuditLog(Base):
    """
    Audit-Log für Bestellungsänderungen.
    Erfasst alle Änderungen an bestätigten Bestellungen.
    """
    __tablename__ = "order_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )

    # Was wurde geändert
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # CREATE, UPDATE, STATUS_CHANGE, LINE_ADD, LINE_UPDATE, LINE_DELETE

    # Betroffenes Feld oder Position
    field_name: Mapped[Optional[str]] = mapped_column(String(100))
    line_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    # Werte
    # Werte
    old_values: Mapped[Optional[dict]] = mapped_column(JSON)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON)

    # Vollständiger Snapshot (optional)
    snapshot: Mapped[Optional[dict]] = mapped_column(JSON)

    # Wer hat geändert
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    user_name: Mapped[Optional[str]] = mapped_column(String(200))

    # Wann
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Grund/Kommentar
    reason: Mapped[Optional[str]] = mapped_column(Text)

    # Beziehung
    order: Mapped["Order"] = relationship("Order", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<OrderAuditLog(order={self.order_id}, action='{self.action}')>"


# Imports für Type Hints (am Ende um zirkuläre Imports zu vermeiden)
from app.models.customer import Customer
from app.models.seed import Seed
from app.models.product import Product
from app.models.production import Harvest
from app.models.invoice import Invoice
