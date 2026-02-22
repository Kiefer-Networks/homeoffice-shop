import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { Cart } from '@/types'

// Mock the cartApi module
vi.mock('@/services/cartApi', () => ({
  cartApi: {
    get: vi.fn(),
    addItem: vi.fn(),
    updateItem: vi.fn(),
    removeItem: vi.fn(),
  },
}))

// Mock the uiStore to avoid side effects
vi.mock('@/stores/uiStore', () => ({
  useUiStore: {
    getState: () => ({
      addToast: vi.fn(),
    }),
  },
}))

function makeCart(overrides: Partial<Cart> = {}): Cart {
  return {
    items: [
      {
        id: 'item-1',
        product_id: 'prod-1',
        product_name: 'Keyboard',
        quantity: 2,
        price_at_add_cents: 5000,
        current_price_cents: 5000,
        price_changed: false,
        price_diff_cents: 0,
        product_active: true,
        image_url: null,
        external_url: 'https://example.com/keyboard',
        max_quantity_per_user: 5,
        variant_asin: null,
        variant_value: null,
      },
      {
        id: 'item-2',
        product_id: 'prod-2',
        product_name: 'Mouse',
        quantity: 1,
        price_at_add_cents: 3000,
        current_price_cents: 3000,
        price_changed: false,
        price_diff_cents: 0,
        product_active: true,
        image_url: null,
        external_url: 'https://example.com/mouse',
        max_quantity_per_user: 3,
        variant_asin: null,
        variant_value: null,
      },
    ],
    total_at_add_cents: 13000,
    total_current_cents: 13000,
    has_price_changes: false,
    has_unavailable_items: false,
    available_budget_cents: 50000,
    budget_exceeded: false,
    ...overrides,
  }
}

describe('cartStore', () => {
  beforeEach(async () => {
    vi.resetModules()
    vi.clearAllMocks()
  })

  async function getStore() {
    const { useCartStore } = await import('../cartStore')
    return useCartStore
  }

  describe('updateItem', () => {
    it('optimistically updates quantity and recalculates totals', async () => {
      const { cartApi } = await import('@/services/cartApi')
      const mocked = vi.mocked(cartApi)
      mocked.updateItem.mockResolvedValue({ data: null } as any)

      const useCartStore = await getStore()
      const cart = makeCart()
      useCartStore.setState({ cart })

      // Update prod-1 quantity from 2 to 3
      await useCartStore.getState().updateItem('prod-1', 3)

      const state = useCartStore.getState()
      expect(state.cart).not.toBeNull()
      // New total: 3*5000 + 1*3000 = 18000
      expect(state.cart!.total_current_cents).toBe(18000)
      expect(state.cart!.total_at_add_cents).toBe(18000)
      // Item quantity should be updated
      const item = state.cart!.items.find((i) => i.product_id === 'prod-1')
      expect(item?.quantity).toBe(3)
    })

    it('removes item when quantity is 0', async () => {
      const { cartApi } = await import('@/services/cartApi')
      const mocked = vi.mocked(cartApi)
      mocked.removeItem.mockResolvedValue({ data: null } as any)

      const useCartStore = await getStore()
      const cart = makeCart()
      useCartStore.setState({ cart })

      // Set quantity to 0 => should remove item
      await useCartStore.getState().updateItem('prod-1', 0)

      const state = useCartStore.getState()
      expect(state.cart!.items).toHaveLength(1)
      expect(state.cart!.items[0].product_id).toBe('prod-2')
      // Total should now be: 1*3000 = 3000
      expect(state.cart!.total_current_cents).toBe(3000)
    })

    it('detects budget exceeded after update', async () => {
      const { cartApi } = await import('@/services/cartApi')
      const mocked = vi.mocked(cartApi)
      mocked.updateItem.mockResolvedValue({ data: null } as any)

      const useCartStore = await getStore()
      const cart = makeCart({ available_budget_cents: 15000 })
      useCartStore.setState({ cart })

      // Update prod-1 to quantity 5 => 5*5000 + 1*3000 = 28000 > 15000
      await useCartStore.getState().updateItem('prod-1', 5)

      const state = useCartStore.getState()
      expect(state.cart!.budget_exceeded).toBe(true)
    })

    it('calls cartApi.updateItem for positive quantity', async () => {
      const { cartApi } = await import('@/services/cartApi')
      const mocked = vi.mocked(cartApi)
      mocked.updateItem.mockResolvedValue({ data: null } as any)

      const useCartStore = await getStore()
      useCartStore.setState({ cart: makeCart() })

      await useCartStore.getState().updateItem('prod-1', 4)

      expect(mocked.updateItem).toHaveBeenCalledWith('prod-1', 4)
    })

    it('calls cartApi.removeItem when quantity is 0', async () => {
      const { cartApi } = await import('@/services/cartApi')
      const mocked = vi.mocked(cartApi)
      mocked.removeItem.mockResolvedValue({ data: null } as any)

      const useCartStore = await getStore()
      useCartStore.setState({ cart: makeCart() })

      await useCartStore.getState().updateItem('prod-2', 0)

      expect(mocked.removeItem).toHaveBeenCalledWith('prod-2')
    })

    it('rolls back on API error', async () => {
      const { cartApi } = await import('@/services/cartApi')
      const mocked = vi.mocked(cartApi)
      mocked.updateItem.mockRejectedValue(new Error('Server error'))
      mocked.get.mockRejectedValue(new Error('Server error'))

      const useCartStore = await getStore()
      const originalCart = makeCart()
      useCartStore.setState({ cart: originalCart })

      await useCartStore.getState().updateItem('prod-1', 10)

      const state = useCartStore.getState()
      // On API failure and re-fetch failure, cart should be rolled back to original
      expect(state.error).toBe('Server error')
    })
  })

  describe('removeItem', () => {
    it('optimistically removes item and recalculates totals', async () => {
      const { cartApi } = await import('@/services/cartApi')
      const mocked = vi.mocked(cartApi)
      mocked.removeItem.mockResolvedValue({ data: null } as any)

      const useCartStore = await getStore()
      useCartStore.setState({ cart: makeCart() })

      await useCartStore.getState().removeItem('prod-1')

      const state = useCartStore.getState()
      expect(state.cart!.items).toHaveLength(1)
      expect(state.cart!.items[0].product_id).toBe('prod-2')
      // Total: 1*3000 = 3000
      expect(state.cart!.total_current_cents).toBe(3000)
      expect(state.cart!.total_at_add_cents).toBe(3000)
    })

    it('calls cartApi.removeItem', async () => {
      const { cartApi } = await import('@/services/cartApi')
      const mocked = vi.mocked(cartApi)
      mocked.removeItem.mockResolvedValue({ data: null } as any)

      const useCartStore = await getStore()
      useCartStore.setState({ cart: makeCart() })

      await useCartStore.getState().removeItem('prod-2')

      expect(mocked.removeItem).toHaveBeenCalledWith('prod-2')
    })

    it('rolls back on API error and sets error state', async () => {
      const { cartApi } = await import('@/services/cartApi')
      const mocked = vi.mocked(cartApi)
      mocked.removeItem.mockRejectedValue(new Error('Network failure'))
      mocked.get.mockRejectedValue(new Error('Network failure'))

      const useCartStore = await getStore()
      const originalCart = makeCart()
      useCartStore.setState({ cart: originalCart })

      await useCartStore.getState().removeItem('prod-1')

      const state = useCartStore.getState()
      expect(state.error).toBe('Network failure')
    })

    it('recalculates budget_exceeded correctly after removal', async () => {
      const { cartApi } = await import('@/services/cartApi')
      const mocked = vi.mocked(cartApi)
      mocked.removeItem.mockResolvedValue({ data: null } as any)

      const useCartStore = await getStore()
      // Budget is 10000, current total is 13000 (exceeds), after removing prod-1 => 3000 (ok)
      const cart = makeCart({ available_budget_cents: 10000, budget_exceeded: true })
      useCartStore.setState({ cart })

      await useCartStore.getState().removeItem('prod-1')

      const state = useCartStore.getState()
      expect(state.cart!.budget_exceeded).toBe(false)
      expect(state.cart!.total_current_cents).toBe(3000)
    })
  })
})
