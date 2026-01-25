"""
Maßeinheiten-Models: UnitOfMeasure und UnitConversion
"""
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from sqlalchemy import String, Numeric, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class UnitCategory(str, Enum):
    """Kategorie der Maßeinheit"""
    WEIGHT = "WEIGHT"       # Gewicht (g, kg)
    VOLUME = "VOLUME"       # Volumen (ml, l)
    COUNT = "COUNT"         # Stückzahl
    CONTAINER = "CONTAINER" # Container (Tray, Schale, Bund)


class UnitOfMeasure(Base):
    """
    Maßeinheit mit Umrechnungsfaktor zur Basiseinheit.

    Beispiele:
    - GRAM (Basiseinheit für WEIGHT, factor=1)
    - KILOGRAM (factor=1000 zu GRAM)
    - TRAY (Container, produktspezifische Umrechnung)
    """
    __tablename__ = "units_of_measure"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Identifikation
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(10))

    # Kategorie
    category: Mapped[UnitCategory] = mapped_column(
        SQLEnum(UnitCategory), nullable=False
    )

    # Umrechnung zur Basiseinheit der Kategorie
    base_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id")
    )
    conversion_factor: Mapped[Decimal] = mapped_column(
        Numeric(15, 6), default=Decimal("1")
    )

    # Flags
    is_base_unit: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Sortierung
    sort_order: Mapped[int] = mapped_column(default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Self-Reference für Basiseinheit
    base_unit: Mapped["UnitOfMeasure | None"] = relationship(
        "UnitOfMeasure", remote_side=[id], foreign_keys=[base_unit_id]
    )

    def convert_to_base(self, quantity: Decimal) -> Decimal:
        """Konvertiert Menge in Basiseinheit"""
        return quantity * self.conversion_factor

    def convert_from_base(self, quantity: Decimal) -> Decimal:
        """Konvertiert von Basiseinheit in diese Einheit"""
        if self.conversion_factor == 0:
            return Decimal(0)
        return quantity / self.conversion_factor

    def __repr__(self) -> str:
        return f"<UnitOfMeasure(code='{self.code}', name='{self.name}')>"


class UnitConversion(Base):
    """
    Produktspezifische Umrechnungen zwischen Einheiten.

    Beispiel:
    - 1 TRAY Sonnenblumen = 350g (produktspezifisch)
    - 1 SCHALE_100G = 100g (allgemein)
    """
    __tablename__ = "unit_conversions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Produkt (optional - NULL = allgemeine Umrechnung)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id")
    )

    # Von-Nach Einheiten
    from_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=False
    )
    to_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=False
    )

    # Umrechnungsfaktor (from_unit * factor = to_unit)
    factor: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    from_unit: Mapped["UnitOfMeasure"] = relationship(
        "UnitOfMeasure", foreign_keys=[from_unit_id]
    )
    to_unit: Mapped["UnitOfMeasure"] = relationship(
        "UnitOfMeasure", foreign_keys=[to_unit_id]
    )

    def __repr__(self) -> str:
        return f"<UnitConversion(from={self.from_unit_id}, to={self.to_unit_id}, factor={self.factor})>"


# Standard-Einheiten für Seed-Daten
STANDARD_UNITS = [
    # Gewicht (Basis: Gramm)
    {
        "code": "G",
        "name": "Gramm",
        "symbol": "g",
        "category": UnitCategory.WEIGHT,
        "is_base_unit": True,
        "conversion_factor": Decimal("1"),
        "sort_order": 1
    },
    {
        "code": "KG",
        "name": "Kilogramm",
        "symbol": "kg",
        "category": UnitCategory.WEIGHT,
        "is_base_unit": False,
        "conversion_factor": Decimal("1000"),
        "sort_order": 2
    },
    {
        "code": "MG",
        "name": "Milligramm",
        "symbol": "mg",
        "category": UnitCategory.WEIGHT,
        "is_base_unit": False,
        "conversion_factor": Decimal("0.001"),
        "sort_order": 0
    },

    # Stückzahl (Basis: Stück)
    {
        "code": "PC",
        "name": "Stück",
        "symbol": "Stk",
        "category": UnitCategory.COUNT,
        "is_base_unit": True,
        "conversion_factor": Decimal("1"),
        "sort_order": 1
    },
    {
        "code": "DZ",
        "name": "Dutzend",
        "symbol": "Dtz",
        "category": UnitCategory.COUNT,
        "is_base_unit": False,
        "conversion_factor": Decimal("12"),
        "sort_order": 2
    },

    # Container
    {
        "code": "TRAY",
        "name": "Tray",
        "symbol": "Tray",
        "category": UnitCategory.CONTAINER,
        "is_base_unit": False,
        "conversion_factor": Decimal("1"),
        "sort_order": 1
    },
    {
        "code": "SCHALE_50G",
        "name": "Schale 50g",
        "symbol": "50g",
        "category": UnitCategory.CONTAINER,
        "is_base_unit": False,
        "conversion_factor": Decimal("50"),  # 50g
        "sort_order": 2
    },
    {
        "code": "SCHALE_100G",
        "name": "Schale 100g",
        "symbol": "100g",
        "category": UnitCategory.CONTAINER,
        "is_base_unit": False,
        "conversion_factor": Decimal("100"),  # 100g
        "sort_order": 3
    },
    {
        "code": "SCHALE_150G",
        "name": "Schale 150g",
        "symbol": "150g",
        "category": UnitCategory.CONTAINER,
        "is_base_unit": False,
        "conversion_factor": Decimal("150"),  # 150g
        "sort_order": 4
    },
    {
        "code": "BUND",
        "name": "Bund",
        "symbol": "Bund",
        "category": UnitCategory.CONTAINER,
        "is_base_unit": False,
        "conversion_factor": Decimal("1"),
        "sort_order": 5
    },
]
