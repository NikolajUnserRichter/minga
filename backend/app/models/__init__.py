"""
SQLAlchemy Models für Minga-Greens ERP
Vollständiges ERP-Datenmodell für Microgreens-Produktion
"""
# Basis-Models
from app.models.seed import Seed, SeedBatch
from app.models.production import GrowBatch, Harvest, GrowBatchStatus

# Units und Products (Core)
from app.models.unit import (
    UnitOfMeasure,
    UnitConversion,
    UnitCategory,
    STANDARD_UNITS,
)
from app.models.product import (
    Product,
    ProductGroup,
    GrowPlan,
    PriceList,
    PriceListItem,
    ProductCategory,
    STANDARD_GROW_PLANS,
)

# Kunden und Bestellungen (Sales)
from app.models.customer import (
    Customer,
    CustomerAddress,
    Subscription,
    CustomerType,
    PaymentTerms,
    AddressType,
    SubscriptionInterval,
)
from app.models.order import Order, OrderLine

# Rechnungen (Accounting)
from app.models.invoice import (
    Invoice,
    InvoiceLine,
    Payment,
    InvoiceStatus,
    InvoiceType,
    TaxRate,
    PaymentMethod,
    generate_invoice_number,
    STANDARD_ACCOUNTS,
)

# Lager (Inventory)
from app.models.inventory import (
    InventoryLocation,
    SeedInventory,
    FinishedGoodsInventory,
    PackagingInventory,
    InventoryMovement,
    InventoryCount,
    InventoryCountItem,
    LocationType,
    MovementType,
    InventoryItemType,
    STANDARD_LOCATIONS,
)

# Forecasting
from app.models.forecast import Forecast, ForecastAccuracy, ProductionSuggestion

# Kapazitäten
from app.models.capacity import Capacity

# Belegkette (Auftragsbestätigung, Lieferschein, Verpackungsliste)
from app.models.documents import (
    OrderConfirmation,
    DeliveryNote,
    PackingList,
    PackingListItem,
)
from app.models.enums import ConfirmationStatus, DeliveryNoteStatus

# Anhänge (Zertifikate, Datenblätter)
from app.models.attachment import (
    Attachment,
    ATTACHMENT_ENTITY_TYPES,
    CERTIFICATE_TYPES,
)

# App-Settings (Runtime-Konfiguration via Admin-Center)
from app.models.app_setting import AppSetting

# Production-Timeline-Events
from app.models.growth_event import (
    GrowthBatchEvent,
    GrowthEventType,
    GROWTH_EVENT_LABELS,
)

__all__ = [
    # Seed & Production
    "Seed",
    "SeedBatch",
    "GrowBatch",
    "GrowBatchStatus",
    "Harvest",
    # Units
    "UnitOfMeasure",
    "UnitConversion",
    "UnitCategory",
    "STANDARD_UNITS",
    # Products
    "Product",
    "ProductGroup",
    "GrowPlan",
    "PriceList",
    "PriceListItem",
    "ProductCategory",
    "STANDARD_GROW_PLANS",
    # Customer & Sales
    "Customer",
    "CustomerAddress",
    "Subscription",
    "CustomerType",
    "PaymentTerms",
    "AddressType",
    "SubscriptionInterval",
    "Order",
    "OrderLine",
    # Invoice & Accounting
    "Invoice",
    "InvoiceLine",
    "Payment",
    "InvoiceStatus",
    "InvoiceType",
    "TaxRate",
    "PaymentMethod",
    "generate_invoice_number",
    "STANDARD_ACCOUNTS",
    # Inventory
    "InventoryLocation",
    "SeedInventory",
    "FinishedGoodsInventory",
    "PackagingInventory",
    "InventoryMovement",
    "InventoryCount",
    "InventoryCountItem",
    "LocationType",
    "MovementType",
    "InventoryItemType",
    "STANDARD_LOCATIONS",
    # Forecasting
    "Forecast",
    "ForecastAccuracy",
    "ProductionSuggestion",
    # Capacity
    "Capacity",
    # Belegkette
    "OrderConfirmation",
    "DeliveryNote",
    "PackingList",
    "PackingListItem",
    "ConfirmationStatus",
    "DeliveryNoteStatus",
    # Attachments
    "Attachment",
    "ATTACHMENT_ENTITY_TYPES",
    "CERTIFICATE_TYPES",
    # App-Settings
    "AppSetting",
    # Production-Timeline
    "GrowthBatchEvent",
    "GrowthEventType",
    "GROWTH_EVENT_LABELS",
]
