import { useEffect, useState, useCallback } from 'react'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Pagination } from '@/components/ui/Pagination'
import { adminApi } from '@/services/adminApi'
import { formatCents, formatDate } from '@/lib/utils'
import { ORDER_STATUS_VARIANT, DEFAULT_PAGE_SIZE, SEARCH_DEBOUNCE_MS } from '@/lib/constants'
import { useUiStore } from '@/stores/uiStore'
import { Search, FileText, Link2, Download } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import { SortHeader } from '@/components/ui/SortHeader'
import { OrderDetailDialog } from '@/components/admin/OrderDetailDialog'
import type { Order } from '@/types'

const STATUS_FILTERS = ['', 'pending', 'ordered', 'delivered', 'rejected', 'cancelled'] as const

type SortKey = 'newest' | 'oldest' | 'total_asc' | 'total_desc'

export function AdminOrdersPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [sort, setSort] = useState<SortKey>('newest')
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, SEARCH_DEBOUNCE_MS)
  const [selected, setSelected] = useState<Order | null>(null)

  const { addToast } = useUiStore()

  const loadOrders = useCallback(() => {
    setLoading(true)
    const params: Record<string, string | number> = { page, per_page: DEFAULT_PAGE_SIZE, sort }
    if (statusFilter) params.status = statusFilter
    if (debouncedSearch) params.q = debouncedSearch
    adminApi.listOrders(params)
      .then(({ data }) => { setOrders(data.items); setTotal(data.total) })
      .catch((err: unknown) => addToast({ title: 'Error loading orders', description: getErrorMessage(err), variant: 'destructive' }))
      .finally(() => setLoading(false))
  }, [page, statusFilter, sort, debouncedSearch])

  useEffect(() => { loadOrders() }, [loadOrders])
  useEffect(() => { setPage(1) }, [debouncedSearch, statusFilter, sort])

  const totalPages = Math.max(1, Math.ceil(total / DEFAULT_PAGE_SIZE))

  const handleOrderUpdated = (updatedOrder: Order) => {
    setSelected(updatedOrder)
    setOrders(prev => prev.map(o => o.id === updatedOrder.id ? updatedOrder : o))
  }

  const handleExport = () => {
    const params: Record<string, string> = {}
    if (statusFilter) params.status = statusFilter
    if (debouncedSearch) params.q = debouncedSearch
    window.open(adminApi.exportOrdersCsvUrl(params), '_blank')
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Orders ({total})</h1>
        <Button variant="outline" size="sm" onClick={handleExport}>
          <Download className="h-4 w-4 mr-1" /> Export CSV
        </Button>
      </div>

      {/* Search */}
      <div className="mb-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input placeholder="Search by name, email, order ID..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10 max-w-sm" />
        </div>
      </div>

      {/* Status filter */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {STATUS_FILTERS.map((s) => (
          <Button key={s} size="sm" variant={statusFilter === s ? 'default' : 'outline'}
            onClick={() => { setStatusFilter(s); setPage(1) }}>
            {s || 'All'}
          </Button>
        ))}
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Order</th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">User</th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Items</th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
                    <SortHeader label="Total" ascKey="total_asc" descKey="total_desc" currentSort={sort} onSort={setSort} />
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Status</th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
                    <SortHeader label="Date" ascKey="oldest" descKey="newest" currentSort={sort} onSort={setSort} />
                  </th>
                </tr>
              </thead>
              <tbody>
                {loading && orders.length === 0 ? (
                  [...Array(5)].map((_, i) => (
                    <tr key={i} className="border-b border-[hsl(var(--border))]">
                      <td colSpan={6} className="px-4 py-4"><div className="h-5 bg-gray-100 rounded animate-pulse" /></td>
                    </tr>
                  ))
                ) : orders.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">No orders found.</td>
                  </tr>
                ) : orders.map((order) => (
                  <tr
                    key={order.id}
                    className="border-b border-[hsl(var(--border))] hover:bg-[hsl(var(--muted)/0.5)] cursor-pointer"
                    onClick={() => setSelected(order)}
                  >
                    <td className="px-4 py-3">
                      <span className="font-mono font-medium">#{order.id.slice(0, 8)}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium">{order.user_display_name || '—'}</div>
                      <div className="text-xs text-[hsl(var(--muted-foreground))]">{order.user_email}</div>
                    </td>
                    <td className="px-4 py-3">
                      {order.items.length} item{order.items.length !== 1 ? 's' : ''}
                    </td>
                    <td className="px-4 py-3 font-medium">{formatCents(order.total_cents)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Badge variant={ORDER_STATUS_VARIANT[order.status]}>{order.status}</Badge>
                        {order.invoices && order.invoices.length > 0 && (
                          <span title="Invoice uploaded"><FileText className="h-3.5 w-3.5 text-[hsl(var(--muted-foreground))]" /></span>
                        )}
                        {order.purchase_url && (
                          <span title="Purchase URL"><Link2 className="h-3.5 w-3.5 text-[hsl(var(--muted-foreground))]" /></span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">{formatDate(order.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </CardContent>
      </Card>

      {/* Detail dialog */}
      <OrderDetailDialog
        order={selected}
        onClose={() => setSelected(null)}
        onOrderUpdated={handleOrderUpdated}
      />
    </div>
  )
}
