"""Customer-spezifische Preise (Sonderpreise pro Kunde, optional zeitlich begrenzt).

Beim Erstellen einer Order wird für jede Position der Customer-Price gesucht
und (wenn aktiv) als unit_price übernommen. Funktioniert für reguläre
Produkte und Bundles gleichermaßen (product_id zeigt einfach auf das Produkt
in der products-Tabelle).
"""
from __future__ import annotations

import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Numeric, DateTime, Date, ForeignKey, Text, UniqueConstraint
from sqlalchemy.types import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CustomerPrice(Base):
    """Sonderpreis eines Produkts für einen bestimmten Kunden."""
    __tablename__ = "customer_prices"
    __table_args__ = (
        UniqueConstraint("customer_id", "product_id", "valid_from",
                         name="uq_customer_price_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )

    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)

    valid_from: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)  # NULL = unbegrenzt

    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    customer = relationship("Customer", backref="customer_prices")
    product  = relationship("Product")
