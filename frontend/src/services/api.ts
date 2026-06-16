import axios from 'axios'
import type {
  Seed, GrowBatch, Harvest, Customer, Order, Forecast,
  ProductionSuggestion, ListResponse, DashboardSummary,
  Product, ProductGroup, GrowPlan, PriceList, PriceListItem,
  Invoice, InvoiceLine, Payment, InvoiceStatus, InvoiceType,
  InventoryLocation, SeedInventory, FinishedGoodsInventory,
  PackagingInventory, InventoryMovement, StockOverview,
  ArticleType, LocationType, TraceabilityChain, Capacity,
  RevenueStats, YieldStats, Subscription, AccuracySummary, AccuracyDetail,
  Contact, Supplier, ProductVariant, UnitOfMeasure, CustomerAddress, BundleComponent
} from '../types'

import keycloak from './auth';

const AUTH_DISABLED = import.meta.env.VITE_AUTH_DISABLED === 'true';

// API Configuration
const API_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')

const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add Auth Interceptor
api.interceptors.request.use(async (config) => {
  if (AUTH_DISABLED) return config;
  if (keycloak.token) {
    try {
      await keycloak.updateToken(30);
      config.headers.Authorization = `Bearer ${keycloak.token}`;
    } catch (_error) {
      // Token refresh failed — silently continue without auth
    }
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

// Seeds API
export const seedsApi = {
  list: (params?: { aktiv?: boolean; search?: string }) =>
    api.get<ListResponse<Seed>>('/seeds', { params }).then(r => r.data),

  get: (id: string) =>
    api.get<Seed>(`/seeds/${id}`).then(r => r.data),

  create: (data: Partial<Seed>) =>
    api.post<Seed>('/seeds', data).then(r => r.data),

  update: (id: string, data: Partial<Seed>) =>
    api.patch<Seed>(`/seeds/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/seeds/${id}`),

  // Suppliers per Seed (M:N)
  listSuppliers: (seedId: string) =>
    api.get<Array<{
      supplier_id: string
      is_default: boolean
      notizen: string | null
      supplier_name: string | null
      supplier_email: string | null
    }>>(`/seeds/${seedId}/suppliers`).then(r => r.data),

  addSupplier: (seedId: string, data: { supplier_id: string; is_default?: boolean; notizen?: string }) =>
    api.post(`/seeds/${seedId}/suppliers`, data).then(r => r.data),

  removeSupplier: (seedId: string, supplierId: string) =>
    api.delete(`/seeds/${seedId}/suppliers/${supplierId}`),

  setDefaultSupplier: (seedId: string, supplierId: string) =>
    api.post(`/seeds/${seedId}/suppliers/${supplierId}/set-default`).then(r => r.data),

  // Batches per Seed (Saatgutchargen)
  listBatches: (seedId: string) =>
    api.get<Array<{
      id: string
      seed_id: string
      charge_nummer: string
      menge_gramm: number
      verbleibend_gramm: number
      mhd: string | null
      lieferdatum: string | null
      in_production_at: string | null
      lieferschein_nr: string | null
      bio_zertifiziert: boolean
      kontrollstelle: string | null
      created_at: string
    }>>(`/seeds/${seedId}/batches`).then(r => r.data),
}

// Production API
export const productionApi = {
  listGrowBatches: (params?: { status?: string; erntereif?: boolean }) =>
    api.get<GrowBatch[]>('/production/grow-batches', { params }).then(r => r.data),

  getGrowBatch: (id: string) =>
    api.get<GrowBatch>(`/production/grow-batches/${id}`).then(r => r.data),

  createGrowBatch: (data: {
    seed_batch_id: string
    tray_anzahl: number
    aussaat_datum: string
    regal_position?: string
    notizen?: string
  }) =>
    api.post<GrowBatch>('/production/grow-batches', data).then(r => r.data),

  updateGrowBatchStatus: (id: string, status: string) =>
    api.post<GrowBatch>(`/production/grow-batches/${id}/status/${status}`).then(r => r.data),

  downloadLabel: (id: string) =>
    api.get(`/production/grow-batches/${id}/label`, { responseType: 'blob' }),

  // Production-Timeline-Events
  listEvents: (batchId: string) =>
    api.get<GrowthEvent[]>(`/production/grow-batches/${batchId}/events`).then(r => r.data),

  createEvent: (batchId: string, data: {
    event_type: GrowthEventTypeKey;
    occurred_at?: string;
    employee_name?: string;
    notes?: string;
    extra?: Record<string, any>;
  }) =>
    api.post<GrowthEvent>(`/production/grow-batches/${batchId}/events`, data).then(r => r.data),

  listEventTypes: () =>
    api.get<Array<{ value: GrowthEventTypeKey; label: string }>>('/production/event-types').then(r => r.data),

  listHarvests: (params?: { von_datum?: string; bis_datum?: string }) =>
    api.get<ListResponse<Harvest>>('/production/harvests', { params }).then(r => r.data),

  createHarvest: (data: {
    grow_batch_id: string
    ernte_datum: string
    menge_gramm: number
    verlust_gramm?: number
    qualitaet_note?: number
  }) =>
    api.post<Harvest>('/production/harvests', data).then(r => r.data),

  getDashboard: () =>
    api.get<DashboardSummary>('/production/dashboard/summary').then(r => r.data),

  getPackagingPlan: (targetDate: string) =>
    api.get<{ target_date: string; items: any[] }>(`/production/packaging-plan`, { params: { target_date: targetDate } }).then(r => r.data),
}

// Sales API
export const salesApi = {
  listCustomers: (params?: { typ?: string; aktiv?: boolean; search?: string; page_size?: number }) =>
    api.get<ListResponse<Customer>>('/sales/customers', { params: { page_size: 500, ...params } }).then(r => r.data),

  getCustomer: (id: string) =>
    api.get<Customer>(`/sales/customers/${id}`).then(r => r.data),

  createCustomer: (data: Partial<Customer>) =>
    api.post<Customer>('/sales/customers', data).then(r => r.data),

  updateCustomer: (id: string, data: Partial<Customer>) =>
    api.patch<Customer>(`/sales/customers/${id}`, data).then(r => r.data),

  deleteCustomer: (id: string) =>
    api.delete(`/sales/customers/${id}`),

  listOrders: (params?: { status?: string; kunde_id?: string }) =>
    api.get<ListResponse<Order>>('/sales/orders', { params }).then(r => r.data),

  getOrder: (id: string) =>
    api.get<Order>(`/sales/orders/${id}`).then(r => r.data),

  createOrder: (data: {
    customer_id: string
    requested_delivery_date: string
    lines: Array<{
      product_id?: string
      product_variant_id?: string
      product_name: string
      quantity: number
      unit: string
      unit_price: number
      tax_rate?: 'STANDARD' | 'REDUZIERT' | 'STEUERFREI'
      variable_bundle_selections?: Array<{ product_id: string; quantity: number }>
    }>
    notes?: string
    customer_reference?: string
  }) =>
    api.post<Order>('/sales/orders', data).then(r => r.data),

  updateOrderStatus: (id: string, status: string) =>
    api.post<Order>(`/sales/orders/${id}/status/${status}`).then(r => r.data),

  runDailySubscriptions: () =>
    api.post('/sales/subscriptions/process-today').then(r => r.data),

  // Addresses (Rechnungs-/Lieferadressen)
  listAddresses: (customerId: string) =>
    api.get<CustomerAddress[]>(`/sales/customers/${customerId}/addresses`).then(r => r.data),

  createAddress: (customerId: string, data: Partial<CustomerAddress>) =>
    api.post<CustomerAddress>(`/sales/customers/${customerId}/addresses`, data).then(r => r.data),

  updateAddress: (customerId: string, addressId: string, data: Partial<CustomerAddress>) =>
    api.patch<CustomerAddress>(`/sales/customers/${customerId}/addresses/${addressId}`, data).then(r => r.data),

  deleteAddress: (customerId: string, addressId: string) =>
    api.delete(`/sales/customers/${customerId}/addresses/${addressId}`),

  // Contacts (Ansprechpartner) — multiple per customer
  listContacts: (customerId: string) =>
    api.get<Contact[]>(`/sales/customers/${customerId}/contacts`).then(r => r.data),

  createContact: (customerId: string, data: Partial<Contact>) =>
    api.post<Contact>(`/sales/customers/${customerId}/contacts`, data).then(r => r.data),

  updateContact: (customerId: string, contactId: string, data: Partial<Contact>) =>
    api.patch<Contact>(`/sales/customers/${customerId}/contacts/${contactId}`, data).then(r => r.data),

  deleteContact: (customerId: string, contactId: string) =>
    api.delete(`/sales/customers/${customerId}/contacts/${contactId}`),
}

// Suppliers API
export const suppliersApi = {
  list: (params?: { is_active?: boolean; search?: string }) =>
    api.get<{ items: Supplier[]; total: number }>('/suppliers', { params }).then(r => r.data),

  get: (id: string) =>
    api.get<Supplier>(`/suppliers/${id}`).then(r => r.data),

  create: (data: Partial<Supplier>) =>
    api.post<Supplier>('/suppliers', data).then(r => r.data),

  update: (id: string, data: Partial<Supplier>) =>
    api.patch<Supplier>(`/suppliers/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/suppliers/${id}`),
}

// Forecasting API
export const forecastingApi = {
  listForecasts: (params?: { seed_id?: string; von_datum?: string; bis_datum?: string }) =>
    api.get<ListResponse<Forecast>>('/forecasting/forecasts', { params }).then(r => r.data),

  generateForecasts: (data: {
    seed_ids?: string[]
    horizont_tage?: number
    modell_typ?: string
  }) =>
    api.post<Forecast[]>('/forecasting/forecasts/generate', data).then(r => r.data),

  overrideForecast: (id: string, data: { override_menge: number; override_grund: string }) =>
    api.patch<Forecast>(`/forecasting/forecasts/${id}/override`, data).then(r => r.data),

  getAccuracySummary: (params?: { von_datum?: string; bis_datum?: string }) =>
    api.get('/forecasting/forecasts/accuracy/summary', { params }).then(r => r.data),

  listProductionSuggestions: (params?: { status?: string }) =>
    api.get<{ items: ProductionSuggestion[]; total: number; warnungen_gesamt: number }>(
      '/forecasting/production-suggestions', { params }
    ).then(r => r.data),

  generateProductionSuggestions: (horizont_tage?: number) =>
    api.post<ProductionSuggestion[]>('/forecasting/production-suggestions/generate', null, {
      params: { horizont_tage }
    }).then(r => r.data),

  approveSuggestion: (id: string, angepasste_trays?: number) =>
    api.post<ProductionSuggestion>(`/forecasting/production-suggestions/${id}/approve`, {
      angepasste_trays
    }).then(r => r.data),

  rejectSuggestion: (id: string) =>
    api.post(`/forecasting/production-suggestions/${id}/reject`),

  getWeeklySummary: (kalenderwoche?: number, jahr?: number) =>
    api.get('/forecasting/weekly-summary', {
      params: { kalenderwoche, jahr }
    }).then(r => r.data),
}

// ============== ERP APIs ==============

// Products API
export const productsApi = {
  list: (params?: { category?: string; is_active?: boolean; search?: string }) =>
    api.get<Product[]>('/products', { params }).then(r => r.data),

  get: (id: string) =>
    api.get<Product>(`/products/${id}`).then(r => r.data),

  create: (data: Partial<Product>) =>
    api.post<Product>('/products', data).then(r => r.data),

  update: (id: string, data: Partial<Product>) =>
    api.patch<Product>(`/products/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/products/${id}`),

  getPrice: (productId: string, params?: { customer_id?: string; quantity?: number }) =>
    api.get<{ product_id: string; price: number; quantity: number }>(`/products/${productId}/price`, { params }).then(r => r.data),

  getStatistics: () =>
    api.get('/products/statistics').then(r => r.data),

  // Variants (Verpackungsgrößen)
  listVariants: (productId: string) =>
    api.get<ProductVariant[]>(`/products/${productId}/variants`).then(r => r.data),

  createVariant: (productId: string, data: Partial<ProductVariant>) =>
    api.post<ProductVariant>(`/products/${productId}/variants`, data).then(r => r.data),

  updateVariant: (productId: string, variantId: string, data: Partial<ProductVariant>) =>
    api.patch<ProductVariant>(`/products/${productId}/variants/${variantId}`, data).then(r => r.data),

  deleteVariant: (productId: string, variantId: string) =>
    api.delete(`/products/${productId}/variants/${variantId}`),

  // Bundle Components (Mischkisten: feste Komponenten)
  listBundleComponents: (productId: string) =>
    api.get<BundleComponent[]>(`/products/${productId}/bundle-components`).then(r => r.data),

  addBundleComponent: (productId: string, data: { child_product_id: string; quantity: number; sort_order?: number }) =>
    api.post<BundleComponent>(`/products/${productId}/bundle-components`, data).then(r => r.data),

  removeBundleComponent: (productId: string, componentId: string) =>
    api.delete(`/products/${productId}/bundle-components/${componentId}`),
}

// Units of Measure API
export const unitsApi = {
  list: () =>
    api.get<UnitOfMeasure[]>('/units').then(r => r.data).catch(() => [] as UnitOfMeasure[]),
}

// Product Groups API
export const productGroupsApi = {
  list: (params?: { parent_id?: string }) =>
    api.get<ProductGroup[]>('/product-groups', { params }).then(r => r.data),

  get: (id: string) =>
    api.get<ProductGroup>(`/product-groups/${id}`).then(r => r.data),

  create: (data: Partial<ProductGroup>) =>
    api.post<ProductGroup>('/product-groups', data).then(r => r.data),

  update: (id: string, data: Partial<ProductGroup>) =>
    api.patch<ProductGroup>(`/product-groups/${id}`, data).then(r => r.data),
}

// Grow Plans API
export const growPlansApi = {
  list: (params?: { is_active?: boolean }) =>
    api.get<GrowPlan[]>('/grow-plans', { params }).then(r => r.data),

  get: (id: string) =>
    api.get<GrowPlan>(`/grow-plans/${id}`).then(r => r.data),

  create: (data: Partial<GrowPlan>) =>
    api.post<GrowPlan>('/grow-plans', data).then(r => r.data),

  update: (id: string, data: Partial<GrowPlan>) =>
    api.patch<GrowPlan>(`/grow-plans/${id}`, data).then(r => r.data),

  calculateSowDate: (planId: string, targetHarvestDate: string) =>
    api.get(`/grow-plans/${planId}/calculate-sow-date`, {
      params: { target_harvest_date: targetHarvestDate }
    }).then(r => r.data),

  calculateHarvestWindow: (planId: string, sowDate: string) =>
    api.get(`/grow-plans/${planId}/calculate-harvest-window`, {
      params: { sow_date: sowDate }
    }).then(r => r.data),
}

// Price Lists API
export const priceListsApi = {
  list: (params?: { is_active?: boolean }) =>
    api.get<PriceList[]>('/price-lists', { params }).then(r => r.data),

  get: (id: string) =>
    api.get<PriceList>(`/price-lists/${id}`).then(r => r.data),

  getDefault: () =>
    api.get<PriceList>('/price-lists/default').then(r => r.data),

  create: (data: Partial<PriceList>) =>
    api.post<PriceList>('/price-lists', data).then(r => r.data),

  update: (id: string, data: Partial<PriceList>) =>
    api.patch<PriceList>(`/price-lists/${id}`, data).then(r => r.data),

  copy: (id: string, data: { new_code: string; new_name: string; price_adjustment_percent?: number }) =>
    api.post<PriceList>(`/price-lists/${id}/copy`, null, { params: data }).then(r => r.data),

  addItem: (listId: string, data: Partial<PriceListItem>) =>
    api.post<PriceListItem>(`/price-lists/${listId}/items`, data).then(r => r.data),

  updateItem: (listId: string, itemId: string, data: Partial<PriceListItem>) =>
    api.patch<PriceListItem>(`/price-lists/${listId}/items/${itemId}`, data).then(r => r.data),

  deleteItem: (listId: string, itemId: string) =>
    api.delete(`/price-lists/${listId}/items/${itemId}`),
}

// Invoices API
export const invoicesApi = {
  list: (params?: { status?: InvoiceStatus; customer_id?: string; invoice_type?: InvoiceType; from_date?: string; to_date?: string }) =>
    api.get<Invoice[]>('/invoices', { params }).then(r => r.data),

  get: (id: string) =>
    api.get<Invoice>(`/invoices/${id}`).then(r => r.data),

  create: (data: {
    customer_id: string
    invoice_date?: string
    delivery_date?: string
    order_id?: string
    invoice_type?: InvoiceType
    discount_percent?: number
    header_text?: string
    footer_text?: string
    internal_notes?: string
    due_date?: string
    buchungskonto?: string
  }) =>
    api.post<Invoice>('/invoices', data).then(r => r.data),

  createFromOrder: (orderId: string) =>
    api.post<Invoice>(`/invoices/from-order/${orderId}`).then(r => r.data),

  update: (id: string, data: Partial<Invoice>) =>
    api.patch<Invoice>(`/invoices/${id}`, data).then(r => r.data),

  finalize: (id: string) =>
    api.post<Invoice>(`/invoices/${id}/finalize`).then(r => r.data),

  cancel: (id: string, data: { reason: string; create_credit_note?: boolean }) =>
    api.post(`/invoices/${id}/cancel`, data).then(r => r.data),

  getOverdue: () =>
    api.get<Invoice[]>('/invoices/overdue').then(r => r.data),

  getRevenueSummary: (fromDate: string, toDate: string) =>
    api.get('/invoices/revenue-summary', { params: { from_date: fromDate, to_date: toDate } }).then(r => r.data),

  // Lines
  addLine: (invoiceId: string, data: Partial<InvoiceLine>) =>
    api.post<InvoiceLine>(`/invoices/${invoiceId}/lines`, data).then(r => r.data),

  updateLine: (invoiceId: string, lineId: string, data: Partial<InvoiceLine>) =>
    api.patch<InvoiceLine>(`/invoices/${invoiceId}/lines/${lineId}`, data).then(r => r.data),

  deleteLine: (invoiceId: string, lineId: string) =>
    api.delete(`/invoices/${invoiceId}/lines/${lineId}`),

  // Payments
  listPayments: (invoiceId: string) =>
    api.get<Payment[]>(`/invoices/${invoiceId}/payments`).then(r => r.data),

  recordPayment: (invoiceId: string, data: {
    amount: number
    payment_date?: string
    payment_method?: string
    reference?: string
    notes?: string
  }) =>
    api.post<Payment>(`/invoices/${invoiceId}/payments`, data).then(r => r.data),

  // DATEV
  exportDatev: (data: { from_date: string; to_date: string; include_payments?: boolean }) =>
    api.post('/invoices/datev-export', data).then(r => r.data),

  downloadDatev: (data: { from_date: string; to_date: string; include_payments?: boolean }) =>
    api.post('/invoices/datev-export/download', data, { responseType: 'blob' }),

  downloadPdf: (id: string) =>
    api.get(`/invoices/${id}/pdf`, { responseType: 'blob' }),

  sendInvoiceEmail: (invoiceId: string, toEmail: string) =>
    api.post(`/invoices/${invoiceId}/send`, null, { params: { to_email: toEmail } }).then(r => r.data),

  // Zahlungserinnerung / Mahnung (level 1-3) als PDF
  generatePaymentReminder: (invoiceId: string, level: number = 1, dunning_fee: number = 0) =>
    api.post(`/invoices/${invoiceId}/payment-reminder`, null, {
      params: { level, dunning_fee },
      responseType: 'blob',
    }),
}

// ... existing code ...

// Production API extensions
// Note: I will append this to the existing productionApi object def, 
// but since I can't easily insert into the middle of the file with search/replace reliably if similar lines exist,
// I'll check where productionApi ends. It ends around line 73.
// I will edit the productionApi block directly.

// Sales API extensions
// salesApi ends around line 107.


// Inventory API
export const inventoryApi = {
  // Locations
  listLocations: (params?: { location_type?: LocationType; is_active?: boolean }) =>
    api.get<InventoryLocation[]>('/inventory/locations', { params }).then(r => r.data),

  getLocation: (id: string) =>
    api.get<InventoryLocation>(`/inventory/locations/${id}`).then(r => r.data),

  createLocation: (data: Partial<InventoryLocation>) =>
    api.post<InventoryLocation>('/inventory/locations', data).then(r => r.data),

  updateLocation: (id: string, data: Partial<InventoryLocation>) =>
    api.patch<InventoryLocation>(`/inventory/locations/${id}`, data).then(r => r.data),

  // Seed Inventory
  listSeedInventory: (params?: { seed_id?: string; location_id?: string; low_stock_only?: boolean }) =>
    api.get<SeedInventory[]>('/inventory/seeds', { params }).then(r => r.data),

  receiveSeedBatch: (data: {
    seed_id: string
    batch_number: string
    quantity: number
    unit: string
    location_id: string
    supplier?: string
    mhd?: string
    lieferdatum?: string
    in_production_at?: string
    lieferschein_nr?: string
    kontrollstelle?: string
    purchase_price?: number
    is_organic?: boolean
    organic_certification?: string
  }) =>
    api.post<SeedInventory>('/inventory/seeds/receive', null, { params: data }).then(r => r.data),

  // Wareneingang Verpackung / Substrat / Pfandkiste: erhöht Bestand wenn SKU bekannt, sonst neu anlegen
  receivePackaging: (data: {
    sku: string
    name: string
    quantity: number
    unit?: string
    article_type?: 'VERPACKUNG' | 'SUBSTRAT' | 'PFANDKISTE'
    location_id?: string
    supplier_name?: string
    supplier_sku?: string
    purchase_price?: number
    min_quantity?: number
    reorder_quantity?: number
  }) =>
    api.post<PackagingInventory>('/inventory/packaging/receive', null, { params: data }).then(r => r.data),

  consumeSeed: (inventoryId: string, data: { quantity: number; grow_batch_id?: string; notes?: string }) =>
    api.post(`/inventory/seeds/${inventoryId}/consume`, null, { params: data }).then(r => r.data),

  // Finished Goods
  listFinishedGoods: (params?: { product_id?: string; location_id?: string; available_only?: boolean }) =>
    api.get<FinishedGoodsInventory[]>('/inventory/finished-goods', { params }).then(r => r.data),

  receiveHarvest: (data: {
    harvest_id: string
    product_id: string
    location_id: string
    quantity: number
    unit: string
    shelf_life_days?: number
  }) =>
    api.post<FinishedGoodsInventory>('/inventory/finished-goods/receive-harvest', null, { params: data }).then(r => r.data),

  shipGoods: (data: {
    product_id: string
    quantity: number
    order_id?: string
    customer_id?: string
    notes?: string
  }) =>
    api.post('/inventory/finished-goods/ship', null, { params: data }).then(r => r.data),

  recordLoss: (inventoryId: string, data: { quantity: number; reason: string }) =>
    api.post(`/inventory/finished-goods/${inventoryId}/loss`, null, { params: data }).then(r => r.data),

  downloadLabel: (id: string) =>
    api.get(`/inventory/finished-goods/${id}/label`, { responseType: 'blob' }),

  getTraceability: (id: string) =>
    api.get<TraceabilityChain>(`/inventory/traceability/${id}`).then(r => r.data),

  // Packaging
  listPackaging: (params?: { location_id?: string; low_stock_only?: boolean }) =>
    api.get<PackagingInventory[]>('/inventory/packaging', { params }).then(r => r.data),

  createPackaging: (data: Partial<PackagingInventory>) =>
    api.post<PackagingInventory>('/inventory/packaging', data).then(r => r.data),

  updatePackaging: (id: string, data: Partial<PackagingInventory>) =>
    api.patch<PackagingInventory>(`/inventory/packaging/${id}`, data).then(r => r.data),

  // Movements
  listMovements: (params?: { article_type?: ArticleType; movement_type?: string; from_date?: string; to_date?: string }) =>
    api.get<InventoryMovement[]>('/inventory/movements', { params }).then(r => r.data),

  // Overview & Alerts
  getStockOverview: (articleType?: ArticleType) =>
    api.get<StockOverview[]>('/inventory/stock-overview', { params: { article_type: articleType } }).then(r => r.data),

  getLowStockAlerts: () =>
    api.get('/inventory/low-stock-alerts').then(r => r.data),

  correctInventory: (data: {
    inventory_id: string;
    inventory_type: string;
    actual_quantity: number;
    reason: string;
  }) =>
    api.post('/inventory/correction', null, { params: data }).then(r => r.data),

}

// Analytics API
export const analyticsApi = {
  getRevenue: (months: number = 12) =>
    api.get<RevenueStats[]>('/analytics/revenue', { params: { months } }).then(r => r.data),

  getYield: () =>
    api.get<YieldStats[]>('/analytics/yield').then(r => r.data),
}

// Subscriptions API
export const subscriptionsApi = {
  list: (params?: { kunde_id?: string; aktiv?: boolean }) =>
    api.get<{ items: Subscription[]; total: number }>('/sales/subscriptions', { params }).then(r => r.data),

  get: (id: string) =>
    api.get<Subscription>(`/sales/subscriptions/${id}`).then(r => r.data),

  create: (data: {
    kunde_id: string
    product_id?: string
    seed_id?: string
    menge: number
    einheit: string
    intervall: 'TAEGLICH' | 'WOECHENTLICH' | 'ZWEIWOECHENTLICH' | 'MONATLICH'
    liefertage?: number[]
    gueltig_von: string
    gueltig_bis?: string
  }) =>
    api.post<Subscription>('/sales/subscriptions', data).then(r => r.data),

  update: (id: string, data: Partial<{
    menge: number
    einheit: string
    intervall: 'TAEGLICH' | 'WOECHENTLICH' | 'ZWEIWOECHENTLICH' | 'MONATLICH'
    liefertage: number[]
    gueltig_bis: string
    aktiv: boolean
  }>) =>
    api.patch<Subscription>(`/sales/subscriptions/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/sales/subscriptions/${id}`),

  processToday: () =>
    api.post('/sales/subscriptions/process-today').then(r => r.data),
}

// Accuracy Reports API
export const accuracyApi = {
  getSummary: (params?: { von_datum?: string; bis_datum?: string }) =>
    api.get<AccuracySummary>('/forecasting/forecasts/accuracy/summary', { params }).then(r => r.data),

  getDetails: (params?: { von_datum?: string; bis_datum?: string; seed_id?: string }) =>
    api.get<{ items: AccuracyDetail[]; total: number }>('/forecasting/accuracy/details', { params }).then(r => r.data),

  getByForecast: (forecastId: string) =>
    api.get<AccuracyDetail>(`/forecasting/accuracy/${forecastId}`).then(r => r.data),
}

// Capacity API
export const capacityApi = {
  list: () =>
    api.get<Capacity[]>('/capacity').then(r => r.data),

  create: (data: Partial<Capacity>) =>
    api.post<Capacity>('/capacity', data).then(r => r.data),

  get: (id: string) =>
    api.get<Capacity>(`/capacity/${id}`).then(r => r.data),

  update: (id: string, data: Partial<Capacity>) =>
    api.patch<Capacity>(`/capacity/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/capacity/${id}`),

  getSummary: () =>
    api.get('/capacity/summary/overview').then(r => r.data),
}

// ============== Users API (Mock Data) ==============
import type { User, UserRole } from '../types'

// Mock users with localStorage persistence
const MOCK_USERS_KEY = 'minga-mock-users'

const defaultMockUsers: User[] = [
  { id: '1', name: 'Max Mustermann', email: 'max@minga-greens.de', role: 'ADMIN', is_active: true, last_login: '2026-04-08T08:14:00Z', created_at: '2024-11-01T10:00:00Z', phone: '+49 89 123 4560' },
  { id: '2', name: 'Anna Schmidt', email: 'anna@minga-greens.de', role: 'SALES', is_active: true, last_login: '2026-04-08T09:32:00Z', created_at: '2025-01-15T09:00:00Z', phone: '+49 89 123 4561' },
  { id: '3', name: 'Peter Müller', email: 'peter@minga-greens.de', role: 'PRODUCTION_PLANNER', is_active: true, last_login: '2026-04-07T16:50:00Z', created_at: '2025-02-10T08:30:00Z', phone: '+49 89 123 4562' },
  { id: '4', name: 'Lisa Weber', email: 'lisa@minga-greens.de', role: 'PRODUCTION_STAFF', is_active: true, last_login: '2026-04-08T06:45:00Z', created_at: '2025-03-20T07:00:00Z' },
  { id: '5', name: 'Thomas Becker', email: 'thomas@minga-greens.de', role: 'ACCOUNTING', is_active: true, last_login: '2026-04-07T14:20:00Z', created_at: '2025-04-01T11:00:00Z', phone: '+49 89 123 4564' },
  { id: '6', name: 'Julia Hoffmann', email: 'julia@minga-greens.de', role: 'SALES', is_active: true, last_login: '2026-04-08T10:05:00Z', created_at: '2025-06-15T09:00:00Z' },
  { id: '7', name: 'Markus Klein', email: 'markus@minga-greens.de', role: 'PRODUCTION_STAFF', is_active: false, last_login: '2026-02-14T11:30:00Z', created_at: '2025-05-01T08:00:00Z' },
]

function getMockUsers(): User[] {
  const stored = localStorage.getItem(MOCK_USERS_KEY)
  if (stored) {
    return JSON.parse(stored)
  }
  localStorage.setItem(MOCK_USERS_KEY, JSON.stringify(defaultMockUsers))
  return defaultMockUsers
}

function saveMockUsers(users: User[]): void {
  localStorage.setItem(MOCK_USERS_KEY, JSON.stringify(users))
}

export const usersApi = {
  list: (params?: { role?: UserRole; search?: string }): Promise<{ items: User[]; total: number }> => {
    return new Promise((resolve) => {
      setTimeout(() => {
        let users = getMockUsers()
        if (params?.role) {
          users = users.filter(u => u.role === params.role)
        }
        if (params?.search) {
          const search = params.search.toLowerCase()
          users = users.filter(u =>
            u.name.toLowerCase().includes(search) ||
            u.email.toLowerCase().includes(search)
          )
        }
        resolve({ items: users, total: users.length })
      }, 200)
    })
  },

  get: (id: string): Promise<User> => {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        const users = getMockUsers()
        const user = users.find(u => u.id === id)
        if (user) {
          resolve(user)
        } else {
          reject(new Error('User not found'))
        }
      }, 100)
    })
  },

  create: (data: Partial<User>): Promise<User> => {
    return new Promise((resolve) => {
      setTimeout(() => {
        const users = getMockUsers()
        const newUser: User = {
          id: String(Date.now()),
          name: data.name || '',
          email: data.email || '',
          role: data.role || 'PRODUCTION_STAFF',
          avatar: data.avatar,
        }
        users.push(newUser)
        saveMockUsers(users)
        resolve(newUser)
      }, 200)
    })
  },

  update: (id: string, data: Partial<User>): Promise<User> => {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        const users = getMockUsers()
        const index = users.findIndex(u => u.id === id)
        if (index !== -1) {
          users[index] = { ...users[index], ...data }
          saveMockUsers(users)
          resolve(users[index])
        } else {
          reject(new Error('User not found'))
        }
      }, 200)
    })
  },

  delete: (id: string): Promise<void> => {
    return new Promise((resolve) => {
      setTimeout(() => {
        const users = getMockUsers().filter(u => u.id !== id)
        saveMockUsers(users)
        resolve()
      }, 200)
    })
  },
}

// ==================== GROWTH-TIMELINE-EVENTS ====================

export type GrowthEventTypeKey =
  | 'SOAKING_STARTED'
  | 'SOAKING_COMPLETED'
  | 'SOWING_STARTED'
  | 'SOWING_COMPLETED'
  | 'MOVED_TO_GERMINATION'
  | 'REMOVED_FROM_GERMINATION'
  | 'MOVED_TO_GROW_ROOM'
  | 'MOVED_TO_COOLING'
  | 'PACKAGING_STARTED'
  | 'PACKAGING_COMPLETED'
  | 'NOTE'

export interface GrowthEvent {
  id: string
  grow_batch_id: string
  event_type: GrowthEventTypeKey
  occurred_at: string
  employee_name: string | null
  notes: string | null
  extra: Record<string, any> | null
  created_at: string
}

// ==================== AUTH / WHOAMI ====================

export interface WhoAmI {
  username: string | null
  role: 'FULL' | 'READONLY'
}

export const authApi = {
  whoami: () => api.get<WhoAmI>('/auth/whoami').then(r => r.data),
}

// ==================== CUSTOMER-PRICING ====================

export interface CustomerPrice {
  id: string
  customer_id: string
  product_id: string
  unit_price: number | string
  currency: string
  valid_from: string
  valid_until: string | null
  notes: string | null
  product_name?: string
  product_sku?: string
  created_at: string
  updated_at: string
}

export const customerPricesApi = {
  list: (customerId: string) =>
    api.get<CustomerPrice[]>(`/sales/customers/${customerId}/prices`).then(r => r.data),

  create: (customerId: string, data: {
    product_id: string;
    unit_price: number;
    valid_from?: string;
    valid_until?: string;
    notes?: string;
  }) =>
    api.post<CustomerPrice>(`/sales/customers/${customerId}/prices`, data).then(r => r.data),

  update: (priceId: string, data: Partial<Pick<CustomerPrice, 'unit_price' | 'valid_from' | 'valid_until' | 'notes'>>) =>
    api.patch<CustomerPrice>(`/sales/customer-prices/${priceId}`, data).then(r => r.data),

  delete: (priceId: string) =>
    api.delete(`/sales/customer-prices/${priceId}`).then(r => r.data),

  getEffective: (customerId: string, productId: string) =>
    api.get<{ unit_price: string; is_customer_specific: boolean; base_price: string | null }>(
      `/sales/customers/${customerId}/effective-price/${productId}`
    ).then(r => r.data),
}

// ==================== ADMIN SETTINGS (SMTP etc.) ====================

export interface AppSettingResponse {
  key: string
  label: string
  is_secret: boolean
  has_value: boolean
  value: string | null
  source: 'db' | 'env' | 'none'
}

export const adminApi = {
  listSettings: () =>
    api.get<AppSettingResponse[]>('/admin/settings').then(r => r.data),

  updateSettings: (updates: Record<string, string | null>) =>
    api.patch<{ changed: number }>('/admin/settings', updates).then(r => r.data),

  sendTestEmail: (toEmail: string) =>
    api.post<{ sent_to: string; ok: boolean }>('/admin/test-email', null, {
      params: { to: toEmail },
    }).then(r => r.data),
}

// ==================== ATTACHMENTS (Zertifikate, Datenblätter) ====================

export type AttachmentEntityType = 'supplier' | 'product' | 'harvest' | 'seed_inventory'

export interface Attachment {
  id: string
  entity_type: AttachmentEntityType
  entity_id: string
  filename: string
  content_type: string | null
  size_bytes: number
  certificate_type: string | null
  bio_kontrollstelle: string | null
  valid_until: string | null
  notes: string | null
  uploaded_at: string
  uploaded_by: string | null
}

export const attachmentsApi = {
  list: (entityType: AttachmentEntityType, entityId: string) =>
    api.get<Attachment[]>(`/attachments/${entityType}/${entityId}`).then(r => r.data),

  upload: async (
    entityType: AttachmentEntityType,
    entityId: string,
    file: File,
    meta: {
      certificate_type?: string;
      bio_kontrollstelle?: string;
      valid_until?: string;
      notes?: string;
    } = {},
  ) => {
    const form = new FormData()
    form.append('file', file)
    if (meta.certificate_type) form.append('certificate_type', meta.certificate_type)
    if (meta.bio_kontrollstelle) form.append('bio_kontrollstelle', meta.bio_kontrollstelle)
    if (meta.valid_until) form.append('valid_until', meta.valid_until)
    if (meta.notes) form.append('notes', meta.notes)
    const res = await api.post<Attachment>(
      `/attachments/${entityType}/${entityId}`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    return res.data
  },

  update: (id: string, data: Partial<Pick<Attachment, 'certificate_type' | 'bio_kontrollstelle' | 'valid_until' | 'notes'>>) =>
    api.patch<Attachment>(`/attachments/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/attachments/${id}`).then(r => r.data),

  download: async (att: Attachment) => {
    const res = await api.get(`/attachments/${att.id}/download`, { responseType: 'blob' })
    const blob = new Blob([res.data], { type: att.content_type || 'application/octet-stream' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = att.filename
    a.target = '_blank'
    a.rel = 'noopener'
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 5000)
  },
}

// ==================== BELEGKETTE (AB / Lieferschein / Packliste) ====================

export interface OrderConfirmation {
  id: string
  order_id: string
  confirmation_number: string
  status: 'ENTWURF' | 'VERSENDET'
  issued_at: string
  sent_at: string | null
  sent_to_email: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface PackingListItem {
  id: string
  order_line_id: string | null
  sort_order: number
  product_name: string
  quantity: number
  unit: string
  batch_number: string | null
  harvest_id: string | null
  is_returnable_container: boolean
  container_type: string | null
  container_count: number | null
}

export interface PackingList {
  id: string
  delivery_note_id: string
  packing_list_number: string
  total_weight_g: number | null
  total_packages: number | null
  notes: string | null
  items: PackingListItem[]
  created_at: string
  updated_at: string
}

export interface DeliveryNote {
  id: string
  order_id: string
  delivery_note_number: string
  status: 'ENTWURF' | 'AUSGESTELLT' | 'GELIEFERT'
  issued_at: string
  delivered_at: string | null
  signed_by: string | null
  actual_delivery_date: string | null
  notes: string | null
  packing_list: PackingList | null
  created_at: string
  updated_at: string
}

const _openPdfFromResponse = async (url: string, filename: string) => {
  const res = await api.get(url, { responseType: 'blob' })
  const blob = new Blob([res.data], { type: 'application/pdf' })
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.target = '_blank'
  a.rel = 'noopener'
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(objectUrl), 5000)
}

export const documentsApi = {
  // Auftragsbestätigungen
  listConfirmations: (orderId: string) =>
    api.get<OrderConfirmation[]>(`/sales/orders/${orderId}/confirmations`).then(r => r.data),

  createConfirmation: (orderId: string, data: { notes?: string }) =>
    api.post<OrderConfirmation>(`/sales/orders/${orderId}/confirmations`, data).then(r => r.data),

  sendConfirmation: (confId: string, data: { sent_to_email?: string }) =>
    api.patch<OrderConfirmation>(`/sales/confirmations/${confId}/send`, data).then(r => r.data),

  downloadConfirmationPdf: (conf: OrderConfirmation) =>
    _openPdfFromResponse(`/sales/confirmations/${conf.id}/pdf`, `${conf.confirmation_number}.pdf`),

  // Lieferscheine + Packlisten
  listDeliveryNotes: (orderId: string) =>
    api.get<DeliveryNote[]>(`/sales/orders/${orderId}/delivery-notes`).then(r => r.data),

  createDeliveryNote: (orderId: string, data: { notes?: string; total_weight_g?: number; total_packages?: number; packing_items?: Partial<PackingListItem>[] }) =>
    api.post<DeliveryNote>(`/sales/orders/${orderId}/delivery-notes`, data).then(r => r.data),

  markDelivered: (noteId: string, data: { signed_by?: string; actual_delivery_date?: string }) =>
    api.patch<DeliveryNote>(`/sales/delivery-notes/${noteId}/mark-delivered`, data).then(r => r.data),

  downloadDeliveryNotePdf: (note: DeliveryNote) =>
    _openPdfFromResponse(`/sales/delivery-notes/${note.id}/pdf`, `${note.delivery_note_number}.pdf`),

  downloadPackingListPdf: (note: DeliveryNote) =>
    _openPdfFromResponse(`/sales/delivery-notes/${note.id}/packing-list/pdf`, `${note.packing_list?.packing_list_number || note.delivery_note_number}-packing.pdf`),
}

export default api
