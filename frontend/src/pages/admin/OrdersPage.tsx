import { useEffect, useState, useCallback, useRef } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { formatCents, formatDate } from '@/lib/utils'
import { useUiStore } from '@/stores/uiStore'
import {
  Search, ExternalLink, ChevronDown, ChevronUp, Upload, Download, Trash2, Loader2, FileText, Link2, CloudUpload, Check,
} from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import { getAccessToken } from '@/lib/token'
import type { Order, OrderInvoice } from '@/types'

const PER_PAGE = 20

const statusVariant: Record<string, 'default' | 'secondary' | 'success' | 'destructive' | 'warning'> = {
  pending: 'warning', ordered: 'default', delivered: 'success', rejected: 'destructive', cancelled: 'secondary',
}

const STATUS_FILTERS = ['', 'pending', 'ordered', 'delivered', 'rejected', 'cancelled'] as const

type SortKey = 'newest' | 'oldest' | 'total_asc' | 'total_desc'

function SortHeader({
  label, ascKey, descKey, currentSort, onSort,
}: {
  label: string; ascKey: SortKey; descKey: SortKey; currentSort: SortKey; onSort: (k: SortKey) => void
}) {
  const isActive = currentSort === ascKey || currentSort === descKey
  const handleClick = () => onSort(currentSort === ascKey ? descKey : ascKey)
  return (
    <button onClick={handleClick} className="inline-flex items-center gap-1 hover:text-[hsl(var(--foreground))] transition-colors">
      {label}
      {isActive && (currentSort === descKey ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />)}
    </button>
  )
}

export function AdminOrdersPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [sort, setSort] = useState<SortKey>('newest')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  // Detail dialog
  const [selected, setSelected] = useState<Order | null>(null)

  // Status change dialog
  const [showStatusDialog, setShowStatusDialog] = useState(false)
  const [statusTarget, setStatusTarget] = useState<Order | null>(null)
  const [newStatus, setNewStatus] = useState('')
  const [adminNote, setAdminNote] = useState('')
  const [expectedDelivery, setExpectedDelivery] = useState('')
  const [statusLoading, setStatusLoading] = useState(false)

  // Purchase URL
  const [purchaseUrl, setPurchaseUrl] = useState('')
  const [purchaseUrlSaving, setPurchaseUrlSaving] = useState(false)

  // Invoice upload
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // HiBob sync
  const [showHiBobDialog, setShowHiBobDialog] = useState(false)
  const [hibobSyncing, setHibobSyncing] = useState(false)

  const { addToast } = useUiStore()
  const apiUrl = import.meta.env.VITE_API_URL || ''

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  const loadOrders = useCallback(() => {
    setLoading(true)
    const params: Record<string, string | number> = { page, per_page: PER_PAGE, sort }
    if (statusFilter) params.status = statusFilter
    if (debouncedSearch) params.q = debouncedSearch
    adminApi.listOrders(params)
      .then(({ data }) => { setOrders(data.items); setTotal(data.total) })
      .catch((err: unknown) => addToast({ title: 'Error loading orders', description: getErrorMessage(err), variant: 'destructive' }))
      .finally(() => setLoading(false))
  }, [page, statusFilter, sort, debouncedSearch])

  useEffect(() => { loadOrders() }, [loadOrders])
  useEffect(() => { setPage(1) }, [debouncedSearch, statusFilter, sort])

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE))

  // Refresh selected order after mutations
  const refreshSelected = async (orderId: string) => {
    try {
      const { data } = await adminApi.getOrder(orderId)
      setSelected(data)
      // Also update in list
      setOrders(prev => prev.map(o => o.id === orderId ? data : o))
    } catch { /* ignore */ }
  }

  // --- Status change ---
  const openStatusDialog = (order: Order, status: string) => {
    setStatusTarget(order)
    setNewStatus(status)
    setAdminNote('')
    setExpectedDelivery('')
    setShowStatusDialog(true)
  }

  const handleStatusChange = async () => {
    if (!statusTarget) return
    setStatusLoading(true)
    try {
      const payload: Record<string, string | undefined> = {
        status: newStatus,
        admin_note: adminNote || undefined,
      }
      if (newStatus === 'ordered' && expectedDelivery) {
        payload.expected_delivery = expectedDelivery
      }
      await adminApi.updateOrderStatus(statusTarget.id, payload as { status: string; admin_note?: string; expected_delivery?: string })
      setShowStatusDialog(false)
      loadOrders()
      if (selected?.id === statusTarget.id) {
        await refreshSelected(statusTarget.id)
      }
      addToast({ title: 'Status updated' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setStatusLoading(false)
    }
  }

  // --- Item check ---
  const handleItemCheck = async (orderId: string, itemId: string, checked: boolean) => {
    try {
      await adminApi.checkOrderItem(orderId, itemId, checked)
      await refreshSelected(orderId)
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  // --- Purchase URL ---
  const handleSavePurchaseUrl = async () => {
    if (!selected) return
    setPurchaseUrlSaving(true)
    try {
      await adminApi.updatePurchaseUrl(selected.id, purchaseUrl || null)
      await refreshSelected(selected.id)
      addToast({ title: 'Purchase URL saved' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setPurchaseUrlSaving(false)
    }
  }

  // --- Invoice upload ---
  const handleInvoiceUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!selected || !e.target.files?.length) return
    const file = e.target.files[0]
    setUploading(true)
    try {
      await adminApi.uploadInvoice(selected.id, file)
      await refreshSelected(selected.id)
      addToast({ title: 'Invoice uploaded' })
    } catch (err: unknown) {
      addToast({ title: 'Upload failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleInvoiceDownload = async (orderId: string, invoiceId: string, filename: string) => {
    try {
      const url = `${apiUrl}${adminApi.downloadInvoiceUrl(orderId, invoiceId)}`
      const token = getAccessToken()
      const response = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!response.ok) throw new Error('Download failed')
      const blob = await response.blob()
      const blobUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = filename
      a.click()
      URL.revokeObjectURL(blobUrl)
    } catch (err: unknown) {
      addToast({ title: 'Download failed', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const handleInvoiceDelete = async (orderId: string, invoiceId: string) => {
    try {
      await adminApi.deleteInvoice(orderId, invoiceId)
      await refreshSelected(orderId)
      addToast({ title: 'Invoice deleted' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  // --- HiBob sync ---
  const handleHiBobSync = async () => {
    if (!selected) return
    setHibobSyncing(true)
    try {
      const { data } = await adminApi.syncOrderToHiBob(selected.id)
      setShowHiBobDialog(false)
      await refreshSelected(selected.id)
      addToast({ title: data.detail })
    } catch (err: unknown) {
      addToast({ title: 'Sync failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setHibobSyncing(false)
    }
  }

  // Open all vendor links
  const openAllLinks = (order: Order) => {
    order.items.forEach((item) => { window.open(item.external_url, '_blank', 'noopener,noreferrer') })
  }

  const transitions: Record<string, string[]> = {
    pending: ['ordered', 'rejected'], ordered: ['delivered', 'cancelled'],
  }

  // When detail dialog opens, sync purchase_url field
  useEffect(() => {
    if (selected) {
      setPurchaseUrl(selected.purchase_url || '')
    }
  }, [selected])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Orders ({total})</h1>

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
                  <th className="text-right px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading && orders.length === 0 ? (
                  [...Array(5)].map((_, i) => (
                    <tr key={i} className="border-b border-[hsl(var(--border))]">
                      <td colSpan={7} className="px-4 py-4"><div className="h-5 bg-gray-100 rounded animate-pulse" /></td>
                    </tr>
                  ))
                ) : orders.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">No orders found.</td>
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
                      <Badge variant={statusVariant[order.status]}>{order.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">{formatDate(order.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                        {transitions[order.status]?.map((status) => (
                          <Button key={status} size="sm"
                            variant={status === 'rejected' || status === 'cancelled' ? 'destructive' : 'default'}
                            onClick={() => openStatusDialog(order, status)}>
                            {status}
                          </Button>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-[hsl(var(--border))]">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Previous</Button>
              <span className="text-sm text-[hsl(var(--muted-foreground))]">Page {page} of {totalPages}</span>
              <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next</Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ===== Order Detail Dialog ===== */}
      <Dialog open={!!selected} onOpenChange={(open) => { if (!open) setSelected(null) }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          {selected && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-3">
                  <span className="font-mono">#{selected.id.slice(0, 8)}</span>
                  <Badge variant={statusVariant[selected.status]}>{selected.status}</Badge>
                  <span className="text-sm font-normal text-[hsl(var(--muted-foreground))]">{formatDate(selected.created_at)}</span>
                </DialogTitle>
              </DialogHeader>

              {/* User info */}
              <div className="border rounded-lg p-3 bg-[hsl(var(--muted)/0.3)]">
                <div className="font-medium">{selected.user_display_name}</div>
                <div className="text-sm text-[hsl(var(--muted-foreground))]">{selected.user_email}</div>
              </div>

              {/* Items table */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-medium">Items</h3>
                  <Button size="sm" variant="outline" onClick={() => openAllLinks(selected)}>
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
                      {selected.items.map((item) => (
                        <tr key={item.id} className="border-b last:border-b-0">
                          <td className="px-3 py-2">
                            <input
                              type="checkbox"
                              checked={item.vendor_ordered}
                              onChange={(e) => handleItemCheck(selected.id, item.id, e.target.checked)}
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
                        <td className="px-3 py-2 font-bold text-right">{formatCents(selected.total_cents)}</td>
                        <td></td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>

              {/* Delivery note */}
              {selected.delivery_note && (
                <div className="text-sm">
                  <span className="font-medium">Delivery note:</span>{' '}
                  <span className="text-[hsl(var(--muted-foreground))]">{selected.delivery_note}</span>
                </div>
              )}

              {/* Expected delivery */}
              {selected.expected_delivery && (
                <div className="text-sm">
                  <span className="font-medium">Expected delivery:</span>{' '}
                  <span className="text-[hsl(var(--muted-foreground))]">{formatDate(selected.expected_delivery)}</span>
                </div>
              )}

              {/* Admin note / rejection reason */}
              {selected.admin_note && (
                <div className="text-sm p-2 rounded bg-amber-50 border border-amber-200">
                  <span className="font-medium">{selected.status === 'rejected' ? 'Rejection reason' : 'Admin note'}:</span>{' '}
                  {selected.admin_note}
                </div>
              )}
              {selected.cancellation_reason && (
                <div className="text-sm p-2 rounded bg-gray-50 border border-gray-200">
                  <span className="font-medium">Cancellation reason:</span>{' '}
                  {selected.cancellation_reason}
                  {selected.cancelled_at && <span className="text-xs ml-2 text-[hsl(var(--muted-foreground))]">({formatDate(selected.cancelled_at)})</span>}
                </div>
              )}

              {/* Purchase URL — only for active orders */}
              {selected.status !== 'rejected' && selected.status !== 'cancelled' && (
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
                      disabled={purchaseUrlSaving || purchaseUrl === (selected.purchase_url || '')}
                    >
                      {purchaseUrlSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save'}
                    </Button>
                  </div>
                </div>
              )}

              {/* Invoices — only for active orders */}
              {selected.status !== 'rejected' && selected.status !== 'cancelled' && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-medium">Invoices</h3>
                    <div>
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf,.jpg,.jpeg,.png"
                        onChange={handleInvoiceUpload}
                        className="hidden"
                      />
                      <Button size="sm" variant="outline" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
                        {uploading ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Upload className="h-3 w-3 mr-1" />}
                        Upload
                      </Button>
                    </div>
                  </div>
                  {selected.invoices && selected.invoices.length > 0 ? (
                    <div className="border rounded-lg divide-y">
                      {selected.invoices.map((inv: OrderInvoice) => (
                        <div key={inv.id} className="flex items-center justify-between px-3 py-2">
                          <div className="flex items-center gap-2 min-w-0">
                            <FileText className="h-4 w-4 text-[hsl(var(--muted-foreground))] shrink-0" />
                            <span className="text-sm truncate">{inv.filename}</span>
                            <span className="text-xs text-[hsl(var(--muted-foreground))] shrink-0">{formatDate(inv.uploaded_at)}</span>
                          </div>
                          <div className="flex gap-1 shrink-0">
                            <Button size="icon" variant="ghost" className="h-7 w-7"
                              onClick={() => handleInvoiceDownload(selected.id, inv.id, inv.filename)}>
                              <Download className="h-3 w-3" />
                            </Button>
                            <Button size="icon" variant="ghost" className="h-7 w-7 text-red-600 hover:text-red-700"
                              onClick={() => handleInvoiceDelete(selected.id, inv.id)}>
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-[hsl(var(--muted-foreground))]">No invoices uploaded.</p>
                  )}
                </div>
              )}

              {/* Status transition buttons */}
              {transitions[selected.status] && (
                <div className="flex gap-2 pt-2 border-t">
                  {transitions[selected.status].map((status) => (
                    <Button key={status}
                      variant={status === 'rejected' || status === 'cancelled' ? 'destructive' : 'default'}
                      onClick={() => openStatusDialog(selected, status)}>
                      Mark as {status}
                    </Button>
                  ))}
                </div>
              )}

              {/* HiBob sync */}
              {selected.status === 'delivered' && (
                <div className="flex items-center gap-2 pt-2 border-t">
                  {selected.hibob_synced_at ? (
                    <div className="flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))]">
                      <Check className="h-4 w-4 text-green-600" />
                      <span>Synced to HiBob on {formatDate(selected.hibob_synced_at)}</span>
                    </div>
                  ) : (
                    <Button variant="outline" onClick={() => setShowHiBobDialog(true)}>
                      <CloudUpload className="h-4 w-4 mr-1" /> Sync to HiBob
                    </Button>
                  )}
                </div>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* ===== Status Change Dialog ===== */}
      <Dialog open={showStatusDialog} onOpenChange={setShowStatusDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change Status to "{newStatus}"</DialogTitle>
          </DialogHeader>

          {newStatus === 'ordered' && (
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

          {newStatus === 'rejected' ? (
            <div>
              <label className="text-sm font-medium">Reason (required)</label>
              <Input value={adminNote} onChange={(e) => setAdminNote(e.target.value)} placeholder="Enter reason..." className="mt-1" />
            </div>
          ) : (
            <div>
              <label className="text-sm font-medium">Note (optional)</label>
              <Input value={adminNote} onChange={(e) => setAdminNote(e.target.value)} placeholder="Enter note..." className="mt-1" />
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowStatusDialog(false)}>Cancel</Button>
            <Button
              onClick={handleStatusChange}
              disabled={statusLoading || (newStatus === 'rejected' && !adminNote)}
            >
              {statusLoading ? <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Updating...</> : 'Confirm'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ===== HiBob Sync Confirmation Dialog ===== */}
      <Dialog open={showHiBobDialog} onOpenChange={setShowHiBobDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Sync to HiBob</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            This will create {selected?.items.length ?? 0} entr{(selected?.items.length ?? 0) === 1 ? 'y' : 'ies'} in the employee's HiBob profile. Continue?
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowHiBobDialog(false)}>Cancel</Button>
            <Button onClick={handleHiBobSync} disabled={hibobSyncing}>
              {hibobSyncing ? <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Syncing...</> : 'Confirm'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
