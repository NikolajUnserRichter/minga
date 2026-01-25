"""
Pydantic Schemas für Minga-Greens ERP API
Vollständige Validierung für alle Module
"""
# Seed Schemas
from app.schemas.seed import (
    SeedBase, SeedCreate, SeedUpdate, SeedResponse, SeedListResponse,
    SeedBatchBase, SeedBatchCreate, SeedBatchResponse
)

# Production Schemas
from app.schemas.production import (
    GrowBatchBase, GrowBatchCreate, GrowBatchUpdate, GrowBatchResponse,
    HarvestBase, HarvestCreate, HarvestResponse
)

# Unit Schemas
from app.schemas.unit import (
    UnitOfMeasureBase, UnitOfMeasureCreate, UnitOfMeasureUpdate, UnitOfMeasureResponse,
    UnitOfMeasureListResponse,
    UnitConversionBase, UnitConversionCreate, UnitConversionResponse, UnitConversionListResponse,
    ConvertUnitsRequest, ConvertUnitsResponse,
)

# Product Schemas
from app.schemas.product import (
    ProductGroupBase, ProductGroupCreate, ProductGroupUpdate, ProductGroupResponse,
    ProductGroupListResponse,
    GrowPlanBase, GrowPlanCreate, GrowPlanUpdate, GrowPlanResponse, GrowPlanListResponse,
    PriceListBase, PriceListCreate, PriceListUpdate, PriceListResponse, PriceListListResponse,
    PriceListItemBase, PriceListItemCreate, PriceListItemUpdate, PriceListItemResponse,
    PriceListItemListResponse,
    ProductBase, ProductCreate, ProductUpdate, ProductResponse, ProductListResponse,
    ProductDetailResponse,
)

# Customer Schemas
from app.schemas.customer import (
    CustomerAddressBase, CustomerAddressCreate, CustomerAddressUpdate, CustomerAddressResponse,
    CustomerAddressListResponse,
    CustomerBase, CustomerCreate, CustomerUpdate, CustomerResponse, CustomerDetailResponse,
    CustomerListResponse,
    SubscriptionBase, SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse,
    SubscriptionListResponse,
)

# Order Schemas
from app.schemas.order import (
    OrderBase, OrderCreate, OrderResponse,
    OrderItemBase, OrderItemCreate, OrderItemResponse
)

# Invoice Schemas
from app.schemas.invoice import (
    InvoiceLineBase, InvoiceLineCreate, InvoiceLineUpdate, InvoiceLineResponse,
    PaymentBase, PaymentCreate, PaymentResponse, PaymentListResponse,
    InvoiceBase, InvoiceCreate, InvoiceUpdate, InvoiceResponse, InvoiceDetailResponse,
    InvoiceListResponse,
    InvoiceSendRequest, InvoiceCancelRequest, DatevExportRequest, DatevExportResponse,
)

# Inventory Schemas
from app.schemas.inventory import (
    InventoryLocationBase, InventoryLocationCreate, InventoryLocationUpdate,
    InventoryLocationResponse, InventoryLocationListResponse,
    SeedInventoryBase, SeedInventoryCreate, SeedInventoryUpdate,
    SeedInventoryResponse, SeedInventoryListResponse,
    FinishedGoodsInventoryBase, FinishedGoodsInventoryCreate, FinishedGoodsInventoryUpdate,
    FinishedGoodsInventoryResponse, FinishedGoodsInventoryListResponse,
    PackagingInventoryBase, PackagingInventoryCreate, PackagingInventoryUpdate,
    PackagingInventoryResponse, PackagingInventoryListResponse,
    InventoryMovementBase, InventoryMovementCreate, InventoryMovementResponse,
    InventoryMovementListResponse,
    InventoryCountBase, InventoryCountCreate, InventoryCountUpdate,
    InventoryCountResponse, InventoryCountDetailResponse, InventoryCountListResponse,
    InventoryCountItemBase, InventoryCountItemCreate, InventoryCountItemUpdate,
    InventoryCountItemResponse,
    StockOverviewItem, StockOverviewResponse, TraceabilityResponse,
)

# Forecast Schemas
from app.schemas.forecast import (
    ForecastBase, ForecastResponse, ForecastOverride,
    ForecastAccuracyResponse, ProductionSuggestionResponse,
    ForecastGenerateRequest
)

__all__ = [
    # Seed
    "SeedBase", "SeedCreate", "SeedUpdate", "SeedResponse", "SeedListResponse",
    "SeedBatchBase", "SeedBatchCreate", "SeedBatchResponse",
    # Production
    "GrowBatchBase", "GrowBatchCreate", "GrowBatchUpdate", "GrowBatchResponse",
    "HarvestBase", "HarvestCreate", "HarvestResponse",
    # Unit
    "UnitOfMeasureBase", "UnitOfMeasureCreate", "UnitOfMeasureUpdate", "UnitOfMeasureResponse",
    "UnitOfMeasureListResponse",
    "UnitConversionBase", "UnitConversionCreate", "UnitConversionResponse", "UnitConversionListResponse",
    "ConvertUnitsRequest", "ConvertUnitsResponse",
    # Product
    "ProductGroupBase", "ProductGroupCreate", "ProductGroupUpdate", "ProductGroupResponse",
    "ProductGroupListResponse",
    "GrowPlanBase", "GrowPlanCreate", "GrowPlanUpdate", "GrowPlanResponse", "GrowPlanListResponse",
    "PriceListBase", "PriceListCreate", "PriceListUpdate", "PriceListResponse", "PriceListListResponse",
    "PriceListItemBase", "PriceListItemCreate", "PriceListItemUpdate", "PriceListItemResponse",
    "PriceListItemListResponse",
    "ProductBase", "ProductCreate", "ProductUpdate", "ProductResponse", "ProductListResponse",
    "ProductDetailResponse",
    # Customer
    "CustomerAddressBase", "CustomerAddressCreate", "CustomerAddressUpdate", "CustomerAddressResponse",
    "CustomerAddressListResponse",
    "CustomerBase", "CustomerCreate", "CustomerUpdate", "CustomerResponse", "CustomerDetailResponse",
    "CustomerListResponse",
    "SubscriptionBase", "SubscriptionCreate", "SubscriptionUpdate", "SubscriptionResponse",
    "SubscriptionListResponse",
    # Order
    "OrderBase", "OrderCreate", "OrderResponse",
    "OrderItemBase", "OrderItemCreate", "OrderItemResponse",
    # Invoice
    "InvoiceLineBase", "InvoiceLineCreate", "InvoiceLineUpdate", "InvoiceLineResponse",
    "PaymentBase", "PaymentCreate", "PaymentResponse", "PaymentListResponse",
    "InvoiceBase", "InvoiceCreate", "InvoiceUpdate", "InvoiceResponse", "InvoiceDetailResponse",
    "InvoiceListResponse",
    "InvoiceSendRequest", "InvoiceCancelRequest", "DatevExportRequest", "DatevExportResponse",
    # Inventory
    "InventoryLocationBase", "InventoryLocationCreate", "InventoryLocationUpdate",
    "InventoryLocationResponse", "InventoryLocationListResponse",
    "SeedInventoryBase", "SeedInventoryCreate", "SeedInventoryUpdate",
    "SeedInventoryResponse", "SeedInventoryListResponse",
    "FinishedGoodsInventoryBase", "FinishedGoodsInventoryCreate", "FinishedGoodsInventoryUpdate",
    "FinishedGoodsInventoryResponse", "FinishedGoodsInventoryListResponse",
    "PackagingInventoryBase", "PackagingInventoryCreate", "PackagingInventoryUpdate",
    "PackagingInventoryResponse", "PackagingInventoryListResponse",
    "InventoryMovementBase", "InventoryMovementCreate", "InventoryMovementResponse",
    "InventoryMovementListResponse",
    "InventoryCountBase", "InventoryCountCreate", "InventoryCountUpdate",
    "InventoryCountResponse", "InventoryCountDetailResponse", "InventoryCountListResponse",
    "InventoryCountItemBase", "InventoryCountItemCreate", "InventoryCountItemUpdate",
    "InventoryCountItemResponse",
    "StockOverviewItem", "StockOverviewResponse", "TraceabilityResponse",
    # Forecast
    "ForecastBase", "ForecastResponse", "ForecastOverride",
    "ForecastAccuracyResponse", "ProductionSuggestionResponse",
    "ForecastGenerateRequest",
]
