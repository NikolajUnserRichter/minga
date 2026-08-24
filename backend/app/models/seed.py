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

    # Produktgruppe — SAATGUT | SUBSTRAT | VERPACKUNG | ARBEITSMATERIAL | SONSTIGES
    product_group: Mapped[Optional[str]] = mapped_column(String(30))

    # BIO-Daten (relevant nur für Saatgut-/Substrat-Lieferanten)
    is_organic: Mapped[bool] = mapped_column(Boolean, default=False)
    bio_certificate_url: Mapped[Optional[str]] = mapped_column(String(500))
    bio_certificate_valid_until: Mapped[Optional[date]] = mapped_column(Date)
    bio_kontrollstelle: Mapped[Optional[str]] = mapped_column(String(100))

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

    # Substrattyp für die Aussaat-Arbeitsanweisung (z.B. "Hanfmatte", "Erde")
    substrat: Mapped[Optional[str]] = mapped_column(String(100))

    # Winterzyklus: zusätzliche Wachstumstage wenn SEASON_MODE=WINTER (App-Setting).
    # Legacy-Pauschale — wird nur noch genutzt, wenn kein Winter-Satz gepflegt ist.
    winter_extra_tage: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Wachstumsparameter
    keimdauer_tage: Mapped[int] = mapped_column(Integer, nullable=False)
    wachstumsdauer_tage: Mapped[int] = mapped_column(Integer, nullable=False)

    # Erntefenster
    erntefenster_min_tage: Mapped[int] = mapped_column(Integer, nullable=False)
    erntefenster_optimal_tage: Mapped[int] = mapped_column(Integer, nullable=False)
    erntefenster_max_tage: Mapped[int] = mapped_column(Integer, nullable=False)

    # Eigenständiger Winter-Parametersatz. Eine Verzögerung kann in der
    # Keimung ODER im Growroom entstehen — pauschale Zusatztage verwischen
    # das, und der Mitarbeiter weiß nicht mehr, wann er was zu tun hat.
    # Leer = Winter verhält sich wie Sommer (ggf. + winter_extra_tage).
    winter_keimdauer_tage: Mapped[Optional[int]] = mapped_column(Integer)
    winter_wachstumsdauer_tage: Mapped[Optional[int]] = mapped_column(Integer)
    winter_erntefenster_min_tage: Mapped[Optional[int]] = mapped_column(Integer)
    winter_erntefenster_optimal_tage: Mapped[Optional[int]] = mapped_column(Integer)
    winter_erntefenster_max_tage: Mapped[Optional[int]] = mapped_column(Integer)

    # Ertrag & Verlust
    ertrag_gramm_pro_tray: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    verlustquote_prozent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0")
    )

    # Mischung (z.B. 'Brotzeitmix'): wird nicht eingekauft, sondern beim
    # Aussäen aus den Komponenten gemischt — siehe SeedMixComponent.
    is_mix: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

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
    mix_components: Mapped[list["SeedMixComponent"]] = relationship(
        "SeedMixComponent",
        back_populates="mix_seed",
        foreign_keys="SeedMixComponent.mix_seed_id",
        cascade="all, delete-orphan",
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

    # Chargen-spezifische Abweichung: verschiebt das Erntefenster um N Tage
    # (z.B. +1 wenn diese Charge langsamer keimt; negativ erlaubt)
    zusatz_tage: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Chargenbedingte Wachstumsparameter: einmal an der Charge gepflegt statt
    # bei jedem Aussaatzyklus neu erfasst. Leer = Sortenwert der Saison.
    keimdauer_tage: Mapped[Optional[int]] = mapped_column(Integer)
    wachstumsdauer_tage: Mapped[Optional[int]] = mapped_column(Integer)
    erntefenster_min_tage: Mapped[Optional[int]] = mapped_column(Integer)
    erntefenster_optimal_tage: Mapped[Optional[int]] = mapped_column(Integer)
    erntefenster_max_tage: Mapped[Optional[int]] = mapped_column(Integer)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Beziehungen
    seed: Mapped["Seed"] = relationship("Seed", back_populates="batches")
    grow_batches: Mapped[list["GrowBatch"]] = relationship(
        "GrowBatch", back_populates="seed_batch"
    )

    def __repr__(self) -> str:
        return f"<SeedBatch(charge='{self.charge_nummer}', id={self.id})>"


class SeedMixComponent(Base):
    """
    Rezept einer Mischsorte: welche Sorte mit wie viel Gramm je Kiste.

    Der Mix selbst ist eine ganz normale Sorte (Seed mit is_mix=True) — nur
    hat er keinen eigenen Wareneingang, sondern entsteht bei jeder Aussaat neu.
    """
    __tablename__ = "seed_mix_components"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    mix_seed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seeds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    component_seed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seeds.id"), nullable=False
    )
    gramm_pro_tray: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)

    mix_seed: Mapped["Seed"] = relationship(
        "Seed", back_populates="mix_components", foreign_keys=[mix_seed_id]
    )
    component_seed: Mapped["Seed"] = relationship("Seed", foreign_keys=[component_seed_id])

    # Nach außen heißt die Komponente schlicht 'seed_id' — für die Maske ist
    # sie eine Sorte mit Menge, nicht eine Beziehung zwischen zwei Sorten.
    @property
    def seed_id(self) -> uuid.UUID:
        return self.component_seed_id

    @property
    def seed_name(self) -> Optional[str]:
        return self.component_seed.name if self.component_seed else None

    def __repr__(self) -> str:
        return f"<SeedMixComponent(mix={self.mix_seed_id}, seed={self.component_seed_id})>"


class SeedBatchComponent(Base):
    """
    Rückverfolgbarkeit einer Mischcharge: welche Ausgangschargen stecken drin.

    Die Chargennummer wird als Text mitgeschrieben und nicht nur verlinkt —
    sie muss auch dann noch lesbar sein, wenn der Bestand längst abverkauft
    und aufgeräumt ist.
    """
    __tablename__ = "seed_batch_components"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    mix_batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seed_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    component_seed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seeds.id"), nullable=False
    )
    charge_nummer: Mapped[str] = mapped_column(String(50), nullable=False)
    menge_gramm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    component_seed: Mapped["Seed"] = relationship("Seed", foreign_keys=[component_seed_id])

    @property
    def seed_name(self) -> Optional[str]:
        return self.component_seed.name if self.component_seed else None

    def __repr__(self) -> str:
        return f"<SeedBatchComponent(charge='{self.charge_nummer}', menge={self.menge_gramm})>"


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
