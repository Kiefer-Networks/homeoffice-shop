import api from './api'
import type { Product, ProductSearchResult, Category } from '@/types'

export const productApi = {
  search: (params: URLSearchParams) =>
    api.get<ProductSearchResult>('/api/products', { params }),
  getById: (id: string) => api.get<Product>(`/api/products/${id}`),
  refreshPrices: () => api.post('/api/products/refresh-prices'),
  getCategories: () => api.get<Category[]>('/api/categories'),
}
