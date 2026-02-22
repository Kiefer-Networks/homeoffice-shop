import type { AxiosRequestConfig, AxiosResponse } from 'axios'
import api from './api'
import type { ProductSearchResult, Category, SearchSuggestion } from '@/types'

let categoriesPromise: Promise<AxiosResponse<Category[]>> | null = null
let categoriesCacheTime = 0
const CACHE_TTL = 60_000 // 1 minute

export const productApi = {
  search: (params: URLSearchParams) =>
    api.get<ProductSearchResult>('/api/products', { params }),
  getSearchSuggestions: (q: string, config?: AxiosRequestConfig) =>
    api.get<SearchSuggestion[]>('/api/products/suggestions', { params: { q }, ...config }),
  getCategories: () => {
    const now = Date.now()
    if (categoriesPromise && (now - categoriesCacheTime) < CACHE_TTL) {
      return categoriesPromise
    }
    categoriesPromise = api.get<Category[]>('/api/categories')
    categoriesCacheTime = now
    categoriesPromise.catch(() => { categoriesPromise = null; categoriesCacheTime = 0 })
    return categoriesPromise
  },
}
