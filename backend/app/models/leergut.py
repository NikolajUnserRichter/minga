"""Leergutkonto je Kunde und Pfandartikel (Paket 3, Q6).

Für Kunden mit pfand_abrechnung = MONATLICH stehen Pfandkisten nicht auf der
Lieferrechnung. Stattdessen bucht jede Lieferung eine AUSGABE ins Konto, jede
Rückgabe eine RUECKNAHME. Einmal im Monat entsteht daraus ein Leergutbeleg
(ausgegeben minus zurückgenommen). Abgerechnete Bewegungen tragen invoice_id
und sind unveränderlich; ein Storno des Belegs gibt sie wieder frei.

Der Kistensaldo (wie viele Kisten stehen beim Kunden) ist die Summe aller
Bewegungen samt Anfangsbestand — unabhängig von der Abrechnung.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Enum as SQLEnum, ForeignKey,
    Integer, Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database import Base


class LeergutArt(str, Enum):
    """Art einer Leergutbewegung. Die Menge ist immer positiv, das
    Vorzeichen folgt aus der Art."""
    AUSGABE = "AUSGABE"                  # Lieferung mit Pfandartikel
    RUECKNAHME = "RUECKNAHME"            # Kunde gibt Kisten zurück
    KORREKTUR_PLUS = "KORREKTUR_PLUS"    # Zählfehler zugunsten Minga Greens
    KORREKTUR_MINUS = "KORREKTUR_MINUS"  # Zählfehler zugunsten des Kunden
    ANFANGSBESTAND = "ANFANGSBESTAND"    # Kisten beim Kunden vor dem Stichtag

    @property
    def vorzeichen(self) -> int:
        return -1 if self in (LeergutArt.RUECKNAHME, LeergutArt.KORREKTUR_MINUS) else 1


class LeergutBewegung(Base):
    __tablename__ = "leergut_bewegungen"
    __table_args__ = (
        CheckConstraint("menge > 0", name="ck_leergut_menge_positiv"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id"), nullable=False
    )
    art: Mapped[LeergutArt] = mapped_column(SQLEnum(LeergutArt, length=20), nullable=False)
    menge: Mapped[int] = mapped_column(Integer, nullable=False)
    # Pfandwert je Stück zum Buchungszeitpunkt (deposit_value, ersatzweise
    # base_price) — Ausgabe und Rücknahme aus derselben Quelle, sonst geht
    # der Saldo bei gleicher Stückzahl nicht auf null.
    einzelwert: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Liefer- bzw. Rückgabetag; bestimmt den Abrechnungsmonat
    leistungsdatum: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Herkunft einer AUSGABE: höchstens eine Bewegung je Bestellposition
    order_line_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("order_lines.id", ondelete="SET NULL"), unique=True
    )
    delivery_note_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("delivery_notes.id", ondelete="SET NULL")
    )
    # Gesetzt = in diesem Leergutbeleg abgerechnet (Doppelabrechnungsschutz)
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("invoices.id", ondelete="SET NULL"), index=True
    )
    # Nur ANFANGSBESTAND: zählt im Kistensaldo, wird aber nicht abgerechnet
    bereits_berechnet: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    erfasst_von: Mapped[Optional[str]] = mapped_column(String(100))
    erfasst_am: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    notiz: Mapped[Optional[str]] = mapped_column(Text)

    product: Mapped["Product"] = relationship("Product")

    @property
    def artikel(self) -> str:
        return self.product.name if self.product else ""

    @property
    def stueck_mit_vorzeichen(self) -> int:
        return self.art.vorzeichen * self.menge

    @property
    def abrechenbar(self) -> bool:
        return self.invoice_id is None and not self.bereits_berechnet


from app.models.product import Product  # noqa: E402
