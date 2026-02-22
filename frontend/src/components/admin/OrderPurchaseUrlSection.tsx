import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { Loader2, Link2 } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import { useRefreshOrder } from '@/hooks/useRefreshOrder'
import type { Order } from '@/types'

interface OrderPurchaseUrlSectionProps {
  order: Order
  onUpdate: (order: Order) => void
}

export function OrderPurchaseUrlSection({ order, onUpdate }: OrderPurchaseUrlSectionProps) {
  const [purchaseUrl, setPurchaseUrl] = useState(order.purchase_url || '')
  const [purchaseUrlSaving, setPurchaseUrlSaving] = useState(false)

  const { addToast } = useUiStore()

  useEffect(() => {
    setPurchaseUrl(order.purchase_url || '')
  }, [order])

  const refreshOrder = useRefreshOrder(order.id, onUpdate)

  const handleSavePurchaseUrl = async () => {
    setPurchaseUrlSaving(true)
    try {
      await adminApi.updatePurchaseUrl(order.id, purchaseUrl || null)
      await refreshOrder()
      addToast({ title: 'Purchase URL saved' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setPurchaseUrlSaving(false)
    }
  }

  return (
    <div>
      <label className="text-sm font-medium block mb-1">Purchase URL (internal)</label>
      <div className="flex gap-2">
        <Input
          value={purchaseUrl}
          onChange={(e) => setPurchaseUrl(e.target.value)}
          placeholder="Vendor order/purchase link..."
          className="flex-1"
        />
        {purchaseUrl && (
          <Button size="icon" variant="outline" asChild>
            <a href={purchaseUrl} target="_blank" rel="noopener noreferrer">
              <Link2 className="h-4 w-4" />
            </a>
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          onClick={handleSavePurchaseUrl}
          disabled={purchaseUrlSaving || purchaseUrl === (order.purchase_url || '')}
        >
          {purchaseUrlSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save'}
        </Button>
      </div>
    </div>
  )
}
