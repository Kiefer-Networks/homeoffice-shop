/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { User } from '@/types'

// Mock authApi to avoid real network calls
vi.mock('@/services/authApi', () => ({
  authApi: {
    getBudget: vi.fn(),
    getMe: vi.fn(),
    refresh: vi.fn(),
    logout: vi.fn(),
  },
}))

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 'user-1',
    email: 'test@example.com',
    display_name: 'Test User',
    department: 'Engineering',
    start_date: '2023-01-15',
    total_budget_cents: 75000,
    available_budget_cents: 50000,
    is_active: true,
    probation_override: false,
    role: 'employee',
    avatar_url: null,
    created_at: '2023-01-15T00:00:00Z',
    ...overrides,
  }
}

describe('authStore', () => {
  beforeEach(async () => {
    vi.resetModules()
    vi.clearAllMocks()
  })

  async function getStore() {
    const { useAuthStore } = await import('../authStore')
    return useAuthStore
  }

  describe('setAccessToken', () => {
    it('stores the access token and sets isAuthenticated to true', async () => {
      const useAuthStore = await getStore()
      useAuthStore.getState().setAccessToken('my-token')

      const state = useAuthStore.getState()
      expect(state.accessToken).toBe('my-token')
      expect(state.isAuthenticated).toBe(true)
    })

    it('sets isAuthenticated to false when token is null', async () => {
      const useAuthStore = await getStore()
      useAuthStore.getState().setAccessToken('my-token')
      useAuthStore.getState().setAccessToken(null)

      const state = useAuthStore.getState()
      expect(state.accessToken).toBeNull()
      expect(state.isAuthenticated).toBe(false)
    })
  })

  describe('setUser', () => {
    it('stores the user and sets isLoading to false', async () => {
      const useAuthStore = await getStore()
      const user = makeUser()
      useAuthStore.getState().setUser(user)

      const state = useAuthStore.getState()
      expect(state.user).toEqual(user)
      expect(state.isLoading).toBe(false)
    })

    it('clears user when set to null', async () => {
      const useAuthStore = await getStore()
      useAuthStore.getState().setUser(makeUser())
      useAuthStore.getState().setUser(null)

      expect(useAuthStore.getState().user).toBeNull()
      expect(useAuthStore.getState().isLoading).toBe(false)
    })
  })

  describe('logout', () => {
    it('clears all auth state', async () => {
      const useAuthStore = await getStore()
      useAuthStore.getState().setAccessToken('some-token')
      useAuthStore.getState().setUser(makeUser())

      useAuthStore.getState().logout()

      const state = useAuthStore.getState()
      expect(state.accessToken).toBeNull()
      expect(state.user).toBeNull()
      expect(state.isAuthenticated).toBe(false)
      expect(state.isLoading).toBe(false)
    })
  })

  describe('refreshBudget', () => {
    it('updates budget info on the current user', async () => {
      const { authApi } = await import('@/services/authApi')
      const mocked = vi.mocked(authApi)
      mocked.getBudget.mockResolvedValue({
        data: {
          total_budget_cents: 100000,
          available_budget_cents: 80000,
        },
      } as any)

      const useAuthStore = await getStore()
      useAuthStore.getState().setUser(makeUser())
      await useAuthStore.getState().refreshBudget()

      const state = useAuthStore.getState()
      expect(state.user!.total_budget_cents).toBe(100000)
      expect(state.user!.available_budget_cents).toBe(80000)
    })

    it('does not crash when there is no user', async () => {
      const { authApi } = await import('@/services/authApi')
      const mocked = vi.mocked(authApi)
      mocked.getBudget.mockResolvedValue({
        data: {
          total_budget_cents: 100000,
          available_budget_cents: 80000,
        },
      } as any)

      const useAuthStore = await getStore()
      // No user set
      await useAuthStore.getState().refreshBudget()

      expect(useAuthStore.getState().user).toBeNull()
    })

    it('silently fails on API error', async () => {
      const { authApi } = await import('@/services/authApi')
      const mocked = vi.mocked(authApi)
      mocked.getBudget.mockRejectedValue(new Error('Network error'))

      const useAuthStore = await getStore()
      const user = makeUser()
      useAuthStore.getState().setUser(user)

      // Should not throw
      await useAuthStore.getState().refreshBudget()

      // Budget should remain unchanged
      const state = useAuthStore.getState()
      expect(state.user!.total_budget_cents).toBe(75000)
      expect(state.user!.available_budget_cents).toBe(50000)
    })
  })

  describe('role checks', () => {
    it('admin user has role "admin"', async () => {
      const useAuthStore = await getStore()
      useAuthStore.getState().setUser(makeUser({ role: 'admin' }))

      expect(useAuthStore.getState().user!.role).toBe('admin')
    })

    it('manager user has role "manager"', async () => {
      const useAuthStore = await getStore()
      useAuthStore.getState().setUser(makeUser({ role: 'manager' }))

      expect(useAuthStore.getState().user!.role).toBe('manager')
    })

    it('employee user has role "employee"', async () => {
      const useAuthStore = await getStore()
      useAuthStore.getState().setUser(makeUser({ role: 'employee' }))

      expect(useAuthStore.getState().user!.role).toBe('employee')
    })
  })
})
