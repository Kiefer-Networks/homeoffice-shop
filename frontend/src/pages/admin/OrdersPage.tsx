import { useEffect, useState, useCallback, useMemo } from 'react'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { SearchInput } from '@/components/ui/search-input'
import { Pagination } from '@/components/ui/Pagination'
import { DataTable } from '@/components/ui/data-table'
import type { Column } from '@/components/ui/data-table'
import { adminApi } from '@/services/adminApi'
import { formatCents, formatDate } from '@/lib/utils'
import { ORDER_STATUS_VARIANT, DEFAULT_PAGE_SIZE, SEARCH_DEBOUNCE_MS } from '@/lib/constants'
import { useUiStore } from '@/stores/uiStore'
import { FileText, Link2, Download } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import { SortHeader } from '@/components/ui/SortHeader'
import { OrderDetailDialog } from '@/components/admin/OrderDetailDialog'
import type { Order } from '@/types'

const STATUS_FILTERS = ['', 'pending', 'ordered', 'delivered', 'rejected', 'cancelled', 'return_requested', 'returned'] as const

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

  const columns = useMemo<Column<Order>[]>(() => [
    {
      header: 'Order',
      accessor: (order) => (
        <span className="font-mono font-medium">#{order.id.slice(0, 8)}</span>
      ),
    },
    {
      header: 'User',
      accessor: (order) => (
        <>
          <div className="font-medium">{order.user_display_name || '—'}</div>
          <div className="text-xs text-[hsl(var(--muted-foreground))]">{order.user_email}</div>
        </>
      ),
    },
    {
      header: 'Items',
      accessor: (order) => (
        <>{order.items.length} item{order.items.length !== 1 ? 's' : ''}</>
      ),
    },
    {
      header: <SortHeader label="Total" ascKey="total_asc" descKey="total_desc" currentSort={sort} onSort={setSort} />,
      accessor: (order) => (
        <span className="font-medium">{formatCents(order.total_cents)}</span>
      ),
    },
    {
      header: 'Status',
      accessor: (order) => (
        <div className="flex items-center gap-2">
          <Badge variant={ORDER_STATUS_VARIANT[order.status]}>{order.status}</Badge>
          {order.invoices && order.invoices.length > 0 && (
            <span title="Invoice uploaded"><FileText className="h-3.5 w-3.5 text-[hsl(var(--muted-foreground))]" /></span>
          )}
          {order.purchase_url && (
            <span title="Purchase URL"><Link2 className="h-3.5 w-3.5 text-[hsl(var(--muted-foreground))]" /></span>
          )}
        </div>
      ),
    },
    {
      header: <SortHeader label="Date" ascKey="oldest" descKey="newest" currentSort={sort} onSort={setSort} />,
      accessor: (order) => (
        <span className="text-[hsl(var(--muted-foreground))]">{formatDate(order.created_at)}</span>
      ),
    },
  ], [sort])

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
        <SearchInput value={search} onChange={setSearch} placeholder="Search by name, email, order ID..." className="max-w-sm" />
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
      {loading && orders.length === 0 ? (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <tbody>
                  {[...Array(5)].map((_, i) => (
                    <tr key={i} className="border-b border-[hsl(var(--border))]">
                      <td colSpan={6} className="px-4 py-4"><div className="h-5 bg-gray-100 rounded animate-pulse" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
          </CardContent>
        </Card>
      ) : (
        <DataTable
          columns={columns}
          data={orders}
          rowKey={(order) => order.id}
          emptyMessage="No orders found."
          onRowClick={(order) => setSelected(order)}
        >
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </DataTable>
      )}

      {/* Detail dialog */}
      <OrderDetailDialog
        order={selected}
        onClose={() => setSelected(null)}
        onOrderUpdated={handleOrderUpdated}
      />
    </div>
  )
}
