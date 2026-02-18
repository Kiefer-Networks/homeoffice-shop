import api from './api'
import type { Cart } from '@/types'

export const cartApi = {
  get: () => api.get<Cart>('/api/cart'),
  addItem: (product_id: string, quantity: number = 1, variant_asin?: string) =>
    api.post('/api/cart/items', { product_id, quantity, ...(variant_asin ? { variant_asin } : {}) }),
  updateItem: (product_id: string, quantity: number) =>
    api.put(`/api/cart/items/${product_id}`, { quantity }),
  removeItem: (product_id: string) =>
    api.delete(`/api/cart/items/${product_id}`),
  clear: () => api.delete('/api/cart'),
}
