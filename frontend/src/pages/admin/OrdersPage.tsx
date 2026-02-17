import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { formatCents, formatDate } from '@/lib/utils'
import { useUiStore } from '@/stores/uiStore'
import { ExternalLink, Check } from 'lucide-react'
import type { Order } from '@/types'

const statusVariant: Record<string, 'default' | 'secondary' | 'success' | 'destructive' | 'warning'> = {
  pending: 'warning', ordered: 'default', delivered: 'success', rejected: 'destructive', cancelled: 'secondary',
}

export function AdminOrdersPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [selected, setSelected] = useState<Order | null>(null)
  const [showStatusDialog, setShowStatusDialog] = useState(false)
  const [newStatus, setNewStatus] = useState('')
  const [adminNote, setAdminNote] = useState('')
  const { addToast } = useUiStore()

  const loadOrders = () => {
    const params: Record<string, string | number> = { page, per_page: 20 }
    if (statusFilter) params.status = statusFilter
    adminApi.listOrders(params).then(({ data }) => { setOrders(data.items); setTotal(data.total) })
  }

  useEffect(() => { loadOrders() }, [page, statusFilter])

  const handleStatusChange = async () => {
    if (!selected) return
    try {
      await adminApi.updateOrderStatus(selected.id, { status: newStatus, admin_note: adminNote || undefined })
      setShowStatusDialog(false)
      setAdminNote('')
      loadOrders()
      addToast({ title: 'Status updated' })
    } catch (err: any) {
      addToast({ title: 'Error', description: err.response?.data?.detail || 'Failed', variant: 'destructive' })
    }
  }

  const handleItemCheck = async (orderId: string, itemId: string, checked: boolean) => {
    await adminApi.checkOrderItem(orderId, itemId, checked)
    loadOrders()
  }

  const openAllLinks = (order: Order) => {
    order.items.forEach((item) => { window.open(item.external_url, '_blank') })
  }

  const transitions: Record<string, string[]> = {
    pending: ['ordered', 'rejected'], ordered: ['delivered', 'cancelled'],
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Orders</h1>

      <div className="flex gap-2 mb-4 flex-wrap">
        {['', 'pending', 'ordered', 'delivered', 'rejected', 'cancelled'].map((s) => (
          <Button key={s} size="sm" variant={statusFilter === s ? 'default' : 'outline'}
            onClick={() => { setStatusFilter(s); setPage(1) }}>
            {s || 'All'}
          </Button>
        ))}
      </div>

      <div className="space-y-4">
        {orders.map((order) => (
          <Card key={order.id}>
            <CardHeader className="flex flex-row items-start justify-between pb-2">
              <div>
                <CardTitle className="text-base">#{order.id.slice(0, 8)}</CardTitle>
                <p className="text-sm text-[hsl(var(--muted-foreground))]">
                  {order.user_display_name} ({order.user_email}) - {formatDate(order.created_at)}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={statusVariant[order.status]}>{order.status}</Badge>
                <span className="font-bold">{formatCents(order.total_cents)}</span>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {order.items.map((item) => (
                  <div key={item.id} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <input type="checkbox" checked={item.vendor_ordered}
                        onChange={(e) => handleItemCheck(order.id, item.id, e.target.checked)}
                        className="rounded" />
                      <span className={item.vendor_ordered ? 'line-through text-gray-400' : ''}>
                        {item.product_name || 'Product'} x{item.quantity}
                      </span>
                      <a href={item.external_url} target="_blank" rel="noopener noreferrer" className="text-blue-600">
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                    <span>{formatCents(item.price_cents * item.quantity)}</span>
                  </div>
                ))}
              </div>
              {order.delivery_note && <p className="text-sm mt-2 text-[hsl(var(--muted-foreground))]">Note: {order.delivery_note}</p>}
              <div className="flex gap-2 mt-3">
                <Button size="sm" variant="outline" onClick={() => openAllLinks(order)}>
                  <ExternalLink className="h-3 w-3 mr-1" /> Open All Links
                </Button>
                {transitions[order.status]?.map((status) => (
                  <Button key={status} size="sm"
                    variant={status === 'rejected' || status === 'cancelled' ? 'destructive' : 'default'}
                    onClick={() => { setSelected(order); setNewStatus(status); setShowStatusDialog(true) }}>
                    {status}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={showStatusDialog} onOpenChange={setShowStatusDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change Status to "{newStatus}"</DialogTitle>
          </DialogHeader>
          {(newStatus === 'rejected') && (
            <div>
              <label className="text-sm font-medium">Reason (required)</label>
              <Input value={adminNote} onChange={(e) => setAdminNote(e.target.value)} placeholder="Enter reason..." className="mt-1" />
            </div>
          )}
          {newStatus !== 'rejected' && (
            <div>
              <label className="text-sm font-medium">Note (optional)</label>
              <Input value={adminNote} onChange={(e) => setAdminNote(e.target.value)} placeholder="Enter note..." className="mt-1" />
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowStatusDialog(false)}>Cancel</Button>
            <Button onClick={handleStatusChange} disabled={newStatus === 'rejected' && !adminNote}>Confirm</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
