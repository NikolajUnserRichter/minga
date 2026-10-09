"""
SQLAlchemy Models für Minga-Greens ERP
Vollständiges ERP-Datenmodell für Microgreens-Produktion
"""
# Basis-Models
from app.models.seed import Seed, SeedBatch, SeedMixComponent, SeedBatchComponent
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

# Einkauf / Wareneingang (Procurement)
from app.models.procurement import (
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    TradeGoodsInventory,
)

# Rechnungen (Accounting)
from app.models.invoice import (
    Invoice,
    InvoiceLine,
    InvoiceLineSource,
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
    DocumentDispatch,
)
from app.models.enums import (
    ConfirmationStatus, DeliveryNoteStatus, DispatchDocType, DispatchStatus,
)

# Anhänge (Zertifikate, Datenblätter)
from app.models.attachment import (
    Attachment,
    ATTACHMENT_ENTITY_TYPES,
    CERTIFICATE_TYPES,
)

# App-Settings (Runtime-Konfiguration via Admin-Center)
from app.models.app_setting import AppSetting

# SEPA-Lastschriftmandate (B10)
from app.models.sepa_mandate import SepaMandat, Zahlungsart, Mandatsart, LastschriftStatus

# Druck-Warteschlange (Etikettendrucker im Hofnetz)
from app.models.print_job import PrintJob, PrintJobStatus

# Import-Läufe (Historien-Import mit Rollback)
from app.models.import_run import ImportRun
# Monatsläufe der Monatsrechnungen (B5)
from app.models.billing_run import BillingRun

# Leergutkonto (Paket 3, Q6): Pfandkisten je Kunde, monatlich abgerechnet
from app.models.leergut import LeergutBewegung, LeergutArt

# Customer-spezifische Preise
from app.models.customer_price import CustomerPrice

# Document-Templates (Custom-PDF-Layouts pro Belegart)
from app.models.document_template import (
    DocumentTemplate,
    DocumentType,
    DEFAULT_SECTIONS,
    DEFAULT_COLUMNS,
    DEFAULT_TEXTS,
)

# Production-Timeline-Events
from app.models.staff import StaffShift, StaffTask
from app.models.growth_event import (
    GrowthBatchEvent,
    GrowthEventType,
    GROWTH_EVENT_LABELS,
)

# Benutzerverwaltung: dauerhafte Audit-Spur (Paket 4, B8)
from app.models.benutzer_audit import BenutzerAudit

__all__ = [
    # Seed & Production
    "Seed",
    "SeedBatch",
    "SeedMixComponent",
    "SeedBatchComponent",
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
    # Procurement (Einkauf)
    "PurchaseOrder",
    "PurchaseOrderLine",
    "PurchaseOrderStatus",
    "TradeGoodsInventory",
    # Invoice & Accounting
    "Invoice",
    "InvoiceLine",
    "InvoiceLineSource",
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
    "DocumentDispatch",
    "ConfirmationStatus",
    "DeliveryNoteStatus",
    "DispatchDocType",
    "DispatchStatus",
    # Attachments
    "Attachment",
    "ATTACHMENT_ENTITY_TYPES",
    "CERTIFICATE_TYPES",
    # App-Settings
    "AppSetting",
    # Druck-Warteschlange
    "PrintJob",
    "PrintJobStatus",
    # Import-Läufe
    "ImportRun",
    # Monatsläufe
    "BillingRun",
    # Leergutkonto
    "LeergutBewegung",
    "LeergutArt",
    # Customer-Pricing
    "CustomerPrice",
    # Production-Timeline
    "GrowthBatchEvent",
    "GrowthEventType",
    "GROWTH_EVENT_LABELS",
    # Dienstplan
    "StaffShift",
    "StaffTask",
    # Benutzer-Audit
    "BenutzerAudit",
]
