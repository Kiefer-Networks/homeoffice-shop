import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ShoppingBag, Users, Wallet } from 'lucide-react'
import { adminApi } from '@/services/adminApi'

export function DashboardPage() {
  const [stats, setStats] = useState({ orders: 0, pending: 0, users: 0, products: 0 })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      adminApi.listOrders({ per_page: 1 }),
      adminApi.listOrders({ status: 'pending', per_page: 1 }),
      adminApi.listUsers({ per_page: 1 }),
    ]).then(([allOrders, pendingOrders, users]) => {
      setStats({
        orders: allOrders.data.total,
        pending: pendingOrders.data.total,
        users: users.data.total,
        products: 0,
      })
    }).catch(() => {
      // Stats may fail to load if APIs are temporarily unavailable
    }).finally(() => setLoading(false))
  }, [])

  const cards = [
    { title: 'Total Orders', value: stats.orders, icon: ShoppingBag, color: 'text-blue-600' },
    { title: 'Pending Orders', value: stats.pending, icon: Wallet, color: 'text-yellow-600' },
    { title: 'Employees', value: stats.users, icon: Users, color: 'text-green-600' },
  ]

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Admin Dashboard</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {cards.map((card) => (
          <Card key={card.title}>
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
    </div>
  )
}
