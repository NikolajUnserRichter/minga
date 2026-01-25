// Basis-Typen

export interface Seed {
  id: string
  name: string
  sorte: string | null
  lieferant: string | null
  keimdauer_tage: number
  wachstumsdauer_tage: number
  erntefenster_min_tage: number
  erntefenster_optimal_tage: number
  erntefenster_max_tage: number
  ertrag_gramm_pro_tray: number
  verlustquote_prozent: number
  aktiv: boolean
  gesamte_wachstumsdauer: number
  created_at: string
  updated_at: string
}

export interface GrowBatch {
  id: string
  seed_batch_id: string
  tray_anzahl: number
  aussaat_datum: string
  erwartete_ernte_min: string
  erwartete_ernte_optimal: string
  erwartete_ernte_max: string
  status: GrowBatchStatus
  regal_position: string | null
  notizen: string | null
  tage_seit_aussaat: number
  ist_erntereif: boolean
  seed_name: string | null
  created_at: string
  updated_at: string
}

export type GrowBatchStatus = 'KEIMUNG' | 'WACHSTUM' | 'ERNTEREIF' | 'GEERNTET' | 'VERLUST'

export interface Harvest {
  id: string
  grow_batch_id: string
  ernte_datum: string
  menge_gramm: number
  verlust_gramm: number
  qualitaet_note: number | null
  verlustquote: number
  created_at: string
}

export interface Customer {
  id: string
  name: string
  typ: CustomerType
  email: string | null
  telefon: string | null
  adresse: string | null
  liefertage: number[] | null
  aktiv: boolean
  created_at: string
  updated_at: string
}

export type CustomerType = 'GASTRO' | 'HANDEL' | 'PRIVAT'

export interface Order {
  id: string
  kunde_id: string
  liefer_datum: string
  status: OrderStatus
  notizen: string | null
  gesamtwert: number
  kunde_name: string | null
  positionen: OrderItem[]
  bestell_datum: string
  created_at: string
  updated_at: string
}

export type OrderStatus = 'OFFEN' | 'BESTAETIGT' | 'IN_PRODUKTION' | 'BEREIT' | 'GELIEFERT' | 'STORNIERT'

export interface OrderItem {
  id: string
  order_id: string
  seed_id: string
  menge: number
  einheit: string
  preis_pro_einheit: number | null
  positionswert: number
  seed_name: string | null
}

export interface Forecast {
  id: string
  seed_id: string
  kunde_id: string | null
  datum: string
  horizont_tage: number
  prognostizierte_menge: number
  konfidenz_untergrenze: number | null
  konfidenz_obergrenze: number | null
  modell_typ: string
  override_menge: number | null
  override_grund: string | null
  effektive_menge: number
  seed_name: string | null
  kunde_name: string | null
  created_at: string
}

export interface ProductionSuggestion {
  id: string
  forecast_id: string
  seed_id: string
  empfohlene_trays: number
  aussaat_datum: string
  erwartete_ernte_datum: string
  status: SuggestionStatus
  warnungen: Warning[] | null
  seed_name: string | null
  created_at: string
  genehmigt_am: string | null
  genehmigt_von: string | null
}

export type SuggestionStatus = 'VORGESCHLAGEN' | 'GENEHMIGT' | 'ABGELEHNT' | 'UMGESETZT'

export interface Warning {
  typ: string
  nachricht: string
}

// API Response Types
export interface ListResponse<T> {
  items: T[]
  total: number
}

export interface DashboardSummary {
  chargen_nach_status: Record<string, number>
  erntereife_chargen: number
  ernten_diese_woche_gramm: number
  verluste_diese_woche_gramm: number
  woche: {
    start: string
    ende: string
  }
}

// User & Auth Types
export type UserRole = 'ADMIN' | 'SALES' | 'PRODUCTION_PLANNER' | 'PRODUCTION_STAFF' | 'ACCOUNTING'

export interface User {
  id: string
  name: string
  email: string
  role: UserRole
  avatar?: string
}

// Extended types with nested relations
export interface GrowBatchWithSeed extends GrowBatch {
  seed?: Seed
}

export interface OrderWithCustomer extends Order {
  kunde?: Customer
}

export interface OrderItemWithSeed extends OrderItem {
  seed?: Seed
}

export interface ForecastWithSeed extends Forecast {
  seed?: Seed
}

export interface ProductionSuggestionWithSeed extends ProductionSuggestion {
  seed?: Seed
}

// Forecast Accuracy
export interface ForecastAccuracy {
  id: string
  forecast_id: string
  ist_menge: number
  abweichung_absolut: number
  abweichung_prozent: number
  ausgewertet_am: string
}

export interface ForecastAccuracyMetrics {
  durchschnittliche_mape: number
  beste_genauigkeit_prozent: number
  anzahl_warnungen: number
  offene_vorschlaege: number
}

// Subscription
export interface Subscription {
  id: string
  kunde_id: string
  seed_id: string
  menge: number
  einheit: string
  intervall: 'TAEGLICH' | 'WOECHENTLICH'
  liefertage: number[]
  gueltig_von: string
  gueltig_bis: string | null
  aktiv: boolean
  created_at: string
}

// ============== ERP TYPES ==============

// Products
export type ProductCategory = 'MICROGREEN' | 'SEED' | 'PACKAGING' | 'BUNDLE'
export type TaxRate = 'STANDARD' | 'REDUZIERT' | 'STEUERFREI'

export interface Product {
  id: string
  sku: string
  name: string
  category: ProductCategory
  description: string | null
  product_group_id: string | null
  base_unit_id: string | null
  base_price: number | null
  tax_rate: TaxRate
  seed_id: string | null
  grow_plan_id: string | null
  seed_variety: string | null
  shelf_life_days: number | null
  storage_temp_min: number | null
  storage_temp_max: number | null
  min_stock_quantity: number | null
  is_active: boolean
  is_sellable: boolean
  created_at: string
  updated_at: string
}

export interface ProductGroup {
  id: string
  code: string
  name: string
  parent_id: string | null
  description: string | null
  is_active: boolean
}

export interface GrowPlan {
  id: string
  code: string
  name: string
  description: string | null
  soak_hours: number
  blackout_days: number
  germination_days: number
  growth_days: number
  harvest_window_start_days: number
  harvest_window_optimal_days: number
  harvest_window_end_days: number
  expected_yield_grams_per_tray: number
  expected_loss_percent: number
  optimal_temp_celsius: number | null
  optimal_humidity_percent: number | null
  light_hours_per_day: number | null
  seed_density_grams_per_tray: number | null
  is_active: boolean
}

export interface PriceList {
  id: string
  code: string
  name: string
  description: string | null
  currency: string
  valid_from: string | null
  valid_until: string | null
  is_default: boolean
  is_active: boolean
  items?: PriceListItem[]
}

export interface PriceListItem {
  id: string
  price_list_id: string
  product_id: string
  unit_id: string | null
  price: number
  min_quantity: number
  valid_from: string | null
  valid_until: string | null
  is_active: boolean
}

// Invoices
export type InvoiceStatus = 'ENTWURF' | 'OFFEN' | 'TEILBEZAHLT' | 'BEZAHLT' | 'UEBERFAELLIG' | 'STORNIERT'
export type InvoiceType = 'RECHNUNG' | 'GUTSCHRIFT' | 'PROFORMA'
export type PaymentMethod = 'UEBERWEISUNG' | 'LASTSCHRIFT' | 'BAR' | 'KARTE' | 'PAYPAL'

export interface Invoice {
  id: string
  invoice_number: string
  invoice_type: InvoiceType
  customer_id: string
  order_id: string | null
  invoice_date: string
  delivery_date: string | null
  due_date: string
  status: InvoiceStatus
  subtotal: number
  discount_percent: number
  discount_amount: number
  tax_amount: number
  total: number
  paid_amount: number
  billing_address: Record<string, string> | null
  shipping_address: Record<string, string> | null
  header_text: string | null
  footer_text: string | null
  internal_notes: string | null
  datev_exported: boolean
  customer_name?: string
  lines?: InvoiceLine[]
  payments?: Payment[]
  created_at: string
  updated_at: string
}

export interface InvoiceLine {
  id: string
  invoice_id: string
  position: number
  product_id: string | null
  description: string
  sku: string | null
  quantity: number
  unit: string
  unit_price: number
  discount_percent: number
  tax_rate: TaxRate
  line_total: number
  tax_amount: number
}

export interface Payment {
  id: string
  invoice_id: string
  payment_date: string
  amount: number
  payment_method: PaymentMethod
  reference: string | null
  bank_reference: string | null
  notes: string | null
  created_at: string
}

// Inventory
export type LocationType = 'LAGER' | 'KUEHLRAUM' | 'REGAL' | 'KEIMRAUM' | 'VERSAND'
export type ArticleType = 'SAATGUT' | 'FERTIGWARE' | 'VERPACKUNG'
export type MovementType = 'EINGANG' | 'AUSGANG' | 'PRODUKTION' | 'ERNTE' | 'VERLUST' | 'KORREKTUR'

export interface InventoryLocation {
  id: string
  code: string
  name: string
  location_type: LocationType
  description: string | null
  temperature_min: number | null
  temperature_max: number | null
  is_active: boolean
}

export interface SeedInventory {
  id: string
  seed_id: string
  batch_number: string
  location_id: string | null
  initial_quantity: number
  current_quantity: number
  unit: string
  mhd: string | null
  supplier: string | null
  purchase_price: number | null
  is_organic: boolean
  organic_certification: string | null
  min_quantity: number | null
  is_active: boolean
  seed_name?: string
  location_name?: string
}

export interface FinishedGoodsInventory {
  id: string
  product_id: string
  batch_number: string
  location_id: string | null
  harvest_id: string | null
  grow_batch_id: string | null
  seed_inventory_id: string | null
  initial_quantity: number
  current_quantity: number
  reserved_quantity: number
  available_quantity: number
  unit: string
  production_date: string
  mhd: string
  quality_grade: string | null
  is_active: boolean
  product_name?: string
  location_name?: string
}

export interface PackagingInventory {
  id: string
  article_number: string
  name: string
  location_id: string | null
  current_quantity: number
  unit: string
  min_quantity: number | null
  reorder_quantity: number | null
  supplier: string | null
  is_active: boolean
  location_name?: string
}

export interface InventoryMovement {
  id: string
  article_type: ArticleType
  article_id: string
  movement_type: MovementType
  quantity: number
  unit: string
  movement_date: string
  reference_type: string | null
  reference_id: string | null
  notes: string | null
  created_at: string
}

export interface StockOverview {
  article_type: ArticleType
  article_id: string
  article_name: string
  location_name: string | null
  current_quantity: number
  min_quantity: number | null
  unit: string
  is_low_stock: boolean
}

export interface TraceabilityInfo {
  finished_goods_id: string
  product_name: string
  batch_number: string
  production_date: string
  mhd: string
  harvest_id: string | null
  harvest_date: string | null
  grow_batch_id: string | null
  sow_date: string | null
  seed_inventory_id: string | null
  seed_batch_number: string | null
  seed_supplier: string | null
  is_organic: boolean
}
