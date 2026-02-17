export interface User {
  id: string
  email: string
  display_name: string
  department: string | null
  start_date: string | null
  total_budget_cents: number
  available_budget_cents: number
  is_active: boolean
  probation_override: boolean
  role: 'employee' | 'admin'
  avatar_url: string | null
  created_at: string
}

export interface UserAdmin extends User {
  hibob_id: string | null
  manager_email: string | null
  manager_name: string | null
  cached_spent_cents: number
  cached_adjustment_cents: number
  budget_cache_updated_at: string | null
  provider: string | null
  last_hibob_sync: string | null
  updated_at: string
}

export interface Product {
  id: string
  category_id: string
  name: string
  description: string | null
  brand: string | null
  model: string | null
  image_url: string | null
  image_gallery: string[] | null
  specifications: Record<string, unknown> | null
  price_cents: number
  price_min_cents: number | null
  price_max_cents: number | null
  color: string | null
  material: string | null
  product_dimensions: string | null
  item_weight: string | null
  item_model_number: string | null
  product_information: Record<string, unknown> | null
  amazon_asin: string | null
  external_url: string
  is_active: boolean
  max_quantity_per_user: number
  created_at: string
  updated_at: string
}

export interface Category {
  id: string
  name: string
  slug: string
  description: string | null
  icon: string | null
  sort_order: number
  created_at: string
}

export interface CartItem {
  id: string
  product_id: string
  product_name: string
  quantity: number
  price_at_add_cents: number
  current_price_cents: number
  price_changed: boolean
  price_diff_cents: number
  product_active: boolean
  image_url: string | null
  external_url: string
  max_quantity_per_user: number
}

export interface Cart {
  items: CartItem[]
  total_at_add_cents: number
  total_current_cents: number
  has_price_changes: boolean
  has_unavailable_items: boolean
  available_budget_cents: number
  budget_exceeded: boolean
}

export interface OrderItem {
  id: string
  product_id: string
  product_name: string | null
  quantity: number
  price_cents: number
  external_url: string
  vendor_ordered: boolean
}

export interface Order {
  id: string
  user_id: string
  user_email: string | null
  user_display_name: string | null
  status: 'pending' | 'ordered' | 'delivered' | 'rejected' | 'cancelled'
  total_cents: number
  delivery_note: string | null
  admin_note: string | null
  reviewed_by: string | null
  reviewed_at: string | null
  items: OrderItem[]
  created_at: string
  updated_at: string
}

export interface BudgetAdjustment {
  id: string
  user_id: string
  amount_cents: number
  reason: string
  created_by: string
  created_at: string
}

export interface AuditLogEntry {
  id: string
  user_id: string
  user_email: string | null
  action: string
  resource_type: string
  resource_id: string | null
  details: Record<string, unknown> | null
  ip_address: string | null
  correlation_id: string | null
  created_at: string
}

export interface HiBobSyncLog {
  id: string
  status: string
  employees_synced: number
  employees_created: number
  employees_updated: number
  employees_deactivated: number
  error_message: string | null
  started_at: string
  completed_at: string | null
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
}

export interface Facets {
  brands: { value: string; count: number }[]
  categories: { id: string; slug: string; name: string; count: number }[]
  colors: { value: string; count: number }[]
  materials: { value: string; count: number }[]
  price_range: { min_cents: number; max_cents: number }
}

export interface ProductSearchResult {
  items: Product[]
  total: number
  page: number
  per_page: number
  facets: Facets | null
}

export interface NotificationPrefs {
  slack_enabled: boolean
  slack_events: string[]
  email_enabled: boolean
  email_events: string[]
}
