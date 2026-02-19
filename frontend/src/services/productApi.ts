import api from './api'
import type { ProductSearchResult, Category } from '@/types'

export const productApi = {
  search: (params: URLSearchParams) =>
    api.get<ProductSearchResult>('/api/products', { params }),
  getCategories: () => api.get<Category[]>('/api/categories'),
}
