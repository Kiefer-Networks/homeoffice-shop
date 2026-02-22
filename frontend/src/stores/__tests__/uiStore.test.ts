import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useUiStore } from '../uiStore'

// Stub crypto.randomUUID for deterministic IDs
let uuidCounter = 0
const mockRandomUUID = vi.fn(() => `toast-${++uuidCounter}`)

describe('uiStore', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    uuidCounter = 0
    vi.stubGlobal('crypto', { randomUUID: mockRandomUUID })
    // Reset store state
    useUiStore.setState({ toasts: [], sidebarOpen: false })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  describe('addToast', () => {
    it('adds a toast with a generated id', () => {
      useUiStore.getState().addToast({ title: 'Item added' })

      const toasts = useUiStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0].id).toBe('toast-1')
      expect(toasts[0].title).toBe('Item added')
    })

    it('adds multiple toasts', () => {
      useUiStore.getState().addToast({ title: 'First' })
      useUiStore.getState().addToast({ title: 'Second' })

      const toasts = useUiStore.getState().toasts
      expect(toasts).toHaveLength(2)
      expect(toasts[0].title).toBe('First')
      expect(toasts[1].title).toBe('Second')
    })

    it('includes optional description and variant', () => {
      useUiStore.getState().addToast({
        title: 'Error',
        description: 'Something went wrong',
        variant: 'destructive',
      })

      const toast = useUiStore.getState().toasts[0]
      expect(toast.description).toBe('Something went wrong')
      expect(toast.variant).toBe('destructive')
    })

    it('auto-removes default toast after 5 seconds', () => {
      useUiStore.getState().addToast({ title: 'Temp' })
      expect(useUiStore.getState().toasts).toHaveLength(1)

      vi.advanceTimersByTime(4999)
      expect(useUiStore.getState().toasts).toHaveLength(1)

      vi.advanceTimersByTime(1)
      expect(useUiStore.getState().toasts).toHaveLength(0)
    })

    it('auto-removes destructive toast after 8 seconds', () => {
      useUiStore.getState().addToast({ title: 'Error', variant: 'destructive' })
      expect(useUiStore.getState().toasts).toHaveLength(1)

      vi.advanceTimersByTime(5000)
      expect(useUiStore.getState().toasts).toHaveLength(1)

      vi.advanceTimersByTime(3000)
      expect(useUiStore.getState().toasts).toHaveLength(0)
    })
  })

  describe('removeToast', () => {
    it('removes a specific toast by id', () => {
      useUiStore.getState().addToast({ title: 'Keep' })
      useUiStore.getState().addToast({ title: 'Remove' })

      useUiStore.getState().removeToast('toast-2')

      const toasts = useUiStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0].title).toBe('Keep')
    })

    it('does nothing when removing a non-existent id', () => {
      useUiStore.getState().addToast({ title: 'Stay' })
      useUiStore.getState().removeToast('nonexistent-id')

      expect(useUiStore.getState().toasts).toHaveLength(1)
    })
  })

  describe('setSidebarOpen', () => {
    it('sets sidebar open state', () => {
      useUiStore.getState().setSidebarOpen(true)
      expect(useUiStore.getState().sidebarOpen).toBe(true)

      useUiStore.getState().setSidebarOpen(false)
      expect(useUiStore.getState().sidebarOpen).toBe(false)
    })
  })
})
