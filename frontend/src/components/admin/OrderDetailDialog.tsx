import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { formatCents, formatDate } from '@/lib/utils'
import { useUiStore } from '@/stores/uiStore'
import { ExternalLink, Loader2 } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import { ORDER_STATUS_VARIANT } from '@/lib/constants'
import { InvoiceSection } from '@/components/admin/InvoiceSection'
import { OrderTrackingSection } from '@/components/admin/OrderTrackingSection'
import { OrderPurchaseUrlSection } from '@/components/admin/OrderPurchaseUrlSection'
import { OrderStatusSection } from '@/components/admin/OrderStatusSection'
import { useRefreshOrder } from '@/hooks/useRefreshOrder'
import { adminApi } from '@/services/adminApi'
import type { Order } from '@/types'

interface OrderDetailDialogProps {
  order: Order | null
  onClose: () => void
  onOrderUpdated: (order: Order) => void
}

export function OrderDetailDialog({ order, onClose, onOrderUpdated }: OrderDetailDialogProps) {
  const { addToast } = useUiStore()
  const [refreshing, setRefreshing] = useState(false)

  const refreshOrderBase = useRefreshOrder(order?.id ?? '', onOrderUpdated)

  const refreshOrder = async () => {
    setRefreshing(true)
    try {
      await refreshOrderBase()
    } catch { /* ignore */ }
    finally { setRefreshing(false) }
  }

  const handleItemCheck = async (orderId: string, itemId: string, checked: boolean) => {
    try {
      await adminApi.checkOrderItem(orderId, itemId, checked)
      await refreshOrder()
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const openAllLinks = (o: Order) => {
    o.items.forEach((item) => { window.open(item.external_url, '_blank', 'noopener,noreferrer') })
  }

  return (
    <Dialog open={!!order} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-2xl relative">
        {order && (
          <>
            {/* Refreshing overlay */}
            {refreshing && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-[hsl(var(--background)/0.5)] rounded-lg">
                <Loader2 className="h-6 w-6 animate-spin text-[hsl(var(--muted-foreground))]" />
              </div>
            )}
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
              <OrderPurchaseUrlSection order={order} onUpdate={onOrderUpdated} />
            )}

            {/* Tracking */}
            {(order.status === 'ordered' || order.status === 'delivered') && (
              <OrderTrackingSection order={order} onUpdate={onOrderUpdated} />
            )}

            {/* Invoices */}
            {order.status !== 'rejected' && order.status !== 'cancelled' && (
              <InvoiceSection order={order} onInvoiceChange={() => refreshOrder()} />
            )}

            {/* Actions bar */}
            {(order.status === 'pending' || order.status === 'ordered' || order.status === 'delivered' || order.status === 'return_requested') && (
              <OrderStatusSection order={order} onUpdate={onOrderUpdated} />
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
