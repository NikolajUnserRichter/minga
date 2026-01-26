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
]
