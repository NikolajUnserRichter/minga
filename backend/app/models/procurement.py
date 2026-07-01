"""
Procurement-Models: PurchaseOrder, PurchaseOrderLine.

Einkaufsseite des ERP (Handels-/Tradesk-Edition): Ware beim Lieferanten
bestellen, Wareneingang verbuchen, Bestellstatus verfolgen. Spiegelt die
Konventionen der Sales-Order (app/models/order.py): UUID-PKs, Numeric-
Decimals, quantize(0.01), calculate_totals()/calculate_line_totals().
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.invoice import TaxRate


class PurchaseOrderStatus(str, Enum):
    """Lebenszyklus einer Bestellung beim Lieferanten."""
    ENTWURF = "ENTWURF"                        # bearbeitbar
    BESTELLT = "BESTELLT"                      # an Lieferant übermittelt
    TEILWEISE_ERHALTEN = "TEILWEISE_ERHALTEN"  # Wareneingang teilweise
    ERHALTEN = "ERHALTEN"                      # vollständig eingegangen
    STORNIERT = "STORNIERT"                    # storniert


class PurchaseOrder(Base):
    """Bestellung beim Lieferanten (Einkauf/Wareneingang)."""

    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    po_number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("suppliers.id"), nullable=False, index=True
    )
    # Referenz des Lieferanten (dessen eigene Auftragsnummer)
    supplier_reference: Mapped[Optional[str]] = mapped_column(String(50))

    status: Mapped[PurchaseOrderStatus] = mapped_column(
        SQLEnum(PurchaseOrderStatus), default=PurchaseOrderStatus.ENTWURF, index=True, nullable=False
    )

    order_date: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    requested_delivery_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    confirmed_delivery_date: Mapped[Optional[date]] = mapped_column(Date)

    total_net: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_vat: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_gross: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)

    notes: Mapped[Optional[str]] = mapped_column(Text)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    supplier: Mapped["Supplier"] = relationship("Supplier")
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        "PurchaseOrderLine", back_populates="purchase_order", cascade="all, delete-orphan"
    )

    def calculate_totals(self) -> None:
        """Summen aus den Positionen berechnen (mirror von Order.calculate_totals)."""
        total_net = Decimal("0.00")
        total_vat = Decimal("0.00")
        for line in self.lines:
            total_net += line.line_net
            total_vat += line.line_vat

        if self.discount_percent and self.discount_percent > 0:
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
        return self.status == PurchaseOrderStatus.ENTWURF

    def recompute_receipt_status(self) -> None:
        """Status anhand der eingegangenen Mengen neu setzen."""
        if not self.lines:
            return
        if all(line.is_fully_received for line in self.lines):
            self.status = PurchaseOrderStatus.ERHALTEN
        elif any(line.quantity_received and line.quantity_received > 0 for line in self.lines):
            self.status = PurchaseOrderStatus.TEILWEISE_ERHALTEN

    def __repr__(self) -> str:
        return f"<PurchaseOrder(number='{self.po_number}', status={self.status.value})>"


class PurchaseOrderLine(Base):
    """Position einer Bestellung."""

    __tablename__ = "purchase_order_lines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL")
    )
    product_sku: Mapped[Optional[str]] = mapped_column(String(50))
    beschreibung: Mapped[Optional[str]] = mapped_column(Text)

    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    # Eingegangene Menge (Wareneingang, ggf. in Teilmengen)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"), nullable=False)

    # Einkaufspreis pro Einheit (Netto)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    tax_rate: Mapped[TaxRate] = mapped_column(SQLEnum(TaxRate), default=TaxRate.STANDARD, nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))

    line_net: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    line_vat: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    line_gross: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    purchase_order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder", back_populates="lines")
    product: Mapped[Optional["Product"]] = relationship("Product")

    def calculate_line_totals(self) -> None:
        """Netto = Menge * Preis * (1 - Rabatt%), dann MwSt + Brutto."""
        net = self.quantity * self.unit_price
        if self.discount_percent and self.discount_percent > 0:
            net = net * (1 - self.discount_percent / 100)
        self.line_net = net.quantize(Decimal("0.01"))
        self.line_vat = (self.line_net * self.tax_rate.rate).quantize(Decimal("0.01"))
        self.line_gross = (self.line_net + self.line_vat).quantize(Decimal("0.01"))

    @property
    def quantity_open(self) -> Decimal:
        """Noch ausstehende (nicht eingegangene) Menge."""
        return (self.quantity or Decimal("0")) - (self.quantity_received or Decimal("0"))

    @property
    def is_fully_received(self) -> bool:
        return self.quantity_open <= Decimal("0")

    def __repr__(self) -> str:
        return f"<PurchaseOrderLine(pos={self.position}, qty={self.quantity})>"
