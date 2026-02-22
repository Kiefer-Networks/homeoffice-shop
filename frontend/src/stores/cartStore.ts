import { create } from 'zustand'
import type { Cart } from '@/types'
import { cartApi } from '@/services/cartApi'
import { getErrorMessage } from '@/lib/error'
import { useUiStore } from '@/stores/uiStore'

interface CartState {
  cart: Cart | null
  isOpen: boolean
  isLoading: boolean
  error: string | null
  setOpen: (open: boolean) => void
  fetchCart: () => Promise<void>
  addItem: (productId: string, quantity?: number, variantAsin?: string) => Promise<void>
  updateItem: (productId: string, quantity: number) => Promise<void>
  removeItem: (productId: string) => Promise<void>
}

export const useCartStore = create<CartState>((set, get) => ({
  cart: null,
  isOpen: false,
  isLoading: false,
  error: null,
  setOpen: (isOpen) => set({ isOpen }),
  fetchCart: async () => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await cartApi.get()
      set({ cart: data })
    } catch (err) {
      set({ error: getErrorMessage(err) })
    } finally {
      set({ isLoading: false })
    }
  },
  addItem: async (productId, quantity = 1, variantAsin) => {
    set({ isLoading: true, error: null })
    try {
      await cartApi.addItem(productId, quantity, variantAsin)
      const { data } = await cartApi.get()
      set({ cart: data })
    } catch (err) {
      set({ error: getErrorMessage(err) })
    } finally {
      set({ isLoading: false })
    }
  },
  updateItem: async (productId, quantity) => {
    const prevCart = get().cart
    // Optimistic update
    if (prevCart) {
      if (quantity <= 0) {
        set({ cart: { ...prevCart, items: prevCart.items.filter(i => i.product_id !== productId) } })
      } else {
        set({
          cart: {
            ...prevCart,
            items: prevCart.items.map(i =>
              i.product_id === productId ? { ...i, quantity } : i
            ),
          },
        })
      }
    }
    try {
      if (quantity <= 0) {
        await cartApi.removeItem(productId)
      } else {
        await cartApi.updateItem(productId, quantity)
      }
    } catch (err) {
      // Rollback on error — re-fetch true server state instead of restoring stale prevCart
      set({ error: getErrorMessage(err) })
      useUiStore.getState().addToast({ title: 'Failed to update cart', description: getErrorMessage(err), variant: 'destructive' })
      try {
        const { data } = await cartApi.get()
        set({ cart: data })
      } catch {
        // keep current cart on refetch failure
      }
    }
  },
  removeItem: async (productId) => {
    const prevCart = get().cart
    // Optimistic: remove locally
    if (prevCart) {
      set({ cart: { ...prevCart, items: prevCart.items.filter(i => i.product_id !== productId) } })
    }
    try {
      await cartApi.removeItem(productId)
    } catch (err) {
      // Rollback on error — re-fetch true server state instead of restoring stale prevCart
      set({ error: getErrorMessage(err) })
      useUiStore.getState().addToast({ title: 'Failed to update cart', description: getErrorMessage(err), variant: 'destructive' })
      try {
        const { data } = await cartApi.get()
        set({ cart: data })
      } catch {
        // keep current cart on refetch failure
      }
    }
  },
}))
