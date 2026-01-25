"""
Bestell-Models: Order und OrderItem
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from sqlalchemy import String, Numeric, DateTime, Date, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class OrderStatus(str, Enum):
    """Status einer Bestellung"""
    OFFEN = "OFFEN"
    BESTAETIGT = "BESTAETIGT"
    IN_PRODUKTION = "IN_PRODUKTION"
    BEREIT = "BEREIT"
    GELIEFERT = "GELIEFERT"
    STORNIERT = "STORNIERT"


class Order(Base):
    """
    Bestellung - Kundenauftrag mit mehreren Positionen.
    """
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kunde_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )

    # Daten
    bestell_datum: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    liefer_datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Status
    status: Mapped[OrderStatus] = mapped_column(
        SQLEnum(OrderStatus), default=OrderStatus.OFFEN
    )

    # Notizen
    notizen: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Beziehungen
    kunde: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    positionen: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )

    @property
    def gesamtwert(self) -> Decimal:
        """Berechnet Gesamtwert der Bestellung"""
        return sum(
            pos.menge * (pos.preis_pro_einheit or Decimal("0"))
            for pos in self.positionen
        )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, status={self.status.value})>"


class OrderItem(Base):
    """
    Bestellposition - Einzelne Zeile in einer Bestellung.
    Verknüpft mit Ernte für Rückverfolgbarkeit.
    """
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False
    )
    seed_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seeds.id"), nullable=False
    )

    # Bestellte Menge
    menge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    einheit: Mapped[str] = mapped_column(String(20), nullable=False)  # GRAMM, BUND, SCHALE

    # Preis
    preis_pro_einheit: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    # Rückverfolgbarkeit zur Ernte
    harvest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("harvests.id")
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Beziehungen
    order: Mapped["Order"] = relationship("Order", back_populates="positionen")
    seed: Mapped["Seed"] = relationship("Seed")
    harvest: Mapped["Harvest | None"] = relationship("Harvest", back_populates="order_items")

    @property
    def positionswert(self) -> Decimal:
        """Wert dieser Position"""
        return self.menge * (self.preis_pro_einheit or Decimal("0"))

    def __repr__(self) -> str:
        return f"<OrderItem(id={self.id}, menge={self.menge})>"


# Imports für Type Hints
from app.models.customer import Customer
from app.models.seed import Seed
from app.models.production import Harvest
