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
    # Mehrere Lieferanten via `seed_suppliers` Join-Tabelle (siehe SeedSupplier-Modell)

    # Kühlphase + Prozessvariante (sortenspezifisch)
    cooling_days: Mapped[Optional[int]] = mapped_column(Integer)
    cooling_shelf_life_days: Mapped[Optional[int]] = mapped_column(Integer)
    process_type: Mapped[str] = mapped_column(String(30), default="STANDARD")  # STANDARD | PLATTE | PLATTE_STEINE

    # Saatgut-Dichte pro Anzucht-Einheit (Kiste/Tray) — wird im SowingForm angezeigt
    saatgut_pro_einheit_gramm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))

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
    supplier_links: Mapped[list["SeedSupplier"]] = relationship(
        "SeedSupplier", back_populates="seed", cascade="all, delete-orphan"
    )

    @property
    def default_supplier(self) -> Optional["Supplier"]:
        """Standard-Lieferant (is_default=True)."""
        for link in self.supplier_links:
            if link.is_default:
                return link.supplier
        return None

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


class SeedSupplier(Base):
    """
    Many-to-Many zwischen Saatgut-Sorte und Lieferanten.
    Mehrere Lieferanten pro Sorte mit optionalem Default-Flag.
    """
    __tablename__ = "seed_suppliers"

    seed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seeds.id", ondelete="CASCADE"), primary_key=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("suppliers.id", ondelete="CASCADE"), primary_key=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    notizen: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    seed: Mapped["Seed"] = relationship("Seed", back_populates="supplier_links")
    supplier: Mapped["Supplier"] = relationship("Supplier")

    def __repr__(self) -> str:
        return f"<SeedSupplier(seed={self.seed_id}, supplier={self.supplier_id}, default={self.is_default})>"


# Import für Type Hints
from app.models.production import GrowBatch
