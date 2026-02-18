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
  role: 'employee' | 'admin' | 'manager'
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

export interface UserSearchResult {
  id: string
  email: string
  display_name: string
  department: string | null
  avatar_url: string | null
}

export interface BudgetSummary {
  total_budget_cents: number
  spent_cents: number
  adjustment_cents: number
  available_cents: number
}

export interface BudgetTimelineEntry {
  year: number
  period_from: string
  period_to: string
  amount_cents: number
  cumulative_cents: number
  source: string
}

export interface BudgetRule {
  id: string
  effective_from: string
  initial_cents: number
  yearly_increment_cents: number
  created_by: string
  created_at: string
}

export interface UserBudgetOverride {
  id: string
  user_id: string
  effective_from: string
  effective_until: string | null
  initial_cents: number
  yearly_increment_cents: number
  reason: string
  created_by: string
  created_at: string
}

export interface UserPurchaseReview {
  id: string
  entry_date: string
  description: string
  amount_cents: number
  currency: string
  status: 'pending' | 'matched' | 'adjusted' | 'dismissed'
  matched_order_id: string | null
}

export interface UserDetailResponse {
  user: UserAdmin
  orders: Order[]
  adjustments: BudgetAdjustment[]
  budget_summary: BudgetSummary
  budget_timeline: BudgetTimelineEntry[]
  budget_overrides: UserBudgetOverride[]
  purchase_reviews: UserPurchaseReview[]
}

export interface Brand {
  id: string
  name: string
  slug: string
  logo_url: string | null
  created_at: string
}

export interface ProductVariant {
  group: string
  value: string
  asin: string
  price_cents: number
  image_url: string | null
  is_selected?: boolean
}

export interface Product {
  id: string
  category_id: string
  name: string
  description: string | null
  brand: string | null
  brand_id: string | null
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
  variants: ProductVariant[] | null
  amazon_asin: string | null
  external_url: string
  is_active: boolean
  archived_at: string | null
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
  variant_asin: string | null
  variant_value: string | null
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
  variant_asin: string | null
  variant_value: string | null
}

export interface OrderInvoice {
  id: string
  filename: string
  uploaded_by: string
  uploaded_at: string
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
  expected_delivery: string | null
  purchase_url: string | null
  reviewed_by: string | null
  reviewed_at: string | null
  cancellation_reason: string | null
  cancelled_by: string | null
  cancelled_at: string | null
  items: OrderItem[]
  invoices: OrderInvoice[]
  created_at: string
  updated_at: string
}

export interface BudgetResponse {
  total_budget_cents: number
  available_budget_cents: number
}

export interface BudgetAdjustment {
  id: string
  user_id: string
  amount_cents: number
  reason: string
  source?: string
  hibob_entry_id?: string | null
  created_by: string
  created_at: string
  user_display_name?: string | null
  creator_display_name?: string | null
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

export interface HiBobPurchaseSyncLog {
  id: string
  status: string
  entries_found: number
  matched: number
  auto_adjusted: number
  pending_review: number
  error_message: string | null
  started_at: string
  completed_at: string | null
}

export interface HiBobPurchaseReview {
  id: string
  user_id: string
  user_display_name?: string
  hibob_employee_id: string
  hibob_entry_id: string
  entry_date: string
  description: string
  amount_cents: number
  currency: string
  status: 'pending' | 'matched' | 'adjusted' | 'dismissed'
  matched_order_id: string | null
  adjustment_id: string | null
  resolved_by: string | null
  resolved_at: string | null
  created_at: string
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
  available_slack_events?: string[]
  available_email_events?: string[]
}

export interface AmazonSearchResult {
  name: string
  asin: string
  price_cents: number
  image_url: string | null
  url: string | null
  rating: number | null
  reviews: number | null
}

export interface AmazonProductDetail {
  name: string
  description: string | null
  brand: string | null
  images: string[]
  price_cents: number
  specifications: Record<string, unknown> | null
  feature_bullets: string[]
  url: string | null
  variants: ProductVariant[]
}

export interface ProductCreateInput {
  category_id: string
  name: string
  description?: string | null
  brand?: string | null
  brand_id: string
  model?: string | null
  price_cents: number
  amazon_asin?: string | null
  external_url: string
  is_active?: boolean
  max_quantity_per_user?: number
}

export interface ProductUpdateInput {
  category_id?: string
  name?: string
  description?: string | null
  brand?: string | null
  brand_id?: string | null
  model?: string | null
  price_cents?: number
  external_url?: string
  is_active?: boolean
  max_quantity_per_user?: number
}

export interface CategoryCreateInput {
  name: string
  slug: string
  description?: string | null
  icon?: string | null
  sort_order?: number
}

export interface CategoryUpdateInput {
  name?: string
  slug?: string
  description?: string | null
  icon?: string | null
  sort_order?: number
}

export interface ProductFieldDiff {
  field: string
  label: string
  old_value: string | number | Record<string, unknown> | unknown[] | null
  new_value: string | number | Record<string, unknown> | unknown[] | null
}

export interface BackupFile {
  filename: string
  size_bytes: number
  created_at: string
}

export interface BackupSchedule {
  enabled: boolean
  hour: number
  minute: number
  max_backups: number
}

export interface RefreshPreviewResponse {
  product_id: string
  images_updated: boolean
  image_url: string | null
  image_gallery: string[] | null
  diffs: ProductFieldDiff[]
}
