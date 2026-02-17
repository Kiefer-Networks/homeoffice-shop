import api from './api'
import type { Order, PaginatedResponse } from '@/types'

export const orderApi = {
  list: (params?: { page?: number; per_page?: number }) =>
    api.get<PaginatedResponse<Order>>('/api/orders', { params }),
  getById: (id: string) => api.get<Order>(`/api/orders/${id}`),
  create: (data: { delivery_note?: string; confirm_price_changes?: boolean }) =>
    api.post<Order>('/api/orders', data),
}
