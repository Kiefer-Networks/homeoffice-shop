import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { orderApi } from '@/services/orderApi'
import { formatCents, formatDate } from '@/lib/utils'
import type { Order } from '@/types'

const statusVariant: Record<string, 'default' | 'secondary' | 'success' | 'destructive' | 'warning'> = {
  pending: 'warning',
  ordered: 'default',
  delivered: 'success',
  rejected: 'destructive',
  cancelled: 'secondary',
}

export function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    orderApi.list().then(({ data }) => setOrders(data.items)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="animate-pulse space-y-4">{[...Array(3)].map((_, i) => <div key={i} className="h-32 bg-gray-100 rounded-xl" />)}</div>

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">My Orders</h1>
      {orders.length === 0 ? (
        <p className="text-[hsl(var(--muted-foreground))]">You haven't placed any orders yet.</p>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => (
            <Card key={order.id}>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div>
                  <CardTitle className="text-base">Order #{order.id.slice(0, 8)}</CardTitle>
                  <p className="text-sm text-[hsl(var(--muted-foreground))]">{formatDate(order.created_at)}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={statusVariant[order.status] || 'secondary'}>
                    {order.status}
                  </Badge>
                  <span className="font-bold">{formatCents(order.total_cents)}</span>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  {order.items.map((item) => (
                    <div key={item.id} className="flex justify-between text-sm">
                      <span>{item.product_name || 'Product'} x{item.quantity}</span>
                      <span>{formatCents(item.price_cents * item.quantity)}</span>
                    </div>
                  ))}
                </div>
                {order.admin_note && (
                  <p className="text-sm mt-3 p-2 bg-gray-50 rounded"><strong>Note:</strong> {order.admin_note}</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
