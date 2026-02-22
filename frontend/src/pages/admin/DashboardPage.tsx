import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ShoppingBag, Users, Wallet, Package, Truck, Box, ArrowRight } from 'lucide-react'
import { adminApi } from '@/services/adminApi'
import { productApi } from '@/services/productApi'
import { formatCents, formatDate } from '@/lib/utils'
import { ORDER_STATUS_VARIANT } from '@/lib/constants'
import type { Order } from '@/types'

export function DashboardPage() {
  const [stats, setStats] = useState({
    orders: 0, pending: 0, ordered: 0, delivered: 0, users: 0, products: 0,
  })
  const [recentOrders, setRecentOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([
      adminApi.listOrders({ per_page: 1 }),
      adminApi.listOrders({ status: 'pending', per_page: 1 }),
      adminApi.listOrders({ status: 'ordered', per_page: 1 }),
      adminApi.listOrders({ status: 'delivered', per_page: 1 }),
      adminApi.listUsers({ per_page: 1 }),
      productApi.search(new URLSearchParams({ per_page: '1' })),
      adminApi.listOrders({ per_page: 5, sort: 'newest' }),
    ]).then(([allOrders, pendingOrders, orderedOrders, deliveredOrders, users, products, recent]) => {
      setStats({
        orders: allOrders.data.total,
        pending: pendingOrders.data.total,
        ordered: orderedOrders.data.total,
        delivered: deliveredOrders.data.total,
        users: users.data.total,
        products: products.data.total,
      })
      setRecentOrders(recent.data.items)
    }).catch(() => {
      // Stats may fail to load if APIs are temporarily unavailable
    }).finally(() => setLoading(false))
  }, [])

  const cards = [
    { title: 'Total Orders', value: stats.orders, icon: ShoppingBag, color: 'text-blue-600', link: '/admin/orders' },
    { title: 'Pending', value: stats.pending, icon: Wallet, color: 'text-yellow-600', link: '/admin/orders' },
    { title: 'Ordered', value: stats.ordered, icon: Truck, color: 'text-blue-500', link: '/admin/orders' },
    { title: 'Delivered', value: stats.delivered, icon: Package, color: 'text-green-600', link: '/admin/orders' },
    { title: 'Employees', value: stats.users, icon: Users, color: 'text-purple-600', link: '/admin/employees' },
    { title: 'Products', value: stats.products, icon: Box, color: 'text-gray-600', link: '/admin/products' },
  ]

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Admin Dashboard</h1>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        {cards.map((card) => (
          <Card
            key={card.title}
            className="cursor-pointer hover:shadow-md transition-shadow"
            onClick={() => navigate(card.link)}
          >
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-[hsl(var(--muted-foreground))]">{card.title}</CardTitle>
              <card.icon className={`h-5 w-5 ${card.color}`} />
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="h-9 w-16 bg-gray-100 rounded animate-pulse" />
              ) : (
                <div className="text-3xl font-bold">{card.value}</div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Recent Orders */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">Recent Orders</CardTitle>
          <Button variant="ghost" size="sm" onClick={() => navigate('/admin/orders')}>
            View All <ArrowRight className="h-4 w-4 ml-1" />
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-4 space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
              ))}
            </div>
          ) : recentOrders.length === 0 ? (
            <div className="p-8 text-center text-[hsl(var(--muted-foreground))]">No orders yet.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                    <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Order</th>
                    <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">User</th>
                    <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Items</th>
                    <th className="text-right px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Total</th>
                    <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Status</th>
                    <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {recentOrders.map((order) => (
                    <tr
                      key={order.id}
                      className="border-b border-[hsl(var(--border))] last:border-b-0 hover:bg-[hsl(var(--muted)/0.5)] cursor-pointer"
                      onClick={() => navigate('/admin/orders')}
                    >
                      <td className="px-4 py-3 font-mono font-medium">#{order.id.slice(0, 8)}</td>
                      <td className="px-4 py-3">{order.user_display_name || '—'}</td>
                      <td className="px-4 py-3">{order.items.length}</td>
                      <td className="px-4 py-3 text-right font-medium">{formatCents(order.total_cents)}</td>
                      <td className="px-4 py-3">
                        <Badge variant={ORDER_STATUS_VARIANT[order.status]}>{order.status}</Badge>
                      </td>
                      <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">{formatDate(order.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
