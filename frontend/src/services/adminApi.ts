import api from './api'
import type {
  Product, Category, Order, OrderInvoice, UserAdmin, BudgetAdjustment, Brand,
  AuditLogEntry, HiBobSyncLog, PaginatedResponse, NotificationPrefs,
  ProductCreateInput, ProductUpdateInput, CategoryCreateInput, CategoryUpdateInput,
  UserSearchResult, UserDetailResponse, RefreshPreviewResponse,
  AmazonProductDetail, BudgetRule, UserBudgetOverride,
} from '@/types'

export const adminApi = {
  // Products
  createProduct: (data: ProductCreateInput) => api.post<Product>('/api/admin/products', data),
  updateProduct: (id: string, data: ProductUpdateInput) => api.put<Product>(`/api/admin/products/${id}`, data),
  activateProduct: (id: string) => api.post<Product>(`/api/admin/products/${id}/activate`),
  deactivateProduct: (id: string) => api.post<Product>(`/api/admin/products/${id}/deactivate`),
  archiveProduct: (id: string) => api.delete<Product>(`/api/admin/products/${id}`),
  restoreProduct: (id: string) => api.post<Product>(`/api/admin/products/${id}/restore`),
  refreshPreview: (id: string) =>
    api.post<RefreshPreviewResponse>(`/api/admin/products/${id}/refresh-preview`),
  refreshApply: (id: string, data: { fields: string[]; values: Record<string, unknown> }) =>
    api.post<Product>(`/api/admin/products/${id}/refresh-apply`, data),
  amazonSearch: (query: string) => api.get('/api/admin/amazon/search', { params: { query } }),
  amazonProduct: (asin: string) => api.get<AmazonProductDetail>('/api/admin/amazon/product', { params: { asin } }),

  // Brands
  listBrands: () => api.get<Brand[]>('/api/admin/brands'),
  createBrand: (data: { name: string }) => api.post<Brand>('/api/admin/brands', data),
  updateBrand: (id: string, data: { name?: string; logo_url?: string | null }) =>
    api.put<Brand>(`/api/admin/brands/${id}`, data),
  deleteBrand: (id: string) => api.delete(`/api/admin/brands/${id}`),

  // Categories
  listCategories: () => api.get<Category[]>('/api/admin/categories'),
  createCategory: (data: CategoryCreateInput) => api.post<Category>('/api/admin/categories', data),
  updateCategory: (id: string, data: CategoryUpdateInput) => api.put<Category>(`/api/admin/categories/${id}`, data),
  deleteCategory: (id: string) => api.delete(`/api/admin/categories/${id}`),
  reorderCategories: (items: { id: string; sort_order: number }[]) =>
    api.put('/api/admin/categories/reorder', items),

  // Orders
  listOrders: (params?: Record<string, string | number>) =>
    api.get<PaginatedResponse<Order>>('/api/admin/orders', { params }),
  getOrder: (id: string) => api.get<Order>(`/api/admin/orders/${id}`),
  updateOrderStatus: (id: string, data: {
    status: string; admin_note?: string; expected_delivery?: string; purchase_url?: string
  }) => api.put(`/api/admin/orders/${id}/status`, data),
  updatePurchaseUrl: (orderId: string, purchase_url: string | null) =>
    api.put(`/api/admin/orders/${orderId}/purchase-url`, { purchase_url }),
  uploadInvoice: (orderId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<OrderInvoice>(`/api/admin/orders/${orderId}/invoices`, formData)
  },
  downloadInvoiceUrl: (orderId: string, invoiceId: string) =>
    `/api/admin/orders/${orderId}/invoices/${invoiceId}/download`,
  deleteInvoice: (orderId: string, invoiceId: string) =>
    api.delete(`/api/admin/orders/${orderId}/invoices/${invoiceId}`),
  checkOrderItem: (orderId: string, itemId: string, vendor_ordered: boolean) =>
    api.put(`/api/admin/orders/${orderId}/items/${itemId}/check`, { vendor_ordered }),

  // Users
  listUsers: (params?: Record<string, string | number>) =>
    api.get<PaginatedResponse<UserAdmin>>('/api/admin/users', { params }),
  searchUsers: (q: string, limit?: number) =>
    api.get<UserSearchResult[]>('/api/admin/users/search', { params: { q, limit: limit || 20 } }),
  getUserDetail: (id: string) => api.get<UserDetailResponse>(`/api/admin/users/${id}`),
  updateUserRole: (id: string, role: string) =>
    api.put(`/api/admin/users/${id}/role`, { role }),
  updateProbationOverride: (id: string, probation_override: boolean) =>
    api.put(`/api/admin/users/${id}/probation-override`, { probation_override }),

  // Budgets
  listAdjustments: (params?: Record<string, string | number>) =>
    api.get<PaginatedResponse<BudgetAdjustment>>('/api/admin/budgets/adjustments', { params }),
  createAdjustment: (data: { user_id: string; amount_cents: number; reason: string }) =>
    api.post('/api/admin/budgets/adjustments', data),
  updateAdjustment: (id: string, data: { amount_cents: number; reason: string }) =>
    api.put<BudgetAdjustment>(`/api/admin/budgets/adjustments/${id}`, data),
  deleteAdjustment: (id: string) =>
    api.delete(`/api/admin/budgets/adjustments/${id}`),

  // Settings
  getSettings: () => api.get<{ settings: Record<string, string> }>('/api/admin/settings'),
  updateSetting: (key: string, value: string) =>
    api.put(`/api/admin/settings/${key}`, { value }),
  sendTestEmail: (to: string) =>
    api.post('/api/admin/settings/test-email', { to }),

  // Notifications
  getNotificationPrefs: () => api.get<NotificationPrefs>('/api/admin/notifications/preferences'),
  updateNotificationPrefs: (data: Partial<NotificationPrefs>) =>
    api.put<NotificationPrefs>('/api/admin/notifications/preferences', data),

  // Audit
  listAuditLogs: (params?: Record<string, string | number>) =>
    api.get<PaginatedResponse<AuditLogEntry>>('/api/admin/audit', { params }),
  exportAuditCsv: (params?: Record<string, string>) =>
    api.get('/api/admin/audit/export', { params, responseType: 'blob' }),

  // Budget Rules
  listBudgetRules: () => api.get<BudgetRule[]>('/api/admin/budget-rules'),
  createBudgetRule: (data: { effective_from: string; initial_cents: number; yearly_increment_cents: number }) =>
    api.post<BudgetRule>('/api/admin/budget-rules', data),
  updateBudgetRule: (id: string, data: Partial<{ effective_from: string; initial_cents: number; yearly_increment_cents: number }>) =>
    api.put<BudgetRule>(`/api/admin/budget-rules/${id}`, data),
  deleteBudgetRule: (id: string) =>
    api.delete(`/api/admin/budget-rules/${id}`),

  // User Budget Overrides
  createUserBudgetOverride: (userId: string, data: {
    effective_from: string; effective_until?: string | null;
    initial_cents: number; yearly_increment_cents: number; reason: string
  }) => api.post<UserBudgetOverride>(`/api/admin/users/${userId}/budget-overrides`, data),
  updateUserBudgetOverride: (userId: string, overrideId: string, data: Partial<{
    effective_from: string; effective_until: string | null;
    initial_cents: number; yearly_increment_cents: number; reason: string
  }>) => api.put<UserBudgetOverride>(`/api/admin/users/${userId}/budget-overrides/${overrideId}`, data),
  deleteUserBudgetOverride: (userId: string, overrideId: string) =>
    api.delete(`/api/admin/users/${userId}/budget-overrides/${overrideId}`),

  // HiBob
  triggerSync: () => api.post('/api/admin/hibob/sync'),
  getSyncLogs: (params?: Record<string, string | number>) =>
    api.get<PaginatedResponse<HiBobSyncLog>>('/api/admin/hibob/sync-log', { params }),
}
