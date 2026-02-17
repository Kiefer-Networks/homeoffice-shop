import { create } from 'zustand'
import api from '@/services/api'

interface BrandingState {
  companyName: string
  loaded: boolean
  fetchBranding: () => Promise<void>
}

export const useBrandingStore = create<BrandingState>((set) => ({
  companyName: 'Home Office Shop',
  loaded: false,
  fetchBranding: async () => {
    try {
      const { data } = await api.get<{ company_name: string }>('/api/branding')
      const name = data.company_name || 'Home Office Shop'
      document.title = name
      set({ companyName: name, loaded: true })
    } catch {
      set({ loaded: true })
    }
  },
}))
