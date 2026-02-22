import { useCallback } from 'react'
import { adminApi } from '@/services/adminApi'
import type { Order } from '@/types'

export function useRefreshOrder(orderId: string, onUpdate: (order: Order) => void) {
  return useCallback(async () => {
    const { data } = await adminApi.getOrder(orderId)
    onUpdate(data)
  }, [orderId, onUpdate])
}
