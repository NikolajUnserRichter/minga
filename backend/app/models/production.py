from typing import Optional
"""
Produktions-Models: GrowBatch und Harvest
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from sqlalchemy import String, Integer, Numeric, DateTime, Date, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.types import Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.database import Base


class GrowBatchStatus(str, Enum):
    """Status einer Wachstumscharge"""
    KEIMUNG = "KEIMUNG"
    WACHSTUM = "WACHSTUM"
    ERNTEREIF = "ERNTEREIF"
    GEERNTET = "GEERNTET"
    VERLUST = "VERLUST"


class GrowBatch(Base):
    """
    Wachstumscharge - repräsentiert eine Aussaat.
    Verfolgt den kompletten Wachstumszyklus von Aussaat bis Ernte.
    """
    __tablename__ = "grow_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    seed_batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seed_batches.id"), nullable=False
    )

    # Produktionsdaten
    tray_anzahl: Mapped[int] = mapped_column(Integer, nullable=False)
    aussaat_datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Berechnete Erntedaten
    erwartete_ernte_min: Mapped[date] = mapped_column(Date, nullable=False)
    erwartete_ernte_optimal: Mapped[date] = mapped_column(Date, nullable=False)
    erwartete_ernte_max: Mapped[date] = mapped_column(Date, nullable=False)

    # Status & Position
    status: Mapped[GrowBatchStatus] = mapped_column(
        SQLEnum(GrowBatchStatus), default=GrowBatchStatus.KEIMUNG
    )
    regal_position: Mapped[Optional[str]] = mapped_column(String(50))

    # Notizen
    notizen: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Beziehungen
    seed_batch: Mapped["SeedBatch"] = relationship("SeedBatch", back_populates="grow_batches")
    harvests: Mapped[list["Harvest"]] = relationship(
        "Harvest", back_populates="grow_batch", cascade="all, delete-orphan"
    )

    @property
    def tage_seit_aussaat(self) -> int:
        """Berechnet Tage seit Aussaat"""
        return (date.today() - self.aussaat_datum).days

    @property
    def ist_erntereif(self) -> bool:
        """Prüft ob Charge im Erntefenster ist"""
        today = date.today()
        return self.erwartete_ernte_min <= today <= self.erwartete_ernte_max

    def __repr__(self) -> str:
        return f"<GrowBatch(id={self.id}, status={self.status.value})>"


class Harvest(Base):
    """
    Ernte - Dokumentiert geerntete Mengen aus einer GrowBatch.
    Ermöglicht Teil- und Mehrfachernten pro Charge.
    """
    __tablename__ = "harvests"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    grow_batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("grow_batches.id"), nullable=False
    )

    # Erntedaten
    ernte_datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    menge_gramm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    verlust_gramm: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))

    # Qualität (1-5 Sterne)
    qualitaet_note: Mapped[Optional[int]] = mapped_column(Integer)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Beziehungen
    grow_batch: Mapped["GrowBatch"] = relationship("GrowBatch", back_populates="harvests")
    order_items: Mapped[list["OrderLine"]] = relationship(
        "OrderLine", back_populates="harvest"
    )

    @property
    def verlustquote(self) -> Decimal:
        """Berechnet Verlustquote in Prozent"""
        total = self.menge_gramm + self.verlust_gramm
        if total == 0:
            return Decimal("0")
        return (self.verlust_gramm / total) * 100

    def __repr__(self) -> str:
        return f"<Harvest(id={self.id}, menge={self.menge_gramm}g)>"


# Imports für Type Hints
from app.models.seed import SeedBatch
from app.models.order import OrderLine
