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
    parent_id: UUID | None = Field(None, description="Übergeordneter Lagerort")
    capacity_trays: int | None = Field(None, ge=0, description="Max. Trays")
    capacity_kg: Decimal | None = Field(None, ge=0, description="Max. Gewicht (kg)")
    temperature_min: Decimal | None = Field(None, description="Min. Temperatur °C")
    temperature_max: Decimal | None = Field(None, description="Max. Temperatur °C")
    humidity_min: int | None = Field(None, ge=0, le=100, description="Min. Luftfeuchtigkeit %")
    humidity_max: int | None = Field(None, ge=0, le=100, description="Max. Luftfeuchtigkeit %")


class InventoryLocationUpdate(BaseModel):
    """Schema zum Aktualisieren eines Lagerorts"""
    name: str | None = None
    parent_id: UUID | None = None
    capacity_trays: int | None = None
    capacity_kg: Decimal | None = None
    temperature_min: Decimal | None = None
    temperature_max: Decimal | None = None
    humidity_min: int | None = None
    humidity_max: int | None = None
    is_active: bool | None = None


class InventoryLocationResponse(InventoryLocationBase):
    """Schema für Lagerort-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    parent_id: UUID | None
    capacity_trays: int | None
    capacity_kg: Decimal | None
    temperature_min: Decimal | None
    temperature_max: Decimal | None
    humidity_min: int | None
    humidity_max: int | None
    is_active: bool
    created_at: datetime

    # Expandiert
    parent_name: str | None = None

    # Berechnete Felder
    current_occupancy_trays: int | None = None
    current_occupancy_kg: Decimal | None = None


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
    supplier_batch: str | None = Field(None, max_length=50, description="Lieferanten-Charge")
    initial_quantity_kg: Decimal = Field(..., gt=0, description="Eingangsmenge (kg)")
    received_date: date = Field(..., description="Eingangsdatum")
    best_before_date: date | None = Field(None, description="Mindesthaltbarkeit")


class SeedInventoryCreate(SeedInventoryBase):
    """Schema zum Erstellen eines Saatgut-Bestands"""
    seed_id: UUID = Field(..., description="Saatgut-ID")
    current_quantity_kg: Decimal | None = Field(None, description="Aktuelle Menge (default = initial)")
    germination_rate: Decimal | None = Field(None, ge=0, le=100, description="Keimrate %")
    quality_grade: str | None = Field(None, max_length=10, description="Qualitätsstufe")
    production_date: date | None = Field(None, description="Produktionsdatum")
    supplier_name: str | None = Field(None, max_length=200, description="Lieferant")
    purchase_price_per_kg: Decimal | None = Field(None, ge=0, description="Einkaufspreis pro kg")
    location_id: UUID | None = Field(None, description="Lagerort-ID")
    is_organic: bool = Field(default=False, description="Bio-Zertifiziert?")
    organic_certificate: str | None = Field(None, max_length=100, description="Bio-Zertifikat")


class SeedInventoryUpdate(BaseModel):
    """Schema zum Aktualisieren eines Saatgut-Bestands"""
    germination_rate: Decimal | None = None
    quality_grade: str | None = None
    location_id: UUID | None = None
    is_blocked: bool | None = None
    block_reason: str | None = None
    is_active: bool | None = None


class SeedInventoryResponse(SeedInventoryBase):
    """Schema für Saatgut-Bestand-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seed_id: UUID
    current_quantity_kg: Decimal
    germination_rate: Decimal | None
    quality_grade: str | None
    production_date: date | None
    supplier_name: str | None
    purchase_price_per_kg: Decimal | None
    location_id: UUID | None
    is_organic: bool
    organic_certificate: str | None
    is_active: bool
    is_blocked: bool
    block_reason: str | None
    created_at: datetime
    updated_at: datetime

    # Berechnete Felder
    is_expired: bool | None = None
    days_until_expiry: int | None = None

    # Expandierte Felder
    seed_name: str | None = None
    location_name: str | None = None


class SeedInventoryListResponse(BaseModel):
    """Schema für Saatgut-Bestands-Liste"""
    items: list[SeedInventoryResponse]
    total: int
    total_quantity_kg: Decimal | None = None


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
    harvest_id: UUID | None = Field(None, description="Ernte-ID (Rückverfolgung)")
    grow_batch_id: UUID | None = Field(None, description="GrowBatch-ID (Rückverfolgung)")
    seed_inventory_id: UUID | None = Field(None, description="Saatgut-Charge (Rückverfolgung)")
    current_quantity_g: Decimal | None = Field(None, description="Aktuelle Menge (default = initial)")
    initial_units: int | None = Field(None, ge=0, description="Eingangsmenge (Einheiten)")
    current_units: int | None = Field(None, ge=0, description="Aktuelle Einheiten")
    unit_size_g: Decimal | None = Field(None, gt=0, description="Gramm pro Einheit")
    quality_grade: int | None = Field(None, ge=1, le=5, description="Qualitätsnote 1-5")
    quality_notes: str | None = Field(None, description="Qualitätsnotizen")
    packed_date: date | None = Field(None, description="Verpackungsdatum")
    location_id: UUID | None = Field(None, description="Lagerort-ID")
    storage_temp_celsius: Decimal | None = Field(None, description="Lagertemperatur °C")


class FinishedGoodsInventoryUpdate(BaseModel):
    """Schema zum Aktualisieren eines Fertigwaren-Bestands"""
    quality_grade: int | None = None
    quality_notes: str | None = None
    location_id: UUID | None = None
    storage_temp_celsius: Decimal | None = None
    is_reserved: bool | None = None
    reserved_order_id: UUID | None = None
    is_active: bool | None = None


class FinishedGoodsInventoryResponse(FinishedGoodsInventoryBase):
    """Schema für Fertigwaren-Bestand-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    harvest_id: UUID | None
    grow_batch_id: UUID | None
    seed_inventory_id: UUID | None
    current_quantity_g: Decimal
    initial_units: int | None
    current_units: int | None
    unit_size_g: Decimal | None
    quality_grade: int | None
    quality_notes: str | None
    packed_date: date | None
    location_id: UUID | None
    storage_temp_celsius: Decimal | None
    is_active: bool
    is_reserved: bool
    reserved_order_id: UUID | None
    created_at: datetime
    updated_at: datetime

    # Berechnete Felder
    is_expired: bool | None = None
    days_until_expiry: int | None = None
    traceability_chain: dict | None = None

    # Expandierte Felder
    product_name: str | None = None
    product_sku: str | None = None
    location_name: str | None = None


class FinishedGoodsInventoryListResponse(BaseModel):
    """Schema für Fertigwaren-Bestands-Liste"""
    items: list[FinishedGoodsInventoryResponse]
    total: int
    total_quantity_g: Decimal | None = None
    total_units: int | None = None


# ============================================================
# PACKAGING INVENTORY SCHEMAS
# ============================================================

class PackagingInventoryBase(BaseModel):
    """Basis-Schema für Verpackungs-Bestand"""
    name: str = Field(..., min_length=1, max_length=200, description="Artikelname")
    sku: str = Field(..., min_length=1, max_length=50, description="Artikelnummer")
    description: str | None = Field(None, description="Beschreibung")


class PackagingInventoryCreate(PackagingInventoryBase):
    """Schema zum Erstellen eines Verpackungs-Bestands"""
    current_quantity: int = Field(default=0, ge=0, description="Aktuelle Menge")
    min_quantity: int = Field(default=0, ge=0, description="Mindestbestand")
    reorder_quantity: int | None = Field(None, ge=0, description="Nachbestellmenge")
    unit: str = Field(default="Stück", description="Einheit")
    supplier_name: str | None = Field(None, max_length=200, description="Lieferant")
    supplier_sku: str | None = Field(None, max_length=50, description="Lieferanten-Artikelnr.")
    purchase_price: Decimal | None = Field(None, ge=0, description="Einkaufspreis")
    location_id: UUID | None = Field(None, description="Lagerort-ID")


class PackagingInventoryUpdate(BaseModel):
    """Schema zum Aktualisieren eines Verpackungs-Bestands"""
    name: str | None = None
    description: str | None = None
    min_quantity: int | None = None
    reorder_quantity: int | None = None
    supplier_name: str | None = None
    supplier_sku: str | None = None
    purchase_price: Decimal | None = None
    location_id: UUID | None = None
    is_active: bool | None = None


class PackagingInventoryResponse(PackagingInventoryBase):
    """Schema für Verpackungs-Bestand-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    current_quantity: int
    min_quantity: int
    reorder_quantity: int | None
    unit: str
    supplier_name: str | None
    supplier_sku: str | None
    purchase_price: Decimal | None
    location_id: UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Berechnete Felder
    needs_reorder: bool | None = None

    # Expandierte Felder
    location_name: str | None = None


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
    seed_inventory_id: UUID | None = Field(None, description="Saatgut-Bestand-ID")
    finished_goods_id: UUID | None = Field(None, description="Fertigwaren-Bestand-ID")
    packaging_id: UUID | None = Field(None, description="Verpackungs-Bestand-ID")
    from_location_id: UUID | None = Field(None, description="Von Lagerort")
    to_location_id: UUID | None = Field(None, description="Nach Lagerort")
    order_id: UUID | None = Field(None, description="Bestellungs-ID")
    order_item_id: UUID | None = Field(None, description="Bestellposition-ID")
    grow_batch_id: UUID | None = Field(None, description="GrowBatch-ID")
    harvest_id: UUID | None = Field(None, description="Ernte-ID")
    created_by: str | None = Field(None, max_length=100, description="Erstellt von")
    reason: str | None = Field(None, description="Grund")
    reference_number: str | None = Field(None, max_length=50, description="Referenznummer")
    movement_date: datetime | None = Field(None, description="Bewegungsdatum")


class InventoryMovementResponse(InventoryMovementBase):
    """Schema für Lagerbewegung-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seed_inventory_id: UUID | None
    finished_goods_id: UUID | None
    packaging_id: UUID | None
    quantity_before: Decimal
    quantity_after: Decimal
    from_location_id: UUID | None
    to_location_id: UUID | None
    order_id: UUID | None
    order_item_id: UUID | None
    grow_batch_id: UUID | None
    harvest_id: UUID | None
    created_by: str | None
    reason: str | None
    reference_number: str | None
    movement_date: datetime
    created_at: datetime

    # Expandierte Felder
    item_name: str | None = None
    from_location_name: str | None = None
    to_location_name: str | None = None


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
    seed_inventory_id: UUID | None = Field(None, description="Saatgut-Bestand-ID")
    finished_goods_id: UUID | None = Field(None, description="Fertigwaren-Bestand-ID")
    packaging_id: UUID | None = Field(None, description="Verpackungs-Bestand-ID")
    counted_quantity: Decimal | None = Field(None, description="Gezählte Menge (Ist)")
    notes: str | None = Field(None, description="Notizen")


class InventoryCountItemUpdate(BaseModel):
    """Schema zum Aktualisieren einer Inventur-Position"""
    counted_quantity: Decimal | None = None
    notes: str | None = None


class InventoryCountItemResponse(InventoryCountItemBase):
    """Schema für Inventur-Position-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    count_id: UUID
    seed_inventory_id: UUID | None
    finished_goods_id: UUID | None
    packaging_id: UUID | None
    counted_quantity: Decimal | None
    difference: Decimal | None
    notes: str | None

    # Expandierte Felder
    item_name: str | None = None
    item_batch: str | None = None


class InventoryCountBase(BaseModel):
    """Basis-Schema für Inventur"""
    count_date: date = Field(..., description="Inventurdatum")


class InventoryCountCreate(InventoryCountBase):
    """Schema zum Erstellen einer Inventur"""
    location_id: UUID | None = Field(None, description="Lagerort (für Teil-Inventur)")
    notes: str | None = Field(None, description="Notizen")
    counted_by: str | None = Field(None, max_length=100, description="Gezählt von")


class InventoryCountUpdate(BaseModel):
    """Schema zum Aktualisieren einer Inventur"""
    status: str | None = None
    notes: str | None = None
    counted_by: str | None = None


class InventoryCountResponse(InventoryCountBase):
    """Schema für Inventur-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    count_number: str
    status: str
    location_id: UUID | None
    notes: str | None
    counted_by: str | None
    created_at: datetime
    completed_at: datetime | None

    # Expandierte Felder
    location_name: str | None = None

    # Berechnete Felder
    item_count: int | None = None
    difference_count: int | None = None


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
    product_id: UUID | None
    product_name: str
    product_sku: str | None
    category: str
    current_stock: Decimal
    unit: str
    min_stock: Decimal | None
    location_count: int
    batch_count: int
    needs_reorder: bool
    earliest_expiry: date | None
    days_to_expiry: int | None


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
    harvest_date: date | None
    harvest_id: UUID | None
    grow_batch_id: UUID | None
    grow_batch_sow_date: date | None
    seed_inventory_id: UUID | None
    seed_batch_number: str | None
    seed_name: str | None
    supplier: str | None
    orders_delivered: list[dict] | None = None
