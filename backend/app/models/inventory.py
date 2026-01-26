"""
Inventory Models: Lagerverwaltung für Saatgut, Verpackung und Fertigware
Mit vollständiger Rückverfolgbarkeit (Seed → Grow → Harvest → Customer)
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional
from sqlalchemy import String, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.types import Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.database import Base


class LocationType(str, Enum):
    """Lagerort-Typ"""
    LAGER = "LAGER"               # Allgemeines Lager
    KUEHLRAUM = "KUEHLRAUM"       # Kühlraum für Fertigware
    REGAL = "REGAL"               # Produktionsregal
    KEIMRAUM = "KEIMRAUM"         # Keimraum/Dunkelphase
    VERSAND = "VERSAND"           # Versandbereich


class MovementType(str, Enum):
    """Art der Lagerbewegung"""
    EINGANG = "EINGANG"           # Wareneingang (Einkauf)
    AUSGANG = "AUSGANG"           # Warenausgang (Verkauf/Lieferung)
    PRODUKTION = "PRODUKTION"     # Verbrauch in Produktion
    ERNTE = "ERNTE"               # Ernte von GrowBatch
    VERLUST = "VERLUST"           # Verlust/Verderb
    KORREKTUR = "KORREKTUR"       # Manuelle Inventurkorrektur
    UMLAGERUNG = "UMLAGERUNG"     # Umlagerung zwischen Standorten
    RUECKGABE = "RUECKGABE"       # Rückgabe


class InventoryItemType(str, Enum):
    """Typ des Lagerartikels"""
    SAATGUT = "SAATGUT"           # Saatgut
    VERPACKUNG = "VERPACKUNG"     # Verpackungsmaterial
    FERTIGWARE = "FERTIGWARE"     # Geerntete Microgreens
    SUBSTRAT = "SUBSTRAT"         # Erde, Kokosfaser, etc.
    SONSTIGES = "SONSTIGES"       # Sonstige Materialien


class InventoryLocation(Base):
    """
    Lagerort - Physische Lagerorte (Regale, Kühlräume, etc.)
    """
    __tablename__ = "inventory_locations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # Identifikation
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location_type: Mapped[LocationType] = mapped_column(
        SQLEnum(LocationType), nullable=False
    )

    # Hierarchie (optional für Regalsysteme: Halle > Reihe > Regal > Fach)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("inventory_locations.id", ondelete="SET NULL")
    )

    # Kapazität
    capacity_trays: Mapped[Optional[int]] = mapped_column(Integer)  # Max Trays
    capacity_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))  # Max Gewicht

    # Umgebungsbedingungen
    temperature_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 1))  # °C
    temperature_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 1))
    humidity_min: Mapped[Optional[int]] = mapped_column(Integer)  # %
    humidity_max: Mapped[Optional[int]] = mapped_column(Integer)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Beziehungen
    parent: Mapped[Optional["InventoryLocation"]] = relationship(
        "InventoryLocation", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["InventoryLocation"]] = relationship(
        "InventoryLocation", back_populates="parent"
    )

    def __repr__(self) -> str:
        return f"<InventoryLocation(code='{self.code}', type={self.location_type.value})>"


class SeedInventory(Base):
    """
    Saatgut-Lagerbestand - Chargen-basierte Saatgutverwaltung
    """
    __tablename__ = "seed_inventory"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # Referenz zum Seed (Sorte)
    seed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seeds.id"), nullable=False
    )

    # Chargenidentifikation
    batch_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    supplier_batch: Mapped[Optional[str]] = mapped_column(String(50))  # Lieferanten-Charge

    # Mengen
    initial_quantity_kg: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    current_quantity_kg: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)

    # Qualität
    germination_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))  # Keimrate %
    quality_grade: Mapped[Optional[str]] = mapped_column(String(10))  # A, B, C

    # Datum
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    best_before_date: Mapped[Optional[date]] = mapped_column(Date)  # MHD
    production_date: Mapped[Optional[date]] = mapped_column(Date)  # Produktionsdatum

    # Lieferant
    supplier_name: Mapped[Optional[str]] = mapped_column(String(200))
    purchase_price_per_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # Lagerort
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("inventory_locations.id", ondelete="SET NULL")
    )

    # Bio-Zertifizierung
    is_organic: Mapped[bool] = mapped_column(Boolean, default=False)
    organic_certificate: Mapped[Optional[str]] = mapped_column(String(100))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)  # Qualitätssperre
    block_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Beziehungen
    seed: Mapped["Seed"] = relationship("Seed")
    location: Mapped[Optional["InventoryLocation"]] = relationship("InventoryLocation")
    movements: Mapped[list["InventoryMovement"]] = relationship(
        "InventoryMovement",
        primaryjoin="SeedInventory.id == InventoryMovement.seed_inventory_id",
        back_populates="seed_inventory"
    )

    @property
    def is_expired(self) -> bool:
        """Ist das Saatgut abgelaufen?"""
        if not self.best_before_date:
            return False
        return date.today() > self.best_before_date

    @property
    def days_until_expiry(self) -> Optional[int]:
        """Tage bis MHD"""
        if not self.best_before_date:
            return None
        return (self.best_before_date - date.today()).days

    def __repr__(self) -> str:
        return f"<SeedInventory(batch='{self.batch_number}', qty={self.current_quantity_kg}kg)>"


class FinishedGoodsInventory(Base):
    """
    Fertigwaren-Lagerbestand - Geerntete Microgreens
    Mit vollständiger Rückverfolgbarkeit zum GrowBatch
    """
    __tablename__ = "finished_goods_inventory"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # Referenz zum Produkt
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id"), nullable=False
    )

    # Chargenidentifikation
    batch_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Rückverfolgbarkeit
    harvest_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("harvests.id", ondelete="SET NULL")
    )
    grow_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("grow_batches.id", ondelete="SET NULL")
    )
    seed_inventory_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("seed_inventory.id", ondelete="SET NULL")
    )

    # Mengen
    initial_quantity_g: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    current_quantity_g: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Verpackungseinheiten (optional)
    initial_units: Mapped[Optional[int]] = mapped_column(Integer)
    current_units: Mapped[Optional[int]] = mapped_column(Integer)
    unit_size_g: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))  # Gramm pro Einheit

    # Qualität
    quality_grade: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    quality_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Datum
    harvest_date: Mapped[date] = mapped_column(Date, nullable=False)
    best_before_date: Mapped[date] = mapped_column(Date, nullable=False)
    packed_date: Mapped[Optional[date]] = mapped_column(Date)

    # Lagerort
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("inventory_locations.id", ondelete="SET NULL")
    )

    # Lagerbedingungen
    storage_temp_celsius: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 1))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_reserved: Mapped[bool] = mapped_column(Boolean, default=False)  # Für Bestellung reserviert
    reserved_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="SET NULL")
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Beziehungen
    product: Mapped["Product"] = relationship("Product")
    harvest: Mapped[Optional["Harvest"]] = relationship("Harvest")
    grow_batch: Mapped[Optional["GrowBatch"]] = relationship("GrowBatch")
    seed_inventory: Mapped[Optional["SeedInventory"]] = relationship("SeedInventory")
    location: Mapped[Optional["InventoryLocation"]] = relationship("InventoryLocation")
    movements: Mapped[list["InventoryMovement"]] = relationship(
        "InventoryMovement",
        primaryjoin="FinishedGoodsInventory.id == InventoryMovement.finished_goods_id",
        back_populates="finished_goods"
    )

    @property
    def is_expired(self) -> bool:
        """Ist die Ware abgelaufen?"""
        return date.today() > self.best_before_date

    @property
    def days_until_expiry(self) -> int:
        """Tage bis MHD"""
        return (self.best_before_date - date.today()).days

    @property
    def traceability_chain(self) -> dict:
        """Vollständige Rückverfolgungskette"""
        return {
            "finished_goods_batch": self.batch_number,
            "harvest_id": str(self.harvest_id) if self.harvest_id else None,
            "grow_batch_id": str(self.grow_batch_id) if self.grow_batch_id else None,
            "seed_inventory_id": str(self.seed_inventory_id) if self.seed_inventory_id else None,
        }

    def __repr__(self) -> str:
        return f"<FinishedGoodsInventory(batch='{self.batch_number}', qty={self.current_quantity_g}g)>"


class PackagingInventory(Base):
    """
    Verpackungsmaterial-Lagerbestand
    """
    __tablename__ = "packaging_inventory"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # Artikel
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Mengen
    current_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_quantity: Mapped[int] = mapped_column(Integer, default=0)  # Mindestbestand
    reorder_quantity: Mapped[Optional[int]] = mapped_column(Integer)  # Nachbestellmenge

    # Einheit
    unit: Mapped[str] = mapped_column(String(20), default="Stück")

    # Lieferant
    supplier_name: Mapped[Optional[str]] = mapped_column(String(200))
    supplier_sku: Mapped[Optional[str]] = mapped_column(String(50))
    purchase_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # Lagerort
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("inventory_locations.id", ondelete="SET NULL")
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Beziehungen
    location: Mapped[Optional["InventoryLocation"]] = relationship("InventoryLocation")
    movements: Mapped[list["InventoryMovement"]] = relationship(
        "InventoryMovement",
        primaryjoin="PackagingInventory.id == InventoryMovement.packaging_id",
        back_populates="packaging"
    )

    @property
    def needs_reorder(self) -> bool:
        """Ist Nachbestellung nötig?"""
        return self.current_quantity <= self.min_quantity

    def __repr__(self) -> str:
        return f"<PackagingInventory(sku='{self.sku}', qty={self.current_quantity})>"


class InventoryMovement(Base):
    """
    Lagerbewegung - Protokolliert jede Bestandsänderung
    Ermöglicht vollständige Rückverfolgbarkeit
    """
    __tablename__ = "inventory_movements"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # Bewegungsart
    movement_type: Mapped[MovementType] = mapped_column(
        SQLEnum(MovementType), nullable=False
    )
    item_type: Mapped[InventoryItemType] = mapped_column(
        SQLEnum(InventoryItemType), nullable=False
    )

    # Referenz zum Bestand (eine davon muss gesetzt sein)
    seed_inventory_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("seed_inventory.id", ondelete="SET NULL")
    )
    finished_goods_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("finished_goods_inventory.id", ondelete="SET NULL")
    )
    packaging_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("packaging_inventory.id", ondelete="SET NULL")
    )

    # Menge (positiv = Zugang, negativ = Abgang)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)

    # Bestand vor/nach
    quantity_before: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    quantity_after: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    # Lagerorte (bei Umlagerung)
    from_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("inventory_locations.id", ondelete="SET NULL")
    )
    to_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("inventory_locations.id", ondelete="SET NULL")
    )

    # Referenzen für Rückverfolgbarkeit
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="SET NULL")
    )
    order_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("order_lines.id", ondelete="SET NULL")
    )
    grow_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("grow_batches.id", ondelete="SET NULL")
    )
    harvest_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("harvests.id", ondelete="SET NULL")
    )

    # Benutzer und Notizen
    created_by: Mapped[Optional[str]] = mapped_column(String(100))  # User ID/Name
    reason: Mapped[Optional[str]] = mapped_column(Text)  # Grund (bei Korrektur/Verlust)
    reference_number: Mapped[Optional[str]] = mapped_column(String(50))  # z.B. Lieferschein-Nr

    # Timestamps
    movement_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Beziehungen
    seed_inventory: Mapped[Optional["SeedInventory"]] = relationship(
        "SeedInventory", back_populates="movements"
    )
    finished_goods: Mapped[Optional["FinishedGoodsInventory"]] = relationship(
        "FinishedGoodsInventory", back_populates="movements"
    )
    packaging: Mapped[Optional["PackagingInventory"]] = relationship(
        "PackagingInventory", back_populates="movements"
    )
    from_location: Mapped[Optional["InventoryLocation"]] = relationship(
        "InventoryLocation", foreign_keys=[from_location_id]
    )
    to_location: Mapped[Optional["InventoryLocation"]] = relationship(
        "InventoryLocation", foreign_keys=[to_location_id]
    )

    def __repr__(self) -> str:
        return f"<InventoryMovement(type={self.movement_type.value}, qty={self.quantity})>"


class InventoryCount(Base):
    """
    Inventur - Regelmäßige Bestandszählung
    """
    __tablename__ = "inventory_counts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # Inventurdatum
    count_date: Mapped[date] = mapped_column(Date, nullable=False)
    count_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="OFFEN")  # OFFEN, IN_BEARBEITUNG, ABGESCHLOSSEN

    # Lagerort (optional, für Teil-Inventur)
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("inventory_locations.id", ondelete="SET NULL")
    )

    # Notizen
    notes: Mapped[Optional[str]] = mapped_column(Text)
    counted_by: Mapped[Optional[str]] = mapped_column(String(100))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Beziehungen
    location: Mapped[Optional["InventoryLocation"]] = relationship("InventoryLocation")
    items: Mapped[list["InventoryCountItem"]] = relationship(
        "InventoryCountItem", back_populates="count", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<InventoryCount(number='{self.count_number}', date={self.count_date})>"


class InventoryCountItem(Base):
    """
    Inventur-Position - Einzelne Zählposition
    """
    __tablename__ = "inventory_count_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    count_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("inventory_counts.id", ondelete="CASCADE"), nullable=False
    )

    # Artikel-Referenz (eine davon)
    item_type: Mapped[InventoryItemType] = mapped_column(
        SQLEnum(InventoryItemType), nullable=False
    )
    seed_inventory_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("seed_inventory.id", ondelete="SET NULL")
    )
    finished_goods_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("finished_goods_inventory.id", ondelete="SET NULL")
    )
    packaging_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("packaging_inventory.id", ondelete="SET NULL")
    )

    # Mengen
    system_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)  # Soll
    counted_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))  # Ist
    unit: Mapped[str] = mapped_column(String(20), nullable=False)

    # Differenz wird berechnet
    difference: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))

    # Notizen
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Beziehungen
    count: Mapped["InventoryCount"] = relationship("InventoryCount", back_populates="items")

    def calculate_difference(self) -> Optional[Decimal]:
        """Berechnet die Differenz zwischen Soll und Ist"""
        if self.counted_quantity is None:
            return None
        self.difference = self.counted_quantity - self.system_quantity
        return self.difference

    def __repr__(self) -> str:
        return f"<InventoryCountItem(type={self.item_type.value}, diff={self.difference})>"


# Standard-Lagerorte für Microgreens-Produktion
STANDARD_LOCATIONS = [
    {"code": "LAGER-01", "name": "Hauptlager", "location_type": LocationType.LAGER},
    {"code": "KUEHL-01", "name": "Kühlraum 1", "location_type": LocationType.KUEHLRAUM,
     "temperature_min": Decimal("2"), "temperature_max": Decimal("6")},
    {"code": "REGAL-A", "name": "Produktionsregal A", "location_type": LocationType.REGAL, "capacity_trays": 100},
    {"code": "REGAL-B", "name": "Produktionsregal B", "location_type": LocationType.REGAL, "capacity_trays": 100},
    {"code": "KEIM-01", "name": "Keimraum", "location_type": LocationType.KEIMRAUM, "capacity_trays": 50},
    {"code": "VERSAND", "name": "Versandbereich", "location_type": LocationType.VERSAND},
]


# Imports für Type Hints
from app.models.seed import Seed
from app.models.product import Product
from app.models.production import GrowBatch, Harvest
from app.models.order import Order
