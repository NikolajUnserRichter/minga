from typing import Optional
"""
Pydantic Schemas für Lagerverwaltung (Inventory)
Mit Rückverfolgbarkeit und Bewegungshistorie
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from app.models.inventory import LocationType, MovementType, InventoryItemType


# ============================================================
# INVENTORY LOCATION SCHEMAS
# ============================================================

class InventoryLocationBase(BaseModel):
    """Basis-Schema für Lagerort"""
    code: str = Field(..., min_length=1, max_length=20, description="Lagerort-Code")
    name: str = Field(..., min_length=1, max_length=100, description="Lagerort-Name")
    location_type: LocationType = Field(..., description="Lagerort-Typ")


class InventoryLocationCreate(InventoryLocationBase):
    """Schema zum Erstellen eines Lagerorts"""
    parent_id: Optional[UUID] = Field(None, description="Übergeordneter Lagerort")
    capacity_trays: Optional[int] = Field(None, ge=0, description="Max. Trays")
    capacity_kg: Optional[Decimal] = Field(None, ge=0, description="Max. Gewicht (kg)")
    temperature_min: Optional[Decimal] = Field(None, description="Min. Temperatur °C")
    temperature_max: Optional[Decimal] = Field(None, description="Max. Temperatur °C")
    humidity_min: Optional[int] = Field(None, ge=0, le=100, description="Min. Luftfeuchtigkeit %")
    humidity_max: Optional[int] = Field(None, ge=0, le=100, description="Max. Luftfeuchtigkeit %")


class InventoryLocationUpdate(BaseModel):
    """Schema zum Aktualisieren eines Lagerorts"""
    name: Optional[str] = None
    parent_id: Optional[UUID] = None
    capacity_trays: Optional[int] = None
    capacity_kg: Optional[Decimal] = None
    temperature_min: Optional[Decimal] = None
    temperature_max: Optional[Decimal] = None
    humidity_min: Optional[int] = None
    humidity_max: Optional[int] = None
    is_active: Optional[bool] = None


class InventoryLocationResponse(InventoryLocationBase):
    """Schema für Lagerort-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    parent_id: Optional[UUID]
    capacity_trays: Optional[int]
    capacity_kg: Optional[Decimal]
    temperature_min: Optional[Decimal]
    temperature_max: Optional[Decimal]
    humidity_min: Optional[int]
    humidity_max: Optional[int]
    is_active: bool
    created_at: datetime

    # Expandiert
    parent_name: Optional[str] = None

    # Berechnete Felder
    current_occupancy_trays: Optional[int] = None
    current_occupancy_kg: Optional[Decimal] = None


class InventoryLocationListResponse(BaseModel):
    """Schema für Lagerort-Liste"""
    items: list[InventoryLocationResponse]
    total: int


# ============================================================
# SEED INVENTORY SCHEMAS
# ============================================================

class SeedInventoryBase(BaseModel):
    """Basis-Schema für Saatgut-Bestand"""
    batch_number: str = Field(..., min_length=1, max_length=50, description="Chargennummer")
    supplier_batch: Optional[str] = Field(None, max_length=50, description="Lieferanten-Charge")
    initial_quantity_kg: Decimal = Field(..., gt=0, description="Eingangsmenge (kg)")
    received_date: date = Field(..., description="Eingangsdatum")
    best_before_date: Optional[date] = Field(None, description="Mindesthaltbarkeit")


class SeedInventoryCreate(SeedInventoryBase):
    """Schema zum Erstellen eines Saatgut-Bestands"""
    seed_id: UUID = Field(..., description="Saatgut-ID")
    current_quantity_kg: Optional[Decimal] = Field(None, description="Aktuelle Menge (default = initial)")
    germination_rate: Optional[Decimal] = Field(None, ge=0, le=100, description="Keimrate %")
    quality_grade: Optional[str] = Field(None, max_length=10, description="Qualitätsstufe")
    production_date: Optional[date] = Field(None, description="Produktionsdatum")
    supplier_name: Optional[str] = Field(None, max_length=200, description="Lieferant")
    purchase_price_per_kg: Optional[Decimal] = Field(None, ge=0, description="Einkaufspreis pro kg")
    location_id: Optional[UUID] = Field(None, description="Lagerort-ID")
    is_organic: bool = Field(default=False, description="Bio-Zertifiziert?")
    organic_certificate: Optional[str] = Field(None, max_length=100, description="Bio-Zertifikat")


class SeedInventoryUpdate(BaseModel):
    """Schema zum Aktualisieren eines Saatgut-Bestands"""
    germination_rate: Optional[Decimal] = None
    quality_grade: Optional[str] = None
    location_id: Optional[UUID] = None
    is_blocked: Optional[bool] = None
    block_reason: Optional[str] = None
    is_active: Optional[bool] = None


class SeedInventoryResponse(SeedInventoryBase):
    """Schema für Saatgut-Bestand-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seed_id: UUID
    current_quantity_kg: Decimal
    germination_rate: Optional[Decimal]
    quality_grade: Optional[str]
    production_date: Optional[date]
    supplier_name: Optional[str]
    purchase_price_per_kg: Optional[Decimal]
    location_id: Optional[UUID]
    is_organic: bool
    organic_certificate: Optional[str]
    is_active: bool
    is_blocked: bool
    block_reason: Optional[str]
    created_at: datetime
    updated_at: datetime

    # Berechnete Felder
    is_expired: Optional[bool] = None
    days_until_expiry: Optional[int] = None

    # Expandierte Felder
    seed_name: Optional[str] = None
    location_name: Optional[str] = None


class SeedInventoryListResponse(BaseModel):
    """Schema für Saatgut-Bestands-Liste"""
    items: list[SeedInventoryResponse]
    total: int
    total_quantity_kg: Optional[Decimal] = None


# ============================================================
# FINISHED GOODS INVENTORY SCHEMAS
# ============================================================

class FinishedGoodsInventoryBase(BaseModel):
    """Basis-Schema für Fertigwaren-Bestand"""
    batch_number: str = Field(..., min_length=1, max_length=50, description="Chargennummer")
    initial_quantity_g: Decimal = Field(..., gt=0, description="Eingangsmenge (g)")
    harvest_date: date = Field(..., description="Erntedatum")
    best_before_date: date = Field(..., description="Mindesthaltbarkeit")


class FinishedGoodsInventoryCreate(FinishedGoodsInventoryBase):
    """Schema zum Erstellen eines Fertigwaren-Bestands"""
    product_id: UUID = Field(..., description="Produkt-ID")
    harvest_id: Optional[UUID] = Field(None, description="Ernte-ID (Rückverfolgung)")
    grow_batch_id: Optional[UUID] = Field(None, description="GrowBatch-ID (Rückverfolgung)")
    seed_inventory_id: Optional[UUID] = Field(None, description="Saatgut-Charge (Rückverfolgung)")
    current_quantity_g: Optional[Decimal] = Field(None, description="Aktuelle Menge (default = initial)")
    initial_units: Optional[int] = Field(None, ge=0, description="Eingangsmenge (Einheiten)")
    current_units: Optional[int] = Field(None, ge=0, description="Aktuelle Einheiten")
    unit_size_g: Optional[Decimal] = Field(None, gt=0, description="Gramm pro Einheit")
    quality_grade: Optional[int] = Field(None, ge=1, le=5, description="Qualitätsnote 1-5")
    quality_notes: Optional[str] = Field(None, description="Qualitätsnotizen")
    packed_date: Optional[date] = Field(None, description="Verpackungsdatum")
    location_id: Optional[UUID] = Field(None, description="Lagerort-ID")
    storage_temp_celsius: Optional[Decimal] = Field(None, description="Lagertemperatur °C")


class FinishedGoodsInventoryUpdate(BaseModel):
    """Schema zum Aktualisieren eines Fertigwaren-Bestands"""
    quality_grade: Optional[int] = None
    quality_notes: Optional[str] = None
    location_id: Optional[UUID] = None
    storage_temp_celsius: Optional[Decimal] = None
    is_reserved: Optional[bool] = None
    reserved_order_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class FinishedGoodsInventoryResponse(FinishedGoodsInventoryBase):
    """Schema für Fertigwaren-Bestand-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    harvest_id: Optional[UUID]
    grow_batch_id: Optional[UUID]
    seed_inventory_id: Optional[UUID]
    current_quantity_g: Decimal
    initial_units: Optional[int]
    current_units: Optional[int]
    unit_size_g: Optional[Decimal]
    quality_grade: Optional[int]
    quality_notes: Optional[str]
    packed_date: Optional[date]
    location_id: Optional[UUID]
    storage_temp_celsius: Optional[Decimal]
    is_active: bool
    is_reserved: bool
    reserved_order_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    # Berechnete Felder
    is_expired: Optional[bool] = None
    days_until_expiry: Optional[int] = None
    traceability_chain: Optional[dict] = None

    # Expandierte Felder
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    location_name: Optional[str] = None


class FinishedGoodsInventoryListResponse(BaseModel):
    """Schema für Fertigwaren-Bestands-Liste"""
    items: list[FinishedGoodsInventoryResponse]
    total: int
    total_quantity_g: Optional[Decimal] = None
    total_units: Optional[int] = None


# ============================================================
# PACKAGING INVENTORY SCHEMAS
# ============================================================

class PackagingInventoryBase(BaseModel):
    """Basis-Schema für Verpackungs-Bestand"""
    name: str = Field(..., min_length=1, max_length=200, description="Artikelname")
    sku: str = Field(..., min_length=1, max_length=50, description="Artikelnummer")
    description: Optional[str] = Field(None, description="Beschreibung")


class PackagingInventoryCreate(PackagingInventoryBase):
    """Schema zum Erstellen eines Verpackungs-Bestands"""
    current_quantity: int = Field(default=0, ge=0, description="Aktuelle Menge")
    min_quantity: int = Field(default=0, ge=0, description="Mindestbestand")
    reorder_quantity: Optional[int] = Field(None, ge=0, description="Nachbestellmenge")
    unit: str = Field(default="Stück", description="Einheit")
    supplier_name: Optional[str] = Field(None, max_length=200, description="Lieferant")
    supplier_sku: Optional[str] = Field(None, max_length=50, description="Lieferanten-Artikelnr.")
    purchase_price: Optional[Decimal] = Field(None, ge=0, description="Einkaufspreis")
    location_id: Optional[UUID] = Field(None, description="Lagerort-ID")


class PackagingInventoryUpdate(BaseModel):
    """Schema zum Aktualisieren eines Verpackungs-Bestands"""
    name: Optional[str] = None
    description: Optional[str] = None
    min_quantity: Optional[int] = None
    reorder_quantity: Optional[int] = None
    supplier_name: Optional[str] = None
    supplier_sku: Optional[str] = None
    purchase_price: Optional[Decimal] = None
    location_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class PackagingInventoryResponse(PackagingInventoryBase):
    """Schema für Verpackungs-Bestand-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    current_quantity: int
    min_quantity: int
    reorder_quantity: Optional[int]
    unit: str
    supplier_name: Optional[str]
    supplier_sku: Optional[str]
    purchase_price: Optional[Decimal]
    location_id: Optional[UUID]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Berechnete Felder
    needs_reorder: Optional[bool] = None

    # Expandierte Felder
    location_name: Optional[str] = None


class PackagingInventoryListResponse(BaseModel):
    """Schema für Verpackungs-Bestands-Liste"""
    items: list[PackagingInventoryResponse]
    total: int


# ============================================================
# INVENTORY MOVEMENT SCHEMAS
# ============================================================

class InventoryMovementBase(BaseModel):
    """Basis-Schema für Lagerbewegung"""
    movement_type: MovementType = Field(..., description="Bewegungsart")
    item_type: InventoryItemType = Field(..., description="Artikeltyp")
    quantity: Decimal = Field(..., description="Menge (+ Zugang, - Abgang)")
    unit: str = Field(..., description="Einheit")


class InventoryMovementCreate(InventoryMovementBase):
    """Schema zum Erstellen einer Lagerbewegung"""
    seed_inventory_id: Optional[UUID] = Field(None, description="Saatgut-Bestand-ID")
    finished_goods_id: Optional[UUID] = Field(None, description="Fertigwaren-Bestand-ID")
    packaging_id: Optional[UUID] = Field(None, description="Verpackungs-Bestand-ID")
    from_location_id: Optional[UUID] = Field(None, description="Von Lagerort")
    to_location_id: Optional[UUID] = Field(None, description="Nach Lagerort")
    order_id: Optional[UUID] = Field(None, description="Bestellungs-ID")
    order_item_id: Optional[UUID] = Field(None, description="Bestellposition-ID")
    grow_batch_id: Optional[UUID] = Field(None, description="GrowBatch-ID")
    harvest_id: Optional[UUID] = Field(None, description="Ernte-ID")
    created_by: Optional[str] = Field(None, max_length=100, description="Erstellt von")
    reason: Optional[str] = Field(None, description="Grund")
    reference_number: Optional[str] = Field(None, max_length=50, description="Referenznummer")
    movement_date: Optional[datetime] = Field(None, description="Bewegungsdatum")


class InventoryMovementResponse(InventoryMovementBase):
    """Schema für Lagerbewegung-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seed_inventory_id: Optional[UUID]
    finished_goods_id: Optional[UUID]
    packaging_id: Optional[UUID]
    quantity_before: Decimal
    quantity_after: Decimal
    from_location_id: Optional[UUID]
    to_location_id: Optional[UUID]
    order_id: Optional[UUID]
    order_item_id: Optional[UUID]
    grow_batch_id: Optional[UUID]
    harvest_id: Optional[UUID]
    created_by: Optional[str]
    reason: Optional[str]
    reference_number: Optional[str]
    movement_date: datetime
    created_at: datetime

    # Expandierte Felder
    item_name: Optional[str] = None
    from_location_name: Optional[str] = None
    to_location_name: Optional[str] = None


class InventoryMovementListResponse(BaseModel):
    """Schema für Lagerbewegungen-Liste"""
    items: list[InventoryMovementResponse]
    total: int


# ============================================================
# INVENTORY COUNT (INVENTUR) SCHEMAS
# ============================================================

class InventoryCountItemBase(BaseModel):
    """Basis-Schema für Inventur-Position"""
    item_type: InventoryItemType = Field(..., description="Artikeltyp")
    system_quantity: Decimal = Field(..., description="System-Bestand (Soll)")
    unit: str = Field(..., description="Einheit")


class InventoryCountItemCreate(InventoryCountItemBase):
    """Schema zum Erstellen einer Inventur-Position"""
    seed_inventory_id: Optional[UUID] = Field(None, description="Saatgut-Bestand-ID")
    finished_goods_id: Optional[UUID] = Field(None, description="Fertigwaren-Bestand-ID")
    packaging_id: Optional[UUID] = Field(None, description="Verpackungs-Bestand-ID")
    counted_quantity: Optional[Decimal] = Field(None, description="Gezählte Menge (Ist)")
    notes: Optional[str] = Field(None, description="Notizen")


class InventoryCountItemUpdate(BaseModel):
    """Schema zum Aktualisieren einer Inventur-Position"""
    counted_quantity: Optional[Decimal] = None
    notes: Optional[str] = None


class InventoryCountItemResponse(InventoryCountItemBase):
    """Schema für Inventur-Position-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    count_id: UUID
    seed_inventory_id: Optional[UUID]
    finished_goods_id: Optional[UUID]
    packaging_id: Optional[UUID]
    counted_quantity: Optional[Decimal]
    difference: Optional[Decimal]
    notes: Optional[str]

    # Expandierte Felder
    item_name: Optional[str] = None
    item_batch: Optional[str] = None


class InventoryCountBase(BaseModel):
    """Basis-Schema für Inventur"""
    count_date: date = Field(..., description="Inventurdatum")


class InventoryCountCreate(InventoryCountBase):
    """Schema zum Erstellen einer Inventur"""
    location_id: Optional[UUID] = Field(None, description="Lagerort (für Teil-Inventur)")
    notes: Optional[str] = Field(None, description="Notizen")
    counted_by: Optional[str] = Field(None, max_length=100, description="Gezählt von")


class InventoryCountUpdate(BaseModel):
    """Schema zum Aktualisieren einer Inventur"""
    status: Optional[str] = None
    notes: Optional[str] = None
    counted_by: Optional[str] = None


class InventoryCountResponse(InventoryCountBase):
    """Schema für Inventur-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    count_number: str
    status: str
    location_id: Optional[UUID]
    notes: Optional[str]
    counted_by: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    # Expandierte Felder
    location_name: Optional[str] = None

    # Berechnete Felder
    item_count: Optional[int] = None
    difference_count: Optional[int] = None


class InventoryCountDetailResponse(InventoryCountResponse):
    """Detailliertes Inventur-Schema mit Positionen"""
    items: list[InventoryCountItemResponse] = []


class InventoryCountListResponse(BaseModel):
    """Schema für Inventur-Liste"""
    items: list[InventoryCountResponse]
    total: int


# ============================================================
# STOCK OVERVIEW SCHEMAS
# ============================================================

class StockOverviewItem(BaseModel):
    """Schema für Bestandsübersicht-Eintrag"""
    product_id: Optional[UUID]
    product_name: str
    product_sku: Optional[str]
    category: str
    current_stock: Decimal
    unit: str
    min_stock: Optional[Decimal]
    location_count: int
    batch_count: int
    needs_reorder: bool
    earliest_expiry: Optional[date]
    days_to_expiry: Optional[int]


class StockOverviewResponse(BaseModel):
    """Schema für Bestandsübersicht"""
    items: list[StockOverviewItem]
    total: int
    low_stock_count: int
    expiring_soon_count: int  # Innerhalb 7 Tage


class TraceabilityResponse(BaseModel):
    """Schema für Rückverfolgbarkeit"""
    finished_goods_batch: str
    product_name: str
    harvest_date: Optional[date]
    harvest_id: Optional[UUID]
    grow_batch_id: Optional[UUID]
    grow_batch_sow_date: Optional[date]
    seed_inventory_id: Optional[UUID]
    seed_batch_number: Optional[str]
    seed_name: Optional[str]
    supplier: Optional[str]
    orders_delivered: Optional[list[dict]] = None
