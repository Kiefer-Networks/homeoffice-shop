import { create } from 'zustand'
import { authApi } from '@/services/authApi'
import type { User } from '@/types'

interface AuthState {
  accessToken: string | null
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  setAccessToken: (token: string | null) => void
  setUser: (user: User | null) => void
  logout: () => void
  refreshBudget: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  user: null,
  isAuthenticated: false,
  isLoading: true,
  setAccessToken: (token) => set({ accessToken: token, isAuthenticated: !!token }),
  setUser: (user) => set({ user, isLoading: false }),
  logout: () => set({ accessToken: null, user: null, isAuthenticated: false, isLoading: false }),
  refreshBudget: async () => {
    try {
      const { data } = await authApi.getBudget()
      const user = get().user
      if (user) {
        set({
          user: {
            ...user,
            total_budget_cents: data.total_budget_cents,
            available_budget_cents: data.available_budget_cents,
          },
        })
      }
    } catch {
      // Silently fail — budget will refresh on next full page load
    }
  },
}))
