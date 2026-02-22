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
    // Optimistic update — apply locally before the API call
    if (prevCart) {
      const newItems = quantity <= 0
        ? prevCart.items.filter(i => i.product_id !== productId)
        : prevCart.items.map(i =>
            i.product_id === productId ? { ...i, quantity } : i
          )
      const newTotal = newItems.reduce((sum, i) => sum + i.current_price_cents * i.quantity, 0)
      const budgetExceeded = newTotal > prevCart.available_budget_cents
      set({
        cart: {
          ...prevCart,
          items: newItems,
          total_current_cents: newTotal,
          total_at_add_cents: newItems.reduce((sum, i) => sum + i.price_at_add_cents * i.quantity, 0),
          budget_exceeded: budgetExceeded,
          has_unavailable_items: newItems.some(i => !i.product_active),
          has_price_changes: newItems.some(i => i.price_changed),
        },
      })
    }
    try {
      if (quantity <= 0) {
        await cartApi.removeItem(productId)
      } else {
        await cartApi.updateItem(productId, quantity)
      }
    } catch (err) {
      // Rollback on error — restore backup then re-fetch true server state
      set({ cart: prevCart, error: getErrorMessage(err) })
      useUiStore.getState().addToast({ title: 'Failed to update cart', description: getErrorMessage(err), variant: 'destructive' })
      try {
        const { data } = await cartApi.get()
        set({ cart: data })
      } catch {
        // keep restored cart on refetch failure
      }
    }
  },
  removeItem: async (productId) => {
    const prevCart = get().cart
    // Optimistic: remove locally with recalculated totals
    if (prevCart) {
      const newItems = prevCart.items.filter(i => i.product_id !== productId)
      const newTotal = newItems.reduce((sum, i) => sum + i.current_price_cents * i.quantity, 0)
      const budgetExceeded = newTotal > prevCart.available_budget_cents
      set({
        cart: {
          ...prevCart,
          items: newItems,
          total_current_cents: newTotal,
          total_at_add_cents: newItems.reduce((sum, i) => sum + i.price_at_add_cents * i.quantity, 0),
          budget_exceeded: budgetExceeded,
          has_unavailable_items: newItems.some(i => !i.product_active),
          has_price_changes: newItems.some(i => i.price_changed),
        },
      })
    }
    try {
      await cartApi.removeItem(productId)
    } catch (err) {
      // Rollback on error — restore backup then re-fetch true server state
      set({ cart: prevCart, error: getErrorMessage(err) })
      useUiStore.getState().addToast({ title: 'Failed to update cart', description: getErrorMessage(err), variant: 'destructive' })
      try {
        const { data } = await cartApi.get()
        set({ cart: data })
      } catch {
        // keep restored cart on refetch failure
      }
    }
  },
}))
