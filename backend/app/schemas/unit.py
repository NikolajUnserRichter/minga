"""
Pydantic Schemas für Maßeinheiten (Units of Measure)
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from app.models.unit import UnitCategory


class UnitOfMeasureBase(BaseModel):
    """Basis-Schema für Maßeinheit"""
    code: str = Field(..., min_length=1, max_length=10, description="Einheitenkürzel (z.B. KG, G)")
    name: str = Field(..., min_length=1, max_length=50, description="Einheitenname")
    symbol: str | None = Field(None, max_length=10, description="Symbol (z.B. kg, g)")
    category: UnitCategory = Field(..., description="Kategorie (WEIGHT, VOLUME, COUNT, CONTAINER)")


class UnitOfMeasureCreate(UnitOfMeasureBase):
    """Schema zum Erstellen einer Maßeinheit"""
    base_unit_id: UUID | None = Field(None, description="Basis-Einheit für Umrechnung")
    conversion_factor: Decimal = Field(default=Decimal("1"), description="Umrechnungsfaktor zur Basiseinheit")
    is_base_unit: bool = Field(default=False, description="Ist dies eine Basiseinheit?")


class UnitOfMeasureUpdate(BaseModel):
    """Schema zum Aktualisieren einer Maßeinheit"""
    name: str | None = Field(None, min_length=1, max_length=50)
    symbol: str | None = None
    conversion_factor: Decimal | None = None
    is_active: bool | None = None


class UnitOfMeasureResponse(UnitOfMeasureBase):
    """Schema für Maßeinheit-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    base_unit_id: UUID | None
    conversion_factor: Decimal
    is_base_unit: bool
    is_active: bool
    created_at: datetime

    # Expandiertes Feld
    base_unit_code: str | None = None


class UnitOfMeasureListResponse(BaseModel):
    """Schema für Maßeinheiten-Liste"""
    items: list[UnitOfMeasureResponse]
    total: int


# Unit Conversion Schemas

class UnitConversionBase(BaseModel):
    """Basis-Schema für Einheiten-Umrechnung"""
    from_unit_id: UUID = Field(..., description="Ausgangs-Einheit")
    to_unit_id: UUID = Field(..., description="Ziel-Einheit")
    factor: Decimal = Field(..., gt=0, description="Umrechnungsfaktor")


class UnitConversionCreate(UnitConversionBase):
    """Schema zum Erstellen einer Umrechnung"""
    product_id: UUID | None = Field(None, description="Produkt-spezifische Umrechnung")


class UnitConversionResponse(UnitConversionBase):
    """Schema für Umrechnungs-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID | None
    is_active: bool
    created_at: datetime

    # Expandierte Felder
    from_unit_code: str | None = None
    to_unit_code: str | None = None


class UnitConversionListResponse(BaseModel):
    """Schema für Umrechnungs-Liste"""
    items: list[UnitConversionResponse]
    total: int


# Hilfschemas

class ConvertUnitsRequest(BaseModel):
    """Request zum Umrechnen von Einheiten"""
    value: Decimal = Field(..., description="Zu konvertierender Wert")
    from_unit_id: UUID = Field(..., description="Ausgangs-Einheit")
    to_unit_id: UUID = Field(..., description="Ziel-Einheit")
    product_id: UUID | None = Field(None, description="Produkt für spezifische Umrechnung")


class ConvertUnitsResponse(BaseModel):
    """Response für Einheiten-Umrechnung"""
    original_value: Decimal
    converted_value: Decimal
    from_unit: str
    to_unit: str
    factor: Decimal
