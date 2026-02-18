import { create } from 'zustand'
import type { Cart } from '@/types'
import { cartApi } from '@/services/cartApi'

interface CartState {
  cart: Cart | null
  isOpen: boolean
  isLoading: boolean
  setCart: (cart: Cart | null) => void
  setOpen: (open: boolean) => void
  setLoading: (loading: boolean) => void
  fetchCart: () => Promise<void>
  addItem: (productId: string, quantity?: number, variantAsin?: string) => Promise<void>
  updateItem: (productId: string, quantity: number) => Promise<void>
  removeItem: (productId: string) => Promise<void>
  clearCart: () => Promise<void>
}

export const useCartStore = create<CartState>((set) => ({
  cart: null,
  isOpen: false,
  isLoading: false,
  setCart: (cart) => set({ cart }),
  setOpen: (isOpen) => set({ isOpen }),
  setLoading: (isLoading) => set({ isLoading }),
  fetchCart: async () => {
    set({ isLoading: true })
    try {
      const { data } = await cartApi.get()
      set({ cart: data })
    } finally {
      set({ isLoading: false })
    }
  },
  addItem: async (productId, quantity = 1, variantAsin) => {
    await cartApi.addItem(productId, quantity, variantAsin)
    const { data } = await cartApi.get()
    set({ cart: data })
  },
  updateItem: async (productId, quantity) => {
    if (quantity <= 0) {
      await cartApi.removeItem(productId)
    } else {
      await cartApi.updateItem(productId, quantity)
    }
    const { data } = await cartApi.get()
    set({ cart: data })
  },
  removeItem: async (productId) => {
    await cartApi.removeItem(productId)
    const { data } = await cartApi.get()
    set({ cart: data })
  },
  clearCart: async () => {
    await cartApi.clear()
    set({ cart: null })
  },
}))
