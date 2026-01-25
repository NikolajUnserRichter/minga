"""
Pydantic Schemas für Produkte, GrowPlans und Preislisten
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from app.models.product import ProductCategory
from app.models.invoice import TaxRate


# ============================================================
# PRODUCT GROUP SCHEMAS
# ============================================================

class ProductGroupBase(BaseModel):
    """Basis-Schema für Produktgruppe"""
    code: str = Field(..., min_length=1, max_length=20, description="Gruppenkürzel")
    name: str = Field(..., min_length=1, max_length=100, description="Gruppenname")
    description: str | None = Field(None, description="Beschreibung")


class ProductGroupCreate(ProductGroupBase):
    """Schema zum Erstellen einer Produktgruppe"""
    parent_id: UUID | None = Field(None, description="Übergeordnete Gruppe")


class ProductGroupUpdate(BaseModel):
    """Schema zum Aktualisieren einer Produktgruppe"""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    parent_id: UUID | None = None
    is_active: bool | None = None


class ProductGroupResponse(ProductGroupBase):
    """Schema für Produktgruppen-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    parent_id: UUID | None
    is_active: bool
    created_at: datetime

    # Expandiert
    parent_name: str | None = None


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
    description: str | None = Field(None, description="Beschreibung")

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
    optimal_temp_celsius: Decimal | None = Field(None, description="Optimale Temperatur °C")
    optimal_humidity_percent: int | None = Field(None, ge=0, le=100, description="Optimale Luftfeuchtigkeit %")
    light_hours_per_day: int | None = Field(None, ge=0, le=24, description="Lichtstunden pro Tag")
    seed_density_grams_per_tray: Decimal | None = Field(None, gt=0, description="Saatdichte g/Tray")


class GrowPlanUpdate(BaseModel):
    """Schema zum Aktualisieren eines GrowPlans"""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    soak_hours: int | None = None
    blackout_days: int | None = None
    germination_days: int | None = None
    growth_days: int | None = None
    harvest_window_start_days: int | None = None
    harvest_window_optimal_days: int | None = None
    harvest_window_end_days: int | None = None
    expected_yield_grams_per_tray: Decimal | None = None
    expected_loss_percent: Decimal | None = None
    optimal_temp_celsius: Decimal | None = None
    optimal_humidity_percent: int | None = None
    light_hours_per_day: int | None = None
    seed_density_grams_per_tray: Decimal | None = None
    is_active: bool | None = None


class GrowPlanResponse(GrowPlanBase):
    """Schema für GrowPlan-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    optimal_temp_celsius: Decimal | None
    optimal_humidity_percent: int | None
    light_hours_per_day: int | None
    seed_density_grams_per_tray: Decimal | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Berechnete Felder
    total_days: int | None = None


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
    description: str | None = Field(None, description="Beschreibung")
    currency: str = Field(default="EUR", max_length=3, description="Währung")


class PriceListCreate(PriceListBase):
    """Schema zum Erstellen einer Preisliste"""
    valid_from: date | None = Field(None, description="Gültig ab")
    valid_until: date | None = Field(None, description="Gültig bis")
    is_default: bool = Field(default=False, description="Standard-Preisliste?")


class PriceListUpdate(BaseModel):
    """Schema zum Aktualisieren einer Preisliste"""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class PriceListResponse(PriceListBase):
    """Schema für Preislisten-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    valid_from: date | None
    valid_until: date | None
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Anzahl Preise
    item_count: int | None = None


class PriceListListResponse(BaseModel):
    """Schema für Preislisten-Liste"""
    items: list[PriceListResponse]
    total: int


# Price List Item Schemas

class PriceListItemBase(BaseModel):
    """Basis-Schema für Preislisten-Position"""
    product_id: UUID = Field(..., description="Produkt-ID")
    unit_id: UUID | None = Field(None, description="Einheit-ID")
    price: Decimal = Field(..., ge=0, description="Preis")
    min_quantity: Decimal = Field(default=Decimal("1"), ge=0, description="Mindestmenge für Staffelpreis")


class PriceListItemCreate(PriceListItemBase):
    """Schema zum Erstellen einer Preislisten-Position"""
    price_list_id: UUID = Field(..., description="Preislisten-ID")
    valid_from: date | None = Field(None, description="Gültig ab")
    valid_until: date | None = Field(None, description="Gültig bis")


class PriceListItemUpdate(BaseModel):
    """Schema zum Aktualisieren einer Preislisten-Position"""
    price: Decimal | None = None
    min_quantity: Decimal | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    is_active: bool | None = None


class PriceListItemResponse(PriceListItemBase):
    """Schema für Preislisten-Position-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    price_list_id: UUID
    valid_from: date | None
    valid_until: date | None
    is_active: bool
    created_at: datetime

    # Expandiert
    product_name: str | None = None
    product_sku: str | None = None
    unit_code: str | None = None


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
    description: str | None = Field(None, description="Beschreibung")
    category: ProductCategory = Field(..., description="Produktkategorie")


class ProductCreate(ProductBase):
    """Schema zum Erstellen eines Produkts"""
    product_group_id: UUID | None = Field(None, description="Produktgruppe")
    base_unit_id: UUID | None = Field(None, description="Basis-Einheit")
    base_price: Decimal | None = Field(None, ge=0, description="Basispreis")
    tax_rate: TaxRate = Field(default=TaxRate.REDUZIERT, description="MwSt-Satz")

    # Microgreen-spezifisch
    seed_id: UUID | None = Field(None, description="Saatgut-Referenz")
    grow_plan_id: UUID | None = Field(None, description="Wachstumsplan")
    seed_variety: str | None = Field(None, max_length=100, description="Sorte")

    # Lager
    shelf_life_days: int | None = Field(None, ge=0, description="Haltbarkeit in Tagen")
    storage_temp_min: Decimal | None = Field(None, description="Min. Lagertemperatur °C")
    storage_temp_max: Decimal | None = Field(None, description="Max. Lagertemperatur °C")
    min_stock_quantity: Decimal | None = Field(None, ge=0, description="Mindestbestand")

    # Bundle
    is_bundle: bool = Field(default=False, description="Ist ein Bundle?")
    bundle_components: list[dict] | None = Field(None, description="Bundle-Komponenten")


class ProductUpdate(BaseModel):
    """Schema zum Aktualisieren eines Produkts"""
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    product_group_id: UUID | None = None
    base_unit_id: UUID | None = None
    base_price: Decimal | None = None
    tax_rate: TaxRate | None = None
    seed_id: UUID | None = None
    grow_plan_id: UUID | None = None
    seed_variety: str | None = None
    shelf_life_days: int | None = None
    storage_temp_min: Decimal | None = None
    storage_temp_max: Decimal | None = None
    min_stock_quantity: Decimal | None = None
    is_bundle: bool | None = None
    bundle_components: list[dict] | None = None
    is_active: bool | None = None
    is_sellable: bool | None = None


class ProductResponse(ProductBase):
    """Schema für Produkt-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_group_id: UUID | None
    base_unit_id: UUID | None
    base_price: Decimal | None
    tax_rate: TaxRate
    seed_id: UUID | None
    grow_plan_id: UUID | None
    seed_variety: str | None
    shelf_life_days: int | None
    storage_temp_min: Decimal | None
    storage_temp_max: Decimal | None
    min_stock_quantity: Decimal | None
    is_bundle: bool
    bundle_components: list[dict] | None
    is_active: bool
    is_sellable: bool
    created_at: datetime
    updated_at: datetime

    # Expandierte Felder
    product_group_name: str | None = None
    base_unit_code: str | None = None
    seed_name: str | None = None
    grow_plan_name: str | None = None

    # Berechnete Felder
    current_stock: Decimal | None = None


class ProductListResponse(BaseModel):
    """Schema für Produkt-Liste"""
    items: list[ProductResponse]
    total: int


class ProductDetailResponse(ProductResponse):
    """Detailliertes Produkt-Schema mit allen Relationen"""
    grow_plan: GrowPlanResponse | None = None
    prices: list[PriceListItemResponse] | None = None
