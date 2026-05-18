"""Belegkette: Auftragsbestätigung (AB), Lieferschein (LS), Verpackungsliste (PL).

Jede Belegart hat eigene Tabelle mit Nummernkreis + Status-Lifecycle.
Status-Übergänge zu finalen Status (VERSENDET / GELIEFERT) machen das Dokument
immutable — Re-Generation bzw. Korrektur erfordert Storno + neues Dokument.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    String, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Text,
    Enum as SQLEnum,
)
from sqlalchemy.types import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ConfirmationStatus, DeliveryNoteStatus


class OrderConfirmation(Base):
    """Auftragsbestätigung (AB) — Snapshot der Order zum Zeitpunkt der Bestätigung."""
    __tablename__ = "order_confirmations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    confirmation_number: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False
    )  # AB-YYYYMMDD-NNNN
    status: Mapped[ConfirmationStatus] = mapped_column(
        SQLEnum(ConfirmationStatus), default=ConfirmationStatus.ENTWURF, nullable=False
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sent_to_email: Mapped[Optional[str]] = mapped_column(String(200))
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

    order: Mapped["Order"] = relationship("Order", foreign_keys=[order_id])

    def is_locked(self) -> bool:
        return self.status == ConfirmationStatus.VERSENDET


class DeliveryNote(Base):
    """Lieferschein (LS) — Begleitpapier zur physischen Lieferung."""
    __tablename__ = "delivery_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    delivery_note_number: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False
    )  # LS-YYYYMMDD-NNNN
    status: Mapped[DeliveryNoteStatus] = mapped_column(
        SQLEnum(DeliveryNoteStatus), default=DeliveryNoteStatus.ENTWURF, nullable=False
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    signed_by: Mapped[Optional[str]] = mapped_column(String(200))
    actual_delivery_date: Mapped[Optional[date]] = mapped_column(Date)
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

    order: Mapped["Order"] = relationship("Order", foreign_keys=[order_id])
    packing_list: Mapped[Optional["PackingList"]] = relationship(
        "PackingList", back_populates="delivery_note", uselist=False,
        cascade="all, delete-orphan"
    )

    def is_locked(self) -> bool:
        return self.status == DeliveryNoteStatus.GELIEFERT


class PackingList(Base):
    """Verpackungsliste — 1:1 zu DeliveryNote, listet was wirklich verpackt wurde."""
    __tablename__ = "packing_lists"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    delivery_note_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("delivery_notes.id", ondelete="CASCADE"),
        unique=True, nullable=False,
    )
    packing_list_number: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False
    )  # PL-YYYYMMDD-NNNN
    total_weight_g: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    total_packages: Mapped[Optional[int]] = mapped_column(Integer)
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

    delivery_note: Mapped["DeliveryNote"] = relationship(
        "DeliveryNote", back_populates="packing_list"
    )
    items: Mapped[list["PackingListItem"]] = relationship(
        "PackingListItem", back_populates="packing_list",
        cascade="all, delete-orphan", order_by="PackingListItem.sort_order"
    )


class PackingListItem(Base):
    """Einzelposition einer Verpackungsliste — kann Produkt ODER Pfand-Position sein."""
    __tablename__ = "packing_list_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    packing_list_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("packing_lists.id", ondelete="CASCADE"), nullable=False
    )
    order_line_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("order_lines.id", ondelete="SET NULL")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Produkt-Snapshot
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)

    # Rückverfolgbarkeit
    batch_number: Mapped[Optional[str]] = mapped_column(String(50))
    harvest_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("harvests.id", ondelete="SET NULL")
    )

    # Pfand-/Verpackungs-Position (Mehrwegkiste, Karton, …)
    is_returnable_container: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    container_type: Mapped[Optional[str]] = mapped_column(String(30))  # KISTE_12, KISTE_6, KARTON_6, ...
    container_count: Mapped[Optional[int]] = mapped_column(Integer)

    packing_list: Mapped["PackingList"] = relationship(
        "PackingList", back_populates="items"
    )
