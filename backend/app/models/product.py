"""
Produkt-Models: Product, ProductGroup, GrowPlan, PriceList
"""
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.types import Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.database import Base

if TYPE_CHECKING:
    from app.models.unit import UnitOfMeasure

from app.models.enums import TaxRate


class ProductCategory(str, Enum):
    """Produktkategorie"""
    MICROGREEN = "MICROGREEN"   # Verkaufsfähige Microgreens
    SEED = "SEED"               # Saatgut (Rohstoff)
    PACKAGING = "PACKAGING"     # Verpackungsmaterial
    BUNDLE = "BUNDLE"           # Produktbündel/Set


class ProductGroup(Base):
    """
    Produktgruppe für Kategorisierung und Reporting.
    Unterstützt Hierarchie (parent_id).
    """
    __tablename__ = "product_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Hierarchie
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("product_groups.id")
    )

    # Sortierung
    sort_order: Mapped[int] = mapped_column(default=0)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    parent: Mapped[Optional["ProductGroup"]] = relationship(
        "ProductGroup", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["ProductGroup"]] = relationship(
        "ProductGroup", back_populates="parent"
    )
    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="product_group"
    )

    def __repr__(self) -> str:
        return f"<ProductGroup(name='{self.name}')>"


class GrowPlan(Base):
    """
    Wachstumsplan für eine Microgreen-Sorte.
    Definiert alle Parameter für Produktion und Ertragsberechnung.
    """
    __tablename__ = "grow_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # Identifikation
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Saatgut-Referenz (welches Saatgut wird verwendet)
    seed_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("products.id", use_alter=True)
    )

    # Saatgut-Dichte
    seed_density_grams_per_tray: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    # Phasen (in Stunden/Tagen)
    soak_hours: Mapped[int] = mapped_column(Integer, default=0)
    blackout_days: Mapped[int] = mapped_column(Integer, default=0)
    germination_days: Mapped[int] = mapped_column(Integer, nullable=False)
    growth_days: Mapped[int] = mapped_column(Integer, nullable=False)

    # Erntefenster (Tage nach Aussaat)
    harvest_window_start_days: Mapped[int] = mapped_column(Integer, nullable=False)
    harvest_window_optimal_days: Mapped[int] = mapped_column(Integer, nullable=False)
    harvest_window_end_days: Mapped[int] = mapped_column(Integer, nullable=False)

    # Ertrag
    expected_yield_grams_per_tray: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    yield_variance_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("10")
    )

    # Verlustquote
    expected_loss_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("5")
    )

    # Umweltbedingungen
    temp_germination_celsius: Mapped[Decimal] = mapped_column(
        Numeric(4, 1), default=Decimal("20")
    )
    temp_growth_celsius: Mapped[Decimal] = mapped_column(
        Numeric(4, 1), default=Decimal("18")
    )
    humidity_percent: Mapped[int] = mapped_column(Integer, default=60)
    light_hours_per_day: Mapped[int] = mapped_column(Integer, default=12)

    # Notizen
    growing_notes: Mapped[Optional[str]] = mapped_column(Text)
    harvest_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    seed_product: Mapped[Optional["Product"]] = relationship(
        "Product", foreign_keys=[seed_product_id]
    )
    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="grow_plan", foreign_keys="Product.grow_plan_id"
    )

    @property
    def total_grow_days(self) -> int:
        """Gesamte Wachstumsdauer in Tagen"""
        return self.germination_days + self.growth_days

    def calculate_harvest_window(self, sow_date: date) -> dict:
        """Berechnet das Erntefenster für ein Aussaatdatum"""
        return {
            "earliest": sow_date + timedelta(days=self.harvest_window_start_days),
            "optimal": sow_date + timedelta(days=self.harvest_window_optimal_days),
            "latest": sow_date + timedelta(days=self.harvest_window_end_days)
        }

    def calculate_sow_date(self, target_harvest_date: date) -> date:
        """Berechnet das Aussaatdatum für ein gewünschtes Erntedatum"""
        return target_harvest_date - timedelta(days=self.harvest_window_optimal_days)

    def __repr__(self) -> str:
        return f"<GrowPlan(code='{self.code}', name='{self.name}')>"


class Product(Base):
    """
    Produkt - Microgreens, Saatgut, Verpackung.
    Zentrale Entität für Verkauf, Einkauf und Produktion.
    """
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # Identifikation
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    name_short: Mapped[Optional[str]] = mapped_column(String(50))  # Für Labels
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Klassifikation
    category: Mapped[ProductCategory] = mapped_column(
        SQLEnum(ProductCategory), nullable=False, index=True
    )
    product_group_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("product_groups.id")
    )

    # Einheiten
    base_unit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("units_of_measure.id"), nullable=False
    )
    # Verkaufseinheiten als JSON: [{unit_id, conversion_factor, is_default}]
    sales_units: Mapped[Optional[dict]] = mapped_column(JSON)

    # Preise
    base_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    cost_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    tax_rate: Mapped[TaxRate] = mapped_column(
        SQLEnum(TaxRate), default=TaxRate.REDUZIERT
    )

    # Microgreen-spezifisch
    grow_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("grow_plans.id", use_alter=True)
    )
    seed_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("seeds.id")
    )
    shelf_life_days: Mapped[Optional[int]] = mapped_column(Integer)
    storage_temp_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 1))
    storage_temp_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 1))

    # Saatgut-spezifisch
    seed_variety: Mapped[Optional[str]] = mapped_column(String(100))
    seed_supplier: Mapped[Optional[str]] = mapped_column(String(200))
    germination_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Verpackung
    packaging_type: Mapped[Optional[str]] = mapped_column(String(50))
    weight_per_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))

    # Bundle-Komponenten (für BUNDLE-Kategorie)
    bundle_components: Mapped[Optional[dict]] = mapped_column(JSON)
    bundle_components: Mapped[Optional[dict]] = mapped_column(JSON)
    # Format: [{"product_id": "uuid", "quantity": 1}]
    is_bundle: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status-Flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_sellable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_purchasable: Mapped[bool] = mapped_column(Boolean, default=False)

    # Bestandsführung
    track_inventory: Mapped[bool] = mapped_column(Boolean, default=True)
    min_stock_level: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    reorder_point: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    base_unit: Mapped["UnitOfMeasure"] = relationship("UnitOfMeasure")
    grow_plan: Mapped[Optional["GrowPlan"]] = relationship(
        "GrowPlan", back_populates="products", foreign_keys=[grow_plan_id]
    )
    product_group: Mapped[Optional["ProductGroup"]] = relationship(
        "ProductGroup", back_populates="products"
    )
    price_list_items: Mapped[list["PriceListItem"]] = relationship(
        "PriceListItem", back_populates="product"
    )

    def __repr__(self) -> str:
        return f"<Product(sku='{self.sku}', name='{self.name}')>"


class PriceList(Base):
    """
    Preisliste für verschiedene Kundengruppen.
    Ermöglicht unterschiedliche Preise für B2B, B2C, Sonderkonditionen.
    """
    __tablename__ = "price_lists"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )



    # Identifikation
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    # Gültigkeit
    valid_from: Mapped[Optional[date]] = mapped_column(Date)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)

    # Flags
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    items: Mapped[list["PriceListItem"]] = relationship(
        "PriceListItem", back_populates="price_list", cascade="all, delete-orphan"
    )

    def is_valid(self, check_date: Optional[date] = None) -> bool:
        """Prüft ob Preisliste zum angegebenen Datum gültig ist"""
        check = check_date or date.today()
        if not self.is_active:
            return False
        if self.valid_from and check < self.valid_from:
            return False
        if self.valid_until and check > self.valid_until:
            return False
        return True

    def __repr__(self) -> str:
        return f"<PriceList(name='{self.name}')>"


class PriceListItem(Base):
    """
    Produktpreis innerhalb einer Preisliste.
    Unterstützt Staffelpreise über min_quantity.
    """
    __tablename__ = "price_list_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # Referenzen
    price_list_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("price_lists.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id"), nullable=False
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("units_of_measure.id"), nullable=False
    )

    # Preis
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Staffelpreis (Mindestmenge)
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("1"))

    # Rabatt (optional)
    discount_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Gültigkeit
    valid_from: Mapped[Optional[date]] = mapped_column(Date)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    price_list: Mapped["PriceList"] = relationship(
        "PriceList", back_populates="items"
    )
    product: Mapped["Product"] = relationship(
        "Product", back_populates="price_list_items"
    )
    unit: Mapped["UnitOfMeasure"] = relationship("UnitOfMeasure")

    def __repr__(self) -> str:
        return f"<PriceListItem(product={self.product_id}, price={self.price})>"


# Standard Wachstumspläne für Seed-Daten
STANDARD_GROW_PLANS = [
    {
        "code": "GP-SUNFLOWER",
        "name": "Sonnenblumen Standard",
        "seed_density_grams_per_tray": Decimal("100"),
        "soak_hours": 8,
        "blackout_days": 3,
        "germination_days": 2,
        "growth_days": 8,
        "harvest_window_start_days": 9,
        "harvest_window_optimal_days": 11,
        "harvest_window_end_days": 14,
        "expected_yield_grams_per_tray": Decimal("350"),
        "expected_loss_percent": Decimal("5"),
        "temp_germination_celsius": Decimal("20"),
        "temp_growth_celsius": Decimal("18"),
        "humidity_percent": 65,
        "light_hours_per_day": 12,
        "growing_notes": "Täglich 2x gießen. Gute Belüftung wichtig.",
        "harvest_notes": "Knapp über dem Samen schneiden."
    },
    {
        "code": "GP-PEA",
        "name": "Erbsen Standard",
        "seed_density_grams_per_tray": Decimal("200"),
        "soak_hours": 12,
        "blackout_days": 2,
        "germination_days": 2,
        "growth_days": 10,
        "harvest_window_start_days": 11,
        "harvest_window_optimal_days": 13,
        "harvest_window_end_days": 16,
        "expected_yield_grams_per_tray": Decimal("400"),
        "expected_loss_percent": Decimal("3"),
        "temp_germination_celsius": Decimal("18"),
        "temp_growth_celsius": Decimal("16"),
        "humidity_percent": 60,
        "light_hours_per_day": 14,
        "growing_notes": "Rankhilfe optional. Kühler halten für besseren Geschmack.",
        "harvest_notes": "Erste Blattpaare mit Ranken ernten."
    },
    {
        "code": "GP-RADISH",
        "name": "Radieschen Standard",
        "seed_density_grams_per_tray": Decimal("30"),
        "soak_hours": 0,
        "blackout_days": 0,
        "germination_days": 1,
        "growth_days": 6,
        "harvest_window_start_days": 6,
        "harvest_window_optimal_days": 8,
        "harvest_window_end_days": 10,
        "expected_yield_grams_per_tray": Decimal("250"),
        "expected_loss_percent": Decimal("8"),
        "temp_germination_celsius": Decimal("20"),
        "temp_growth_celsius": Decimal("18"),
        "humidity_percent": 55,
        "light_hours_per_day": 10,
        "growing_notes": "Kein Einweichen nötig. Schnelle Keimung.",
        "harvest_notes": "Bei erstem echten Blattpaar ernten."
    },
    {
        "code": "GP-BROCCOLI",
        "name": "Brokkoli Standard",
        "seed_density_grams_per_tray": Decimal("25"),
        "soak_hours": 6,
        "blackout_days": 2,
        "germination_days": 2,
        "growth_days": 7,
        "harvest_window_start_days": 8,
        "harvest_window_optimal_days": 10,
        "harvest_window_end_days": 12,
        "expected_yield_grams_per_tray": Decimal("200"),
        "expected_loss_percent": Decimal("10"),
        "temp_germination_celsius": Decimal("20"),
        "temp_growth_celsius": Decimal("18"),
        "humidity_percent": 60,
        "light_hours_per_day": 12,
        "growing_notes": "Schimmelanfällig - gute Belüftung!",
        "harvest_notes": "Knapp über Substrat schneiden."
    },
    {
        "code": "GP-MUSTARD",
        "name": "Senf Standard",
        "seed_density_grams_per_tray": Decimal("20"),
        "soak_hours": 0,
        "blackout_days": 0,
        "germination_days": 1,
        "growth_days": 5,
        "harvest_window_start_days": 5,
        "harvest_window_optimal_days": 7,
        "harvest_window_end_days": 9,
        "expected_yield_grams_per_tray": Decimal("180"),
        "expected_loss_percent": Decimal("5"),
        "temp_germination_celsius": Decimal("22"),
        "temp_growth_celsius": Decimal("18"),
        "humidity_percent": 55,
        "light_hours_per_day": 10,
        "growing_notes": "Schnellwachsend. Nicht zu feucht halten.",
        "harvest_notes": "Jung ernten für milderen Geschmack."
    }
]
