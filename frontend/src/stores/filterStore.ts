import { create } from 'zustand'

interface FilterState {
  q: string
  category: string
  brand: string
  color: string
  material: string
  priceMin: string
  priceMax: string
  sort: string
  page: number
  setFilter: (key: string, value: string | number) => void
  resetFilters: () => void
  syncFromUrl: (params: URLSearchParams) => void
  toSearchParams: () => URLSearchParams
}

const defaults = {
  q: '',
  category: '',
  brand: '',
  color: '',
  material: '',
  priceMin: '',
  priceMax: '',
  sort: 'relevance',
  page: 1,
}

export const useFilterStore = create<FilterState>((set, get) => ({
  ...defaults,
  setFilter: (key, value) => set({ [key]: value, ...(key !== 'page' ? { page: 1 } : {}) }),
  resetFilters: () => set(defaults),
  syncFromUrl: (params) => set({
    q: params.get('q') || '',
    category: params.get('category') || '',
    brand: params.get('brand') || '',
    color: params.get('color') || '',
    material: params.get('material') || '',
    priceMin: params.get('price_min') || '',
    priceMax: params.get('price_max') || '',
    sort: params.get('sort') || 'relevance',
    page: parseInt(params.get('page') || '1', 10),
  }),
  toSearchParams: () => {
    const state = get()
    const params = new URLSearchParams()
    if (state.q) params.set('q', state.q)
    if (state.category) params.set('category', state.category)
    if (state.brand) params.set('brand', state.brand)
    if (state.color) params.set('color', state.color)
    if (state.material) params.set('material', state.material)
    if (state.priceMin) params.set('price_min', state.priceMin)
    if (state.priceMax) params.set('price_max', state.priceMax)
    if (state.sort !== 'relevance') params.set('sort', state.sort)
    if (state.page > 1) params.set('page', state.page.toString())
    return params
  },
}))
