import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { Loader2 } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import { HiBobSyncSection } from '@/components/admin/HiBobSyncSection'
import type { Order } from '@/types'

type PendingAction = 'ordered' | 'rejected' | 'delivered' | 'cancelled' | 'returned' | null

const ACTION_BUTTONS: Record<string, { label: string; action: PendingAction; variant: 'default' | 'destructive' }[]> = {
  pending: [
    { label: 'Approve', action: 'ordered', variant: 'default' },
    { label: 'Reject', action: 'rejected', variant: 'destructive' },
  ],
  ordered: [
    { label: 'Mark Delivered', action: 'delivered', variant: 'default' },
    { label: 'Cancel Order', action: 'cancelled', variant: 'destructive' },
  ],
  return_requested: [
    { label: 'Approve Return', action: 'returned', variant: 'default' },
    { label: 'Reject Return', action: 'delivered', variant: 'destructive' },
  ],
}

interface OrderStatusSectionProps {
  order: Order
  onUpdate: (order: Order) => void
}

export function OrderStatusSection({ order, onUpdate }: OrderStatusSectionProps) {
  const [pendingAction, setPendingAction] = useState<PendingAction>(null)
  const [adminNote, setAdminNote] = useState('')
  const [expectedDelivery, setExpectedDelivery] = useState('')
  const [statusLoading, setStatusLoading] = useState(false)

  const { addToast } = useUiStore()

  const refreshOrder = async () => {
    try {
      const { data } = await adminApi.getOrder(order.id)
      onUpdate(data)
    } catch { /* ignore */ }
  }

  const startAction = (action: PendingAction) => {
    setPendingAction(action)
    setAdminNote('')
    setExpectedDelivery('')
  }

  const handleStatusConfirm = async () => {
    if (!pendingAction) return
    setStatusLoading(true)
    try {
      const payload: Record<string, string | undefined> = {
        status: pendingAction,
        admin_note: adminNote || undefined,
      }
      if (pendingAction === 'ordered' && expectedDelivery) {
        payload.expected_delivery = expectedDelivery
      }
      await adminApi.updateOrderStatus(order.id, payload as { status: string; admin_note?: string; expected_delivery?: string })
      setPendingAction(null)
      await refreshOrder()
      addToast({ title: 'Status updated' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setStatusLoading(false)
    }
  }

  return (
    <div className="pt-2 border-t">
      {pendingAction ? (
        <div className="space-y-3">
          <div className="text-sm font-medium">
            {pendingAction === 'ordered' && 'Approve Order'}
            {pendingAction === 'rejected' && 'Reject Order'}
            {pendingAction === 'delivered' && (order.status === 'return_requested' ? 'Reject Return' : 'Mark as Delivered')}
            {pendingAction === 'cancelled' && 'Cancel Order'}
            {pendingAction === 'returned' && 'Approve Return'}
          </div>

          {pendingAction === 'ordered' && (
            <div>
              <label className="text-sm font-medium">Expected delivery (optional)</label>
              <Input
                type="date"
                value={expectedDelivery}
                onChange={(e) => setExpectedDelivery(e.target.value)}
                min={new Date().toISOString().split('T')[0]}
                className="mt-1"
              />
            </div>
          )}

          <div>
            <label className="text-sm font-medium">
              {pendingAction === 'rejected' ? 'Reason (required)' : 'Note (optional)'}
            </label>
            <Input
              value={adminNote}
              onChange={(e) => setAdminNote(e.target.value)}
              placeholder={pendingAction === 'rejected' ? 'Enter reason...' : 'Enter note...'}
              className="mt-1"
            />
          </div>

          <div className="flex gap-2">
            <Button
              onClick={handleStatusConfirm}
              disabled={statusLoading || (pendingAction === 'rejected' && !adminNote)}
            >
              {statusLoading ? <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Updating...</> : 'Confirm'}
            </Button>
            <Button variant="outline" onClick={() => setPendingAction(null)} disabled={statusLoading}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {ACTION_BUTTONS[order.status]?.map((btn) => (
            <Button key={btn.action} variant={btn.variant} onClick={() => startAction(btn.action)}>
              {btn.label}
            </Button>
          ))}
        </div>
      )}

      {/* HiBob sync */}
      {order.status === 'delivered' && !pendingAction && (
        <HiBobSyncSection order={order} onSyncChange={() => refreshOrder()} />
      )}
    </div>
  )
}
