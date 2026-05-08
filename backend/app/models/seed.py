from typing import Optional
"""
Saatgut-Models: Seed und SeedBatch
"""

import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import String, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Text
from sqlalchemy.types import Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.database import Base


class Supplier(Base):
    """
    Lieferant — Saatgut-Lieferanten als Stammdaten.
    Erlaubt Default + Backup-Lieferant pro Sorte.
    """
    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(200))
    telefon: Mapped[Optional[str]] = mapped_column(String(50))
    adresse: Mapped[Optional[str]] = mapped_column(Text)
    ust_id: Mapped[Optional[str]] = mapped_column(String(20))
    notizen: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<Supplier(name='{self.name}')>"


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
    lieferant: Mapped[Optional[str]] = mapped_column(String(200))  # Legacy free-text

    # Strukturierte Lieferanten (default + backup)
    supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("suppliers.id", ondelete="SET NULL")
    )
    backup_supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("suppliers.id", ondelete="SET NULL")
    )

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Beziehungen
    batches: Mapped[list["SeedBatch"]] = relationship(
        "SeedBatch", back_populates="seed", cascade="all, delete-orphan"
    )
    supplier: Mapped[Optional["Supplier"]] = relationship(
        "Supplier", foreign_keys=[supplier_id]
    )
    backup_supplier: Mapped[Optional["Supplier"]] = relationship(
        "Supplier", foreign_keys=[backup_supplier_id]
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
    in_production_at: Mapped[Optional[date]] = mapped_column(Date)  # Wann in Produktion genommen

    # Lieferschein / Bio-Doku
    lieferschein_nr: Mapped[Optional[str]] = mapped_column(String(50))
    bio_zertifiziert: Mapped[bool] = mapped_column(Boolean, default=False)
    kontrollstelle: Mapped[Optional[str]] = mapped_column(String(100))  # z.B. DE-ÖKO-006

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Beziehungen
    seed: Mapped["Seed"] = relationship("Seed", back_populates="batches")
    grow_batches: Mapped[list["GrowBatch"]] = relationship(
        "GrowBatch", back_populates="seed_batch"
    )

    def __repr__(self) -> str:
        return f"<SeedBatch(charge='{self.charge_nummer}', id={self.id})>"


# Import für Type Hints
from app.models.production import GrowBatch
