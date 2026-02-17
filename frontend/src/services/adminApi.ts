import api from './api'
import type {
  Product, Category, Order, UserAdmin, BudgetAdjustment,
  AuditLogEntry, HiBobSyncLog, PaginatedResponse, NotificationPrefs
} from '@/types'

export const adminApi = {
  // Products
  createProduct: (data: Partial<Product>) => api.post<Product>('/api/admin/products', data),
  updateProduct: (id: string, data: Partial<Product>) => api.put<Product>(`/api/admin/products/${id}`, data),
  activateProduct: (id: string) => api.post<Product>(`/api/admin/products/${id}/activate`),
  deactivateProduct: (id: string) => api.post<Product>(`/api/admin/products/${id}/deactivate`),
  redownloadImages: (id: string) => api.post(`/api/admin/products/${id}/redownload-images`),
  icecatLookup: (gtin: string) => api.post('/api/admin/icecat/lookup', { gtin }),

  // Categories
  listCategories: () => api.get<Category[]>('/api/admin/categories'),
  createCategory: (data: Partial<Category>) => api.post<Category>('/api/admin/categories', data),
  updateCategory: (id: string, data: Partial<Category>) => api.put<Category>(`/api/admin/categories/${id}`, data),
  deleteCategory: (id: string) => api.delete(`/api/admin/categories/${id}`),
  reorderCategories: (items: { id: string; sort_order: number }[]) =>
    api.put('/api/admin/categories/reorder', items),

  // Orders
  listOrders: (params?: Record<string, string | number>) =>
    api.get<PaginatedResponse<Order>>('/api/admin/orders', { params }),
  getOrder: (id: string) => api.get<Order>(`/api/admin/orders/${id}`),
  updateOrderStatus: (id: string, data: { status: string; admin_note?: string }) =>
    api.put(`/api/admin/orders/${id}/status`, data),
  checkOrderItem: (orderId: string, itemId: string, vendor_ordered: boolean) =>
    api.put(`/api/admin/orders/${orderId}/items/${itemId}/check`, { vendor_ordered }),

  // Users
  listUsers: (params?: Record<string, string | number>) =>
    api.get<PaginatedResponse<UserAdmin>>('/api/admin/users', { params }),
  updateUserRole: (id: string, role: string) =>
    api.put(`/api/admin/users/${id}/role`, { role }),
  updateProbationOverride: (id: string, probation_override: boolean) =>
    api.put(`/api/admin/users/${id}/probation-override`, { probation_override }),

  // Budgets
  listAdjustments: (params?: Record<string, string | number>) =>
    api.get<PaginatedResponse<BudgetAdjustment>>('/api/admin/budgets/adjustments', { params }),
  createAdjustment: (data: { user_id: string; amount_cents: number; reason: string }) =>
    api.post('/api/admin/budgets/adjustments', data),

  // Settings
  getSettings: () => api.get<{ settings: Record<string, string> }>('/api/admin/settings'),
  updateSetting: (key: string, value: string) =>
    api.put(`/api/admin/settings/${key}`, { value }),

  // Notifications
  getNotificationPrefs: () => api.get<NotificationPrefs>('/api/admin/notifications/preferences'),
  updateNotificationPrefs: (data: Partial<NotificationPrefs>) =>
    api.put('/api/admin/notifications/preferences', data),

  // Audit
  listAuditLogs: (params?: Record<string, string | number>) =>
    api.get<PaginatedResponse<AuditLogEntry>>('/api/admin/audit', { params }),
  exportAuditCsv: (params?: Record<string, string>) =>
    api.get('/api/admin/audit/export', { params, responseType: 'blob' }),

  // HiBob
  triggerSync: () => api.post('/api/admin/hibob/sync'),
  getSyncLogs: (params?: Record<string, string | number>) =>
    api.get<PaginatedResponse<HiBobSyncLog>>('/api/admin/hibob/sync-log', { params }),
}
