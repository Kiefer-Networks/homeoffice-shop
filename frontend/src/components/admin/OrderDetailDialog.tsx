import { useState, useEffect } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { formatCents, formatDate } from '@/lib/utils'
import { useUiStore } from '@/stores/uiStore'
import { ExternalLink, Loader2, Link2 } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import { ORDER_STATUS_VARIANT } from '@/lib/constants'
import { InvoiceSection } from '@/components/admin/InvoiceSection'
import { HiBobSyncSection } from '@/components/admin/HiBobSyncSection'
import type { Order } from '@/types'

type PendingAction = 'ordered' | 'rejected' | 'delivered' | 'cancelled' | null

interface OrderDetailDialogProps {
  order: Order | null
  onClose: () => void
  onOrderUpdated: (order: Order) => void
}

export function OrderDetailDialog({ order, onClose, onOrderUpdated }: OrderDetailDialogProps) {
  const [pendingAction, setPendingAction] = useState<PendingAction>(null)
  const [adminNote, setAdminNote] = useState('')
  const [expectedDelivery, setExpectedDelivery] = useState('')
  const [statusLoading, setStatusLoading] = useState(false)

  const [purchaseUrl, setPurchaseUrl] = useState('')
  const [purchaseUrlSaving, setPurchaseUrlSaving] = useState(false)

  const { addToast } = useUiStore()

  useEffect(() => {
    if (order) {
      setPurchaseUrl(order.purchase_url || '')
      setPendingAction(null)
      setAdminNote('')
      setExpectedDelivery('')
    }
  }, [order])

  const refreshOrder = async (orderId: string) => {
    try {
      const { data } = await adminApi.getOrder(orderId)
      onOrderUpdated(data)
    } catch { /* ignore */ }
  }

  const startAction = (action: PendingAction) => {
    setPendingAction(action)
    setAdminNote('')
    setExpectedDelivery('')
  }

  const handleStatusConfirm = async () => {
    if (!order || !pendingAction) return
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
      await refreshOrder(order.id)
      addToast({ title: 'Status updated' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setStatusLoading(false)
    }
  }

  const handleItemCheck = async (orderId: string, itemId: string, checked: boolean) => {
    try {
      await adminApi.checkOrderItem(orderId, itemId, checked)
      await refreshOrder(orderId)
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const handleSavePurchaseUrl = async () => {
    if (!order) return
    setPurchaseUrlSaving(true)
    try {
      await adminApi.updatePurchaseUrl(order.id, purchaseUrl || null)
      await refreshOrder(order.id)
      addToast({ title: 'Purchase URL saved' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setPurchaseUrlSaving(false)
    }
  }

  const openAllLinks = (o: Order) => {
    o.items.forEach((item) => { window.open(item.external_url, '_blank', 'noopener,noreferrer') })
  }

  const actionButtons: Record<string, { label: string; action: PendingAction; variant: 'default' | 'destructive' }[]> = {
    pending: [
      { label: 'Approve', action: 'ordered', variant: 'default' },
      { label: 'Reject', action: 'rejected', variant: 'destructive' },
    ],
    ordered: [
      { label: 'Mark Delivered', action: 'delivered', variant: 'default' },
      { label: 'Cancel Order', action: 'cancelled', variant: 'destructive' },
    ],
  }

  return (
    <Dialog open={!!order} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        {order && (
          <>
            {/* Header */}
            <DialogHeader>
              <DialogTitle className="flex items-center gap-3">
                <span className="font-mono">#{order.id.slice(0, 8)}</span>
                <Badge variant={ORDER_STATUS_VARIANT[order.status]}>{order.status}</Badge>
                <span className="text-sm font-normal text-[hsl(var(--muted-foreground))]">{formatDate(order.created_at)}</span>
              </DialogTitle>
            </DialogHeader>

            {/* User card */}
            <div className="border rounded-lg p-3 bg-[hsl(var(--muted)/0.3)]">
              <div className="font-medium">{order.user_display_name}</div>
              <div className="text-sm text-[hsl(var(--muted-foreground))]">{order.user_email}</div>
            </div>

            {/* Items table */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-medium">Items</h3>
                <Button size="sm" variant="outline" onClick={() => openAllLinks(order)}>
                  <ExternalLink className="h-3 w-3 mr-1" /> Open All Links
                </Button>
              </div>
              <div className="border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-[hsl(var(--muted))]">
                      <th className="text-left px-3 py-2 font-medium w-8"></th>
                      <th className="text-left px-3 py-2 font-medium">Product</th>
                      <th className="text-center px-3 py-2 font-medium">Qty</th>
                      <th className="text-right px-3 py-2 font-medium">Price</th>
                      <th className="w-8"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {order.items.map((item) => (
                      <tr key={item.id} className="border-b last:border-b-0">
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            checked={item.vendor_ordered}
                            onChange={(e) => handleItemCheck(order.id, item.id, e.target.checked)}
                            disabled={order.status === 'rejected' || order.status === 'cancelled'}
                            className="rounded"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <span className={item.vendor_ordered ? 'line-through text-gray-400' : ''}>
                            {item.product_name || 'Product'}
                          </span>
                          {item.variant_value && (
                            <span className="ml-1 text-xs text-[hsl(var(--muted-foreground))]">({item.variant_value})</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-center">{item.quantity}</td>
                        <td className="px-3 py-2 text-right">{formatCents(item.price_cents * item.quantity)}</td>
                        <td className="px-3 py-2">
                          <a href={item.external_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800">
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t bg-[hsl(var(--muted)/0.3)]">
                      <td colSpan={3} className="px-3 py-2 font-medium text-right">Total</td>
                      <td className="px-3 py-2 font-bold text-right">{formatCents(order.total_cents)}</td>
                      <td></td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>

            {/* Info section */}
            {order.delivery_note && (
              <div className="text-sm">
                <span className="font-medium">Delivery note:</span>{' '}
                <span className="text-[hsl(var(--muted-foreground))]">{order.delivery_note}</span>
              </div>
            )}
            {order.expected_delivery && (
              <div className="text-sm">
                <span className="font-medium">Expected delivery:</span>{' '}
                <span className="text-[hsl(var(--muted-foreground))]">{formatDate(order.expected_delivery)}</span>
              </div>
            )}
            {order.admin_note && (
              <div className="text-sm p-2 rounded bg-amber-50 border border-amber-200">
                <span className="font-medium">{order.status === 'rejected' ? 'Rejection reason' : 'Admin note'}:</span>{' '}
                {order.admin_note}
              </div>
            )}
            {order.cancellation_reason && (
              <div className="text-sm p-2 rounded bg-gray-50 border border-gray-200">
                <span className="font-medium">Cancellation reason:</span>{' '}
                {order.cancellation_reason}
                {order.cancelled_at && <span className="text-xs ml-2 text-[hsl(var(--muted-foreground))]">({formatDate(order.cancelled_at)})</span>}
              </div>
            )}

            {/* Purchase URL */}
            {order.status !== 'rejected' && order.status !== 'cancelled' && (
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
            )}

            {/* Invoices */}
            {order.status !== 'rejected' && order.status !== 'cancelled' && (
              <InvoiceSection order={order} onInvoiceChange={() => refreshOrder(order.id)} />
            )}

            {/* Actions bar */}
            {(actionButtons[order.status] || order.status === 'delivered') && (
              <div className="pt-2 border-t">
                {pendingAction ? (
                  <div className="space-y-3">
                    <div className="text-sm font-medium">
                      {pendingAction === 'ordered' && 'Approve Order'}
                      {pendingAction === 'rejected' && 'Reject Order'}
                      {pendingAction === 'delivered' && 'Mark as Delivered'}
                      {pendingAction === 'cancelled' && 'Cancel Order'}
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
                    {actionButtons[order.status]?.map((btn) => (
                      <Button key={btn.action} variant={btn.variant} onClick={() => startAction(btn.action)}>
                        {btn.label}
                      </Button>
                    ))}
                  </div>
                )}

                {/* HiBob sync */}
                {order.status === 'delivered' && !pendingAction && (
                  <HiBobSyncSection order={order} onSyncChange={() => refreshOrder(order.id)} />
                )}
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
