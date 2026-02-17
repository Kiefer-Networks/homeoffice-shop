import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { orderApi } from '@/services/orderApi'
import { formatCents, formatDate } from '@/lib/utils'
import { ChevronRight, Package, AlertTriangle, CheckCircle2, XCircle, Clock, Truck } from 'lucide-react'
import type { Order } from '@/types'

const statusConfig: Record<string, { variant: 'default' | 'secondary' | 'success' | 'destructive' | 'warning'; icon: typeof Clock; label: string }> = {
  pending: { variant: 'warning', icon: Clock, label: 'Ausstehend' },
  ordered: { variant: 'default', icon: Package, label: 'Bestellt' },
  delivered: { variant: 'success', icon: CheckCircle2, label: 'Geliefert' },
  rejected: { variant: 'destructive', icon: XCircle, label: 'Abgelehnt' },
  cancelled: { variant: 'secondary', icon: AlertTriangle, label: 'Storniert' },
}

export function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null)
  const [filter, setFilter] = useState<string>('')

  useEffect(() => {
    orderApi.list({ per_page: 100 }).then(({ data }) => setOrders(data.items)).finally(() => setLoading(false))
  }, [])

  const filteredOrders = filter ? orders.filter(o => o.status === filter) : orders

  if (loading) return <div className="animate-pulse space-y-4">{[...Array(3)].map((_, i) => <div key={i} className="h-32 bg-gray-100 rounded-xl" />)}</div>

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Meine Bestellungen</h1>

      {/* Status Filter */}
      <div className="flex flex-wrap gap-2 mb-6">
        <Button size="sm" variant={filter === '' ? 'default' : 'outline'} onClick={() => setFilter('')}>
          Alle ({orders.length})
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
          <p className="text-lg">Keine Bestellungen gefunden</p>
          {!filter && <p className="text-sm">Du hast noch keine Bestellungen aufgegeben.</p>}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredOrders.map((order) => {
            const cfg = statusConfig[order.status] || statusConfig.pending
            const StatusIcon = cfg.icon
            return (
              <Card key={order.id} className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setSelectedOrder(order)}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <StatusIcon className="h-5 w-5 text-[hsl(var(--muted-foreground))]" />
                      <div>
                        <div className="font-medium">Bestellung #{order.id.slice(0, 8)}</div>
                        <div className="text-sm text-[hsl(var(--muted-foreground))]">
                          {formatDate(order.created_at)} — {order.items.length} {order.items.length === 1 ? 'Artikel' : 'Artikel'}
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
                  {order.status === 'rejected' && order.admin_note && (
                    <div className="mt-3 p-2 rounded bg-red-50 border border-red-200 text-sm text-red-800">
                      <strong>Ablehnungsgrund:</strong> {order.admin_note}
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
                <DialogTitle>Bestellung #{selectedOrder.id.slice(0, 8)}</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                {/* Status */}
                <div className="flex items-center justify-between">
                  <Badge variant={statusConfig[selectedOrder.status]?.variant || 'secondary'} className="text-sm px-3 py-1">
                    {statusConfig[selectedOrder.status]?.label || selectedOrder.status}
                  </Badge>
                  <span className="text-sm text-[hsl(var(--muted-foreground))]">{formatDate(selectedOrder.created_at)}</span>
                </div>

                {/* Status Timeline */}
                {selectedOrder.reviewed_at && (
                  <div className="text-sm text-[hsl(var(--muted-foreground))]">
                    Bearbeitet am {formatDate(selectedOrder.reviewed_at)}
                  </div>
                )}

                {/* Rejection/Admin Note */}
                {selectedOrder.admin_note && (
                  <div className={`p-3 rounded-lg text-sm ${
                    selectedOrder.status === 'rejected'
                      ? 'bg-red-50 border border-red-200 text-red-800'
                      : 'bg-[hsl(var(--muted))] text-[hsl(var(--foreground))]'
                  }`}>
                    <strong>{selectedOrder.status === 'rejected' ? 'Ablehnungsgrund:' : 'Hinweis:'}</strong>
                    <p className="mt-1">{selectedOrder.admin_note}</p>
                  </div>
                )}

                {/* Items */}
                <div>
                  <h4 className="font-medium mb-2">Artikel</h4>
                  <div className="space-y-2">
                    {selectedOrder.items.map((item) => (
                      <div key={item.id} className="flex justify-between items-center p-2 rounded bg-[hsl(var(--muted)/0.5)]">
                        <div>
                          <div className="text-sm font-medium">{item.product_name || 'Produkt'}</div>
                          <div className="text-xs text-[hsl(var(--muted-foreground))]">Menge: {item.quantity}</div>
                        </div>
                        <div className="text-sm font-medium">{formatCents(item.price_cents * item.quantity)}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Total */}
                <div className="flex justify-between items-center border-t pt-3">
                  <span className="font-bold">Gesamt</span>
                  <span className="text-lg font-bold">{formatCents(selectedOrder.total_cents)}</span>
                </div>

                {/* Delivery Note */}
                {selectedOrder.delivery_note && (
                  <div className="p-3 rounded-lg bg-[hsl(var(--muted))] text-sm">
                    <strong>Lieferhinweis:</strong> {selectedOrder.delivery_note}
                  </div>
                )}

                {/* Vendor Ordered Status */}
                {selectedOrder.status === 'ordered' && (
                  <div className="space-y-1">
                    <h4 className="font-medium text-sm">Bestellstatus</h4>
                    {selectedOrder.items.map((item) => (
                      <div key={item.id} className="flex items-center gap-2 text-sm">
                        {item.vendor_ordered ? (
                          <CheckCircle2 className="h-4 w-4 text-green-500" />
                        ) : (
                          <Clock className="h-4 w-4 text-yellow-500" />
                        )}
                        <span>{item.product_name}: {item.vendor_ordered ? 'Beim Händler bestellt' : 'Wird bestellt'}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
