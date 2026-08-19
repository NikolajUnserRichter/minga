from typing import Optional
"""
Produktions-Models: GrowBatch und Harvest
"""
import uuid
from datetime import datetime, date, timezone
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

    # Ende der Keimphase (Umzug in den Growroom) — im Winter oder bei
    # langsamen Chargen verschiebt sich dieser Tag unabhängig vom Erntefenster.
    keimende_datum: Mapped[Optional[date]] = mapped_column(Date)
    # Welcher Parametersatz galt: SORTE | WINTER | CHARGE
    parameter_quelle: Mapped[Optional[str]] = mapped_column(String(10))

    # Status & Position
    status: Mapped[GrowBatchStatus] = mapped_column(
        SQLEnum(GrowBatchStatus), default=GrowBatchStatus.KEIMUNG
    )
    regal_position: Mapped[Optional[str]] = mapped_column(String(50))

    # Notizen
    notizen: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Beziehungen
    seed_batch: Mapped["SeedBatch"] = relationship("SeedBatch", back_populates="grow_batches")
    harvests: Mapped[list["Harvest"]] = relationship(
        "Harvest", back_populates="grow_batch", cascade="all, delete-orphan"
    )

    @property
    def seed_name(self) -> Optional[str]:
        """Sortenname über die Saatgut-Charge (für Listen/Karten-Anzeige)"""
        if self.seed_batch and self.seed_batch.seed:
            return self.seed_batch.seed.name
        return None

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
    # einheit bestimmt, welche Mengenfelder gelten:
    # "G"   → menge_gramm/verlust_gramm (geschnittene Ernte, gewogen)
    # "STK" → menge_stueck/verlust_stueck (ganze Schalen, gezählt);
    #         menge_gramm wird dann als 0 gespeichert (SQLite-Tenant-DBs haben
    #         NOT NULL auf der Spalte; 0 verfälscht keine Gramm-Summen)
    ernte_datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    einheit: Mapped[str] = mapped_column(String(10), default="G", server_default="G", nullable=False)
    menge_gramm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    verlust_gramm: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    menge_stueck: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    verlust_stueck: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Kistenformat zum Erntezeitpunkt (z.B. 15 oder 21 Stk pro Anzuchtkiste)
    stueck_pro_kiste: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Qualität (1-5 Sterne)
    qualitaet_note: Mapped[Optional[int]] = mapped_column(Integer)

    # Quality control
    quality_approved: Mapped[bool] = mapped_column(Integer, default=True)  # Freigegeben?
    quality_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Beziehungen
    grow_batch: Mapped["GrowBatch"] = relationship("GrowBatch", back_populates="harvests")
    order_items: Mapped[list["OrderLine"]] = relationship(
        "OrderLine", back_populates="harvest"
    )

    @property
    def verlustquote(self) -> Decimal:
        """Berechnet Verlustquote in Prozent (einheitsbewusst)"""
        if self.einheit == "STK":
            menge = Decimal(self.menge_stueck or 0)
            verlust = Decimal(self.verlust_stueck or 0)
        else:
            menge = self.menge_gramm or Decimal("0")
            verlust = self.verlust_gramm or Decimal("0")
        total = menge + verlust
        if total == 0:
            return Decimal("0")
        return (verlust / total) * 100

    def __repr__(self) -> str:
        if self.einheit == "STK":
            return f"<Harvest(id={self.id}, menge={self.menge_stueck}Stk)>"
        return f"<Harvest(id={self.id}, menge={self.menge_gramm}g)>"


# Imports für Type Hints
from app.models.seed import SeedBatch
from app.models.order import OrderLine
