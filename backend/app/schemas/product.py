from typing import Optional
"""
Pydantic Schemas für Produkte, GrowPlans und Preislisten
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from app.models.product import ProductCategory
from app.models.enums import TaxRate


# ============================================================
# PRODUCT GROUP SCHEMAS
# ============================================================

class ProductGroupBase(BaseModel):
    """Basis-Schema für Produktgruppe"""
    code: str = Field(..., min_length=1, max_length=20, description="Gruppenkürzel")
    name: str = Field(..., min_length=1, max_length=100, description="Gruppenname")
    description: Optional[str] = Field(None, description="Beschreibung")


class ProductGroupCreate(ProductGroupBase):
    """Schema zum Erstellen einer Produktgruppe"""
    parent_id: Optional[UUID] = Field(None, description="Übergeordnete Gruppe")


class ProductGroupUpdate(BaseModel):
    """Schema zum Aktualisieren einer Produktgruppe"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class ProductGroupResponse(ProductGroupBase):
    """Schema für Produktgruppen-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    parent_id: Optional[UUID]
    is_active: bool
    created_at: datetime

    # Expandiert
    parent_name: Optional[str] = None


class ProductGroupListResponse(BaseModel):
    """Schema für Produktgruppen-Liste"""
    items: list[ProductGroupResponse]
    total: int


# ============================================================
# GROW PLAN SCHEMAS
# ============================================================

class GrowPlanBase(BaseModel):
    """Basis-Schema für Wachstumsplan"""
    code: str = Field(..., min_length=1, max_length=20, description="Plan-Kürzel")
    name: str = Field(..., min_length=1, max_length=100, description="Plan-Name")
    description: Optional[str] = Field(None, description="Beschreibung")

    # Phasen
    soak_hours: int = Field(default=0, ge=0, description="Einweichzeit in Stunden")
    blackout_days: int = Field(default=0, ge=0, description="Dunkelphase in Tagen")
    germination_days: int = Field(..., ge=1, description="Keimzeit in Tagen")
    growth_days: int = Field(..., ge=1, description="Wachstumszeit in Tagen")

    # Erntefenster
    harvest_window_start_days: int = Field(..., ge=1, description="Erntefenster Start (Tage)")
    harvest_window_optimal_days: int = Field(..., ge=1, description="Optimaler Erntezeitpunkt (Tage)")
    harvest_window_end_days: int = Field(..., ge=1, description="Erntefenster Ende (Tage)")

    # Ertrag
    expected_yield_grams_per_tray: Decimal = Field(..., gt=0, description="Erwarteter Ertrag g/Tray")
    expected_loss_percent: Decimal = Field(default=Decimal("5"), ge=0, le=100, description="Erwartete Verlustquote %")


class GrowPlanCreate(GrowPlanBase):
    """Schema zum Erstellen eines GrowPlans"""
    optimal_temp_celsius: Optional[Decimal] = Field(None, description="Optimale Temperatur °C")
    optimal_humidity_percent: Optional[int] = Field(None, ge=0, le=100, description="Optimale Luftfeuchtigkeit %")
    light_hours_per_day: Optional[int] = Field(None, ge=0, le=24, description="Lichtstunden pro Tag")
    seed_density_grams_per_tray: Optional[Decimal] = Field(None, gt=0, description="Saatdichte g/Tray")


class GrowPlanUpdate(BaseModel):
    """Schema zum Aktualisieren eines GrowPlans"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    soak_hours: Optional[int] = None
    blackout_days: Optional[int] = None
    germination_days: Optional[int] = None
    growth_days: Optional[int] = None
    harvest_window_start_days: Optional[int] = None
    harvest_window_optimal_days: Optional[int] = None
    harvest_window_end_days: Optional[int] = None
    expected_yield_grams_per_tray: Optional[Decimal] = None
    expected_loss_percent: Optional[Decimal] = None
    optimal_temp_celsius: Optional[Decimal] = None
    optimal_humidity_percent: Optional[int] = None
    light_hours_per_day: Optional[int] = None
    seed_density_grams_per_tray: Optional[Decimal] = None
    is_active: Optional[bool] = None


class GrowPlanResponse(GrowPlanBase):
    """Schema für GrowPlan-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    optimal_temp_celsius: Optional[Decimal] = Field(validation_alias="temp_growth_celsius")
    optimal_humidity_percent: Optional[int] = Field(validation_alias="humidity_percent")
    light_hours_per_day: Optional[int]
    seed_density_grams_per_tray: Optional[Decimal]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Berechnete Felder
    total_days: Optional[int] = None


class GrowPlanListResponse(BaseModel):
    """Schema für GrowPlan-Liste"""
    items: list[GrowPlanResponse]
    total: int


# ============================================================
# PRICE LIST SCHEMAS
# ============================================================

class PriceListBase(BaseModel):
    """Basis-Schema für Preisliste"""
    code: str = Field(..., min_length=1, max_length=20, description="Preislisten-Kürzel")
    name: str = Field(..., min_length=1, max_length=100, description="Preislisten-Name")
    description: Optional[str] = Field(None, description="Beschreibung")
    currency: str = Field(default="EUR", max_length=3, description="Währung")


class PriceListCreate(PriceListBase):
    """Schema zum Erstellen einer Preisliste"""
    valid_from: Optional[date] = Field(None, description="Gültig ab")
    valid_until: Optional[date] = Field(None, description="Gültig bis")
    is_default: bool = Field(default=False, description="Standard-Preisliste?")


class PriceListUpdate(BaseModel):
    """Schema zum Aktualisieren einer Preisliste"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class PriceListResponse(PriceListBase):
    """Schema für Preislisten-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    valid_from: Optional[date]
    valid_until: Optional[date]
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Anzahl Preise
    item_count: Optional[int] = None


class PriceListListResponse(BaseModel):
    """Schema für Preislisten-Liste"""
    items: list[PriceListResponse]
    total: int


# Price List Item Schemas

class PriceListItemBase(BaseModel):
    """Basis-Schema für Preislisten-Position"""
    product_id: UUID = Field(..., description="Produkt-ID")
    unit_id: Optional[UUID] = Field(None, description="Einheit-ID")
    price: Decimal = Field(..., ge=0, description="Preis")
    min_quantity: Decimal = Field(default=Decimal("1"), ge=0, description="Mindestmenge für Staffelpreis")


class PriceListItemCreate(PriceListItemBase):
    """Schema zum Erstellen einer Preislisten-Position"""
    price_list_id: UUID = Field(..., description="Preislisten-ID")
    valid_from: Optional[date] = Field(None, description="Gültig ab")
    valid_until: Optional[date] = Field(None, description="Gültig bis")


class PriceListItemUpdate(BaseModel):
    """Schema zum Aktualisieren einer Preislisten-Position"""
    price: Optional[Decimal] = None
    min_quantity: Optional[Decimal] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    is_active: Optional[bool] = None


class PriceListItemResponse(PriceListItemBase):
    """Schema für Preislisten-Position-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    price_list_id: UUID
    valid_from: Optional[date]
    valid_until: Optional[date]
    is_active: bool
    created_at: datetime

    # Expandiert
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    unit_code: Optional[str] = None


class PriceListItemListResponse(BaseModel):
    """Schema für Preislisten-Positionen-Liste"""
    items: list[PriceListItemResponse]
    total: int


# ============================================================
# PRODUCT SCHEMAS
# ============================================================

class ProductBase(BaseModel):
    """Basis-Schema für Produkt"""
    sku: str = Field(..., min_length=1, max_length=50, description="Artikelnummer")
    name: str = Field(..., min_length=1, max_length=200, description="Produktname")
    description: Optional[str] = Field(None, description="Beschreibung")
    category: ProductCategory = Field(..., description="Produktkategorie")


class ProductCreate(ProductBase):
    """Schema zum Erstellen eines Produkts"""
    product_group_id: Optional[UUID] = Field(None, description="Produktgruppe")
    base_unit_id: Optional[UUID] = Field(None, description="Basis-Einheit")
    base_price: Optional[Decimal] = Field(None, ge=0, description="Basispreis")
    tax_rate: TaxRate = Field(default=TaxRate.REDUZIERT, description="MwSt-Satz")

    # Microgreen-spezifisch
    seed_id: Optional[UUID] = Field(None, description="Saatgut-Referenz")
    grow_plan_id: Optional[UUID] = Field(None, description="Wachstumsplan")
    seed_variety: Optional[str] = Field(None, max_length=100, description="Sorte")

    # Lager
    shelf_life_days: Optional[int] = Field(None, ge=0, description="Haltbarkeit in Tagen")
    storage_temp_min: Optional[Decimal] = Field(None, description="Min. Lagertemperatur °C")
    storage_temp_max: Optional[Decimal] = Field(None, description="Max. Lagertemperatur °C")
    min_stock_quantity: Optional[Decimal] = Field(None, ge=0, description="Mindestbestand")

    # Bundle
    is_bundle: bool = Field(default=False, description="Ist ein Bundle?")
    bundle_components: Optional[list[dict]] = Field(None, description="Bundle-Komponenten")


class ProductUpdate(BaseModel):
    """Schema zum Aktualisieren eines Produkts"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    product_group_id: Optional[UUID] = None
    base_unit_id: Optional[UUID] = None
    base_price: Optional[Decimal] = None
    tax_rate: Optional[TaxRate] = None
    seed_id: Optional[UUID] = None
    grow_plan_id: Optional[UUID] = None
    seed_variety: Optional[str] = None
    shelf_life_days: Optional[int] = None
    storage_temp_min: Optional[Decimal] = None
    storage_temp_max: Optional[Decimal] = None
    min_stock_quantity: Optional[Decimal] = None
    is_bundle: Optional[bool] = None
    bundle_components: Optional[list[dict]] = None
    is_active: Optional[bool] = None
    is_sellable: Optional[bool] = None


class ProductResponse(ProductBase):
    """Schema für Produkt-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_group_id: Optional[UUID]
    base_unit_id: Optional[UUID]
    base_price: Optional[Decimal]
    tax_rate: TaxRate
    seed_id: Optional[UUID]
    grow_plan_id: Optional[UUID]
    seed_variety: Optional[str]
    shelf_life_days: Optional[int]
    storage_temp_min: Optional[Decimal]
    storage_temp_max: Optional[Decimal]
    min_stock_quantity: Optional[Decimal] = Field(validation_alias="min_stock_level")
    is_bundle: bool
    bundle_components: Optional[list[dict]]
    is_active: bool
    is_sellable: bool
    created_at: datetime
    updated_at: datetime

    # Expandierte Felder
    product_group_name: Optional[str] = None
    base_unit_code: Optional[str] = None
    seed_name: Optional[str] = None
    grow_plan_name: Optional[str] = None

    # Berechnete Felder
    current_stock: Optional[Decimal] = None


class ProductListResponse(BaseModel):
    """Schema für Produkt-Liste"""
    items: list[ProductResponse]
    total: int


class ProductDetailResponse(ProductResponse):
    """Detailliertes Produkt-Schema mit allen Relationen"""
    grow_plan: Optional[GrowPlanResponse] = None
    prices: Optional[list[PriceListItemResponse]] = None
