import axios from 'axios'
import type {
  Seed, GrowBatch, Harvest, Customer, Order, Forecast,
  ProductionSuggestion, ListResponse, DashboardSummary,
  Product, ProductGroup, GrowPlan, PriceList, PriceListItem,
  Invoice, InvoiceLine, Payment, InvoiceStatus, InvoiceType,
  InventoryLocation, SeedInventory, FinishedGoodsInventory,
  PackagingInventory, InventoryMovement, StockOverview, TraceabilityInfo,
  ArticleType, LocationType, TraceabilityChain, Capacity,
  RevenueStats, YieldStats, Subscription, AccuracySummary, AccuracyDetail
} from '../types'

import keycloak from './auth';

// API Configuration
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add Auth Interceptor
api.interceptors.request.use(async (config) => {
  if (keycloak.token) {
    try {
      // Update token if it's about to expire (within 30 seconds)
      await keycloak.updateToken(30);
      config.headers.Authorization = `Bearer ${keycloak.token}`;
    } catch (error) {
      console.error('Failed to update token', error);
      // Optional: Force login if update fails? 
      // keycloak.login(); 
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
}

// Production API
export const productionApi = {
  listGrowBatches: (params?: { status?: string; erntereif?: boolean }) =>
    api.get<ListResponse<GrowBatch>>('/production/grow-batches', { params }).then(r => r.data),

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
  listCustomers: (params?: { typ?: string; aktiv?: boolean }) =>
    api.get<ListResponse<Customer>>('/sales/customers', { params }).then(r => r.data),

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
    kunde_id: string
    liefer_datum: string
    positionen: Array<{
      seed_id: string
      menge: number
      einheit: string
      preis_pro_einheit?: number
    }>
    notizen?: string
  }) =>
    api.post<Order>('/sales/orders', data).then(r => r.data),

  updateOrderStatus: (id: string, status: string) =>
    api.post<Order>(`/sales/orders/${id}/status/${status}`).then(r => r.data),

  runDailySubscriptions: () =>
    api.post('/sales/subscriptions/process-today').then(r => r.data),
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
    purchase_price?: number
    is_organic?: boolean
    organic_certification?: string
  }) =>
    api.post<SeedInventory>('/inventory/seeds/receive', null, { params: data }).then(r => r.data),

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
    seed_id: string
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
  { id: '1', name: 'Max Mustermann', email: 'max@minga-greens.de', role: 'ADMIN' },
  { id: '2', name: 'Anna Schmidt', email: 'anna@minga-greens.de', role: 'SALES' },
  { id: '3', name: 'Peter Müller', email: 'peter@minga-greens.de', role: 'PRODUCTION_PLANNER' },
  { id: '4', name: 'Lisa Weber', email: 'lisa@minga-greens.de', role: 'PRODUCTION_STAFF' },
  { id: '5', name: 'Thomas Becker', email: 'thomas@minga-greens.de', role: 'ACCOUNTING' },
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

export default api
