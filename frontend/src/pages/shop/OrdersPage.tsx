import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { orderApi } from '@/services/orderApi'
import { formatCents, formatDate } from '@/lib/utils'
import { ChevronRight, Package, AlertTriangle, CheckCircle2, XCircle, Clock, Truck, ExternalLink, MessageSquare } from 'lucide-react'
import { useUiStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { getErrorMessage } from '@/lib/error'
import type { Order } from '@/types'

const statusConfig: Record<string, { variant: 'default' | 'secondary' | 'success' | 'destructive' | 'warning'; icon: typeof Clock; label: string }> = {
  pending: { variant: 'warning', icon: Clock, label: 'Pending' },
  ordered: { variant: 'default', icon: Package, label: 'Ordered' },
  delivered: { variant: 'success', icon: CheckCircle2, label: 'Delivered' },
  rejected: { variant: 'destructive', icon: XCircle, label: 'Rejected' },
  cancelled: { variant: 'secondary', icon: AlertTriangle, label: 'Cancelled' },
}

export function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null)
  const [filter, setFilter] = useState<string>('')
  const [cancelOrder, setCancelOrder] = useState<Order | null>(null)
  const [cancelReason, setCancelReason] = useState('')
  const [cancelling, setCancelling] = useState(false)
  const { addToast } = useUiStore()

  const loadOrders = () => {
    orderApi.list({ per_page: 100 }).then(({ data }) => setOrders(data.items)).finally(() => setLoading(false))
  }

  useEffect(() => { loadOrders() }, [])

  const openOrderDetail = async (order: Order) => {
    setSelectedOrder(order)
    try {
      const { data } = await orderApi.get(order.id)
      setSelectedOrder(data)
    } catch { /* keep list data as fallback */ }
  }

  const filteredOrders = filter ? orders.filter(o => o.status === filter) : orders

  const handleCancel = async () => {
    if (!cancelOrder || !cancelReason.trim()) return
    setCancelling(true)
    try {
      await orderApi.cancel(cancelOrder.id, cancelReason)
      setCancelOrder(null)
      setCancelReason('')
      loadOrders()
      useAuthStore.getState().refreshBudget()
      addToast({ title: 'Order cancelled' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setCancelling(false)
    }
  }

  if (loading) return <div className="animate-pulse space-y-4">{[...Array(3)].map((_, i) => <div key={i} className="h-32 bg-gray-100 rounded-xl" />)}</div>

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">My Orders</h1>

      {/* Status Filter */}
      <div className="flex flex-wrap gap-2 mb-6">
        <Button size="sm" variant={filter === '' ? 'default' : 'outline'} onClick={() => setFilter('')}>
          All ({orders.length})
        </Button>
        {Object.entries(statusConfig).map(([key, cfg]) => {
          const count = orders.filter(o => o.status === key).length
          if (count === 0) return null
          return (
            <Button key={key} size="sm" variant={filter === key ? 'default' : 'outline'} onClick={() => setFilter(key)}>
              {cfg.label} ({count})
            </Button>
          )
        })}
      </div>

      {filteredOrders.length === 0 ? (
        <div className="text-center py-12 text-[hsl(var(--muted-foreground))]">
          <Package className="h-12 w-12 mx-auto mb-3 opacity-40" />
          <p className="text-lg">No orders found</p>
          {!filter && <p className="text-sm">You haven't placed any orders yet.</p>}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredOrders.map((order) => {
            const cfg = statusConfig[order.status] || statusConfig.pending
            const StatusIcon = cfg.icon
            return (
              <Card key={order.id} className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => openOrderDetail(order)}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <StatusIcon className="h-5 w-5 text-[hsl(var(--muted-foreground))]" />
                      <div>
                        <div className="font-medium">Order #{order.id.slice(0, 8)}</div>
                        <div className="text-sm text-[hsl(var(--muted-foreground))]">
                          {formatDate(order.created_at)} — {order.items.length} {order.items.length === 1 ? 'item' : 'items'}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <div className="font-bold">{formatCents(order.total_cents)}</div>
                        <Badge variant={cfg.variant}>{cfg.label}</Badge>
                      </div>
                      <ChevronRight className="h-4 w-4 text-[hsl(var(--muted-foreground))]" />
                    </div>
                  </div>
                  {order.tracking_number && (order.status === 'ordered' || order.status === 'delivered') && (
                    <div className="mt-3 flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))]">
                      <Truck className="h-4 w-4" />
                      <span>Tracking: {order.tracking_number}</span>
                    </div>
                  )}
                  {order.status === 'rejected' && order.admin_note && (
                    <div className="mt-3 p-2 rounded bg-red-50 border border-red-200 text-sm text-red-800">
                      <strong>Rejection reason:</strong> {order.admin_note}
                    </div>
                  )}
                  {order.status === 'cancelled' && order.cancellation_reason && (
                    <div className="mt-3 p-2 rounded bg-gray-50 border border-gray-200 text-sm text-gray-700">
                      <strong>Cancellation reason:</strong> {order.cancellation_reason}
                    </div>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {/* Order Detail Modal */}
      <Dialog open={!!selectedOrder} onOpenChange={() => setSelectedOrder(null)}>
        <DialogContent className="max-w-lg">
          {selectedOrder && (
            <>
              <DialogHeader>
                <DialogTitle>Order #{selectedOrder.id.slice(0, 8)}</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Badge variant={statusConfig[selectedOrder.status]?.variant || 'secondary'} className="text-sm px-3 py-1">
                    {statusConfig[selectedOrder.status]?.label || selectedOrder.status}
                  </Badge>
                  <span className="text-sm text-[hsl(var(--muted-foreground))]">{formatDate(selectedOrder.created_at)}</span>
                </div>

                {selectedOrder.reviewed_at && (
                  <div className="text-sm text-[hsl(var(--muted-foreground))]">
                    Reviewed on {formatDate(selectedOrder.reviewed_at)}
                  </div>
                )}

                {selectedOrder.admin_note && (
                  <div className={`p-3 rounded-lg text-sm ${
                    selectedOrder.status === 'rejected'
                      ? 'bg-red-50 border border-red-200 text-red-800'
                      : 'bg-[hsl(var(--muted))] text-[hsl(var(--foreground))]'
                  }`}>
                    <strong>{selectedOrder.status === 'rejected' ? 'Rejection reason:' : 'Note:'}</strong>
                    <p className="mt-1">{selectedOrder.admin_note}</p>
                  </div>
                )}

                {selectedOrder.cancellation_reason && (
                  <div className="p-3 rounded-lg text-sm bg-gray-50 border border-gray-200 text-gray-700">
                    <strong>Cancellation reason:</strong>
                    <p className="mt-1">{selectedOrder.cancellation_reason}</p>
                    {selectedOrder.cancelled_at && (
                      <p className="text-xs mt-1 text-[hsl(var(--muted-foreground))]">Cancelled on {formatDate(selectedOrder.cancelled_at)}</p>
                    )}
                  </div>
                )}

                <div>
                  <h4 className="font-medium mb-2">Items</h4>
                  <div className="space-y-2">
                    {selectedOrder.items.map((item) => (
                      <div key={item.id} className="flex justify-between items-center p-2 rounded bg-[hsl(var(--muted)/0.5)]">
                        <div>
                          <div className="text-sm font-medium">
                            {item.product_name || 'Product'}
                            {item.variant_value && (
                              <span className="text-[hsl(var(--muted-foreground))] font-normal"> — {item.variant_value}</span>
                            )}
                          </div>
                          <div className="text-xs text-[hsl(var(--muted-foreground))]">Qty: {item.quantity}</div>
                        </div>
                        <div className="text-sm font-medium">{formatCents(item.price_cents * item.quantity)}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex justify-between items-center border-t pt-3">
                  <span className="font-bold">Total</span>
                  <span className="text-lg font-bold">{formatCents(selectedOrder.total_cents)}</span>
                </div>

                {selectedOrder.delivery_note && (
                  <div className="p-3 rounded-lg bg-[hsl(var(--muted))] text-sm">
                    <strong>Delivery note:</strong> {selectedOrder.delivery_note}
                  </div>
                )}

                {(selectedOrder.status === 'ordered' || selectedOrder.status === 'delivered') &&
                  (selectedOrder.tracking_number || selectedOrder.tracking_url) && (
                  <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 text-sm space-y-1">
                    <div className="flex items-center gap-2 font-medium text-blue-900">
                      <Truck className="h-4 w-4" /> Tracking Info
                    </div>
                    {selectedOrder.tracking_number && (
                      <div className="text-blue-800">Number: <strong>{selectedOrder.tracking_number}</strong></div>
                    )}
                    {selectedOrder.tracking_url && (
                      <a
                        href={selectedOrder.tracking_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 underline"
                      >
                        Track Shipment <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                )}

                {selectedOrder.tracking_updates && selectedOrder.tracking_updates.length > 0 && (
                  <div>
                    <h4 className="font-medium text-sm mb-2 flex items-center gap-1">
                      <MessageSquare className="h-3 w-3" /> Tracking Updates
                    </h4>
                    <div className="space-y-2">
                      {selectedOrder.tracking_updates.map((update) => (
                        <div key={update.id} className="text-sm p-2 rounded bg-[hsl(var(--muted)/0.5)] border">
                          <div className="text-[hsl(var(--muted-foreground))] text-xs mb-1">
                            {formatDate(update.created_at)}
                          </div>
                          <div>{update.comment}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {selectedOrder.status === 'ordered' && (
                  <div className="space-y-1">
                    <h4 className="font-medium text-sm">Order status</h4>
                    {selectedOrder.items.map((item) => (
                      <div key={item.id} className="flex items-center gap-2 text-sm">
                        {item.vendor_ordered ? (
                          <CheckCircle2 className="h-4 w-4 text-green-500" />
                        ) : (
                          <Clock className="h-4 w-4 text-yellow-500" />
                        )}
                        <span>
                          {item.product_name}{item.variant_value ? ` — ${item.variant_value}` : ''}: {item.vendor_ordered ? 'Ordered from vendor' : 'Pending order'}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {selectedOrder.status === 'pending' && (
                  <Button
                    variant="destructive"
                    className="w-full"
                    onClick={() => {
                      setCancelOrder(selectedOrder)
                      setSelectedOrder(null)
                    }}
                  >
                    Cancel Order
                  </Button>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Cancel Order Dialog */}
      <Dialog open={!!cancelOrder} onOpenChange={() => { setCancelOrder(null); setCancelReason('') }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel Order #{cancelOrder?.id.slice(0, 8)}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              Please provide a reason for cancelling this order. Your budget will be released.
            </p>
            <textarea
              placeholder="Cancellation reason *"
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              className="w-full rounded-md border px-3 py-2 text-sm min-h-[80px]"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setCancelOrder(null); setCancelReason('') }}>Keep Order</Button>
            <Button variant="destructive" onClick={handleCancel} disabled={cancelling || !cancelReason.trim()}>
              {cancelling ? 'Cancelling...' : 'Cancel Order'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
