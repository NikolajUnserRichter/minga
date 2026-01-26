from typing import Optional
"""
Saatgut-Models: Seed und SeedBatch
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Text
from sqlalchemy.types import Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.database import Base


class Seed(Base):
    """
    Saatgut-Sorte mit Wachstumsparametern.
    Definiert die Eigenschaften einer Microgreens-Sorte.
    """
    __tablename__ = "seeds"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    sorte: Mapped[Optional[str]] = mapped_column(String(100))
    lieferant: Mapped[Optional[str]] = mapped_column(String(200))

    # Wachstumsparameter
    keimdauer_tage: Mapped[int] = mapped_column(Integer, nullable=False)
    wachstumsdauer_tage: Mapped[int] = mapped_column(Integer, nullable=False)

    # Erntefenster
    erntefenster_min_tage: Mapped[int] = mapped_column(Integer, nullable=False)
    erntefenster_optimal_tage: Mapped[int] = mapped_column(Integer, nullable=False)
    erntefenster_max_tage: Mapped[int] = mapped_column(Integer, nullable=False)

    # Ertrag & Verlust
    ertrag_gramm_pro_tray: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    verlustquote_prozent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0")
    )

    # Status
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Beziehungen
    batches: Mapped[list["SeedBatch"]] = relationship(
        "SeedBatch", back_populates="seed", cascade="all, delete-orphan"
    )

    @property
    def gesamte_wachstumsdauer(self) -> int:
        """Keimung + Wachstum = Tage bis Ernte"""
        return self.keimdauer_tage + self.wachstumsdauer_tage

    def __repr__(self) -> str:
        return f"<Seed(name='{self.name}', id={self.id})>"


class SeedBatch(Base):
    """
    Saatgut-Charge für Rückverfolgbarkeit.
    Jede Lieferung von Saatgut wird als Batch erfasst.
    """
    __tablename__ = "seed_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    seed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seeds.id"), nullable=False
    )

    # Chargen-Info
    charge_nummer: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    menge_gramm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    verbleibend_gramm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Daten
    mhd: Mapped[Optional[date]] = mapped_column(Date)
    lieferdatum: Mapped[Optional[date]] = mapped_column(Date)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Beziehungen
    seed: Mapped["Seed"] = relationship("Seed", back_populates="batches")
    grow_batches: Mapped[list["GrowBatch"]] = relationship(
        "GrowBatch", back_populates="seed_batch"
    )

    def __repr__(self) -> str:
        return f"<SeedBatch(charge='{self.charge_nummer}', id={self.id})>"


# Import für Type Hints
from app.models.production import GrowBatch
