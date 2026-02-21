import { create } from 'zustand'
import api from '@/services/api'

interface BrandingState {
  companyName: string
  fetchBranding: () => Promise<void>
}

export const useBrandingStore = create<BrandingState>((set) => ({
  companyName: 'Home Office Shop',
  fetchBranding: async () => {
    try {
      const { data } = await api.get<{ company_name: string }>('/api/branding')
      const name = data.company_name || 'Home Office Shop'
      document.title = name
      set({ companyName: name })
    } catch {
      // Branding fetch failed, keep default
    }
  },
}))
