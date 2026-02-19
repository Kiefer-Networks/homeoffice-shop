import { useState, useEffect, useRef } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { formatCents, formatDate } from '@/lib/utils'
import { useUiStore } from '@/stores/uiStore'
import {
  ExternalLink, Upload, Download, Trash2, Loader2, FileText, Link2, CloudUpload, Check,
} from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import { getAccessToken } from '@/lib/token'
import type { Order, OrderInvoice } from '@/types'

const statusVariant: Record<string, 'default' | 'secondary' | 'success' | 'destructive' | 'warning'> = {
  pending: 'warning', ordered: 'default', delivered: 'success', rejected: 'destructive', cancelled: 'secondary',
}

type PendingAction = 'ordered' | 'rejected' | 'delivered' | 'cancelled' | null

interface OrderDetailDialogProps {
  order: Order | null
  onClose: () => void
  onOrderUpdated: (order: Order) => void
}

export function OrderDetailDialog({ order, onClose, onOrderUpdated }: OrderDetailDialogProps) {
  // Inline status change
  const [pendingAction, setPendingAction] = useState<PendingAction>(null)
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
  const [showHiBobConfirm, setShowHiBobConfirm] = useState(false)
  const [hibobSyncing, setHibobSyncing] = useState(false)

  const { addToast } = useUiStore()
  const apiUrl = import.meta.env.VITE_API_URL || ''

  // Sync purchase_url field when order changes
  useEffect(() => {
    if (order) {
      setPurchaseUrl(order.purchase_url || '')
      setPendingAction(null)
      setAdminNote('')
      setExpectedDelivery('')
      setShowHiBobConfirm(false)
    }
  }, [order])

  const refreshOrder = async (orderId: string) => {
    try {
      const { data } = await adminApi.getOrder(orderId)
      onOrderUpdated(data)
    } catch { /* ignore */ }
  }

  // --- Status change ---
  const startAction = (action: PendingAction) => {
    setPendingAction(action)
    setAdminNote('')
    setExpectedDelivery('')
  }

  const handleStatusConfirm = async () => {
    if (!order || !pendingAction) return
    setStatusLoading(true)
    try {
      const payload: Record<string, string | undefined> = {
        status: pendingAction,
        admin_note: adminNote || undefined,
      }
      if (pendingAction === 'ordered' && expectedDelivery) {
        payload.expected_delivery = expectedDelivery
      }
      await adminApi.updateOrderStatus(order.id, payload as { status: string; admin_note?: string; expected_delivery?: string })
      setPendingAction(null)
      await refreshOrder(order.id)
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
      await refreshOrder(orderId)
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  // --- Purchase URL ---
  const handleSavePurchaseUrl = async () => {
    if (!order) return
    setPurchaseUrlSaving(true)
    try {
      await adminApi.updatePurchaseUrl(order.id, purchaseUrl || null)
      await refreshOrder(order.id)
      addToast({ title: 'Purchase URL saved' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setPurchaseUrlSaving(false)
    }
  }

  // --- Invoice upload ---
  const handleInvoiceUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!order || !e.target.files?.length) return
    const file = e.target.files[0]
    setUploading(true)
    try {
      await adminApi.uploadInvoice(order.id, file)
      await refreshOrder(order.id)
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
      await refreshOrder(orderId)
      addToast({ title: 'Invoice deleted' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  // --- HiBob sync ---
  const handleHiBobSync = async () => {
    if (!order) return
    setHibobSyncing(true)
    try {
      const { data } = await adminApi.syncOrderToHiBob(order.id)
      setShowHiBobConfirm(false)
      await refreshOrder(order.id)
      addToast({ title: data.detail })
    } catch (err: unknown) {
      addToast({ title: 'Sync failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setHibobSyncing(false)
    }
  }

  // Open all vendor links
  const openAllLinks = (o: Order) => {
    o.items.forEach((item) => { window.open(item.external_url, '_blank', 'noopener,noreferrer') })
  }

  // Action button labels
  const actionButtons: Record<string, { label: string; action: PendingAction; variant: 'default' | 'destructive' }[]> = {
    pending: [
      { label: 'Approve', action: 'ordered', variant: 'default' },
      { label: 'Reject', action: 'rejected', variant: 'destructive' },
    ],
    ordered: [
      { label: 'Mark Delivered', action: 'delivered', variant: 'default' },
      { label: 'Cancel Order', action: 'cancelled', variant: 'destructive' },
    ],
  }

  return (
    <Dialog open={!!order} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        {order && (
          <>
            {/* Header */}
            <DialogHeader>
              <DialogTitle className="flex items-center gap-3">
                <span className="font-mono">#{order.id.slice(0, 8)}</span>
                <Badge variant={statusVariant[order.status]}>{order.status}</Badge>
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
                    disabled={purchaseUrlSaving || purchaseUrl === (order.purchase_url || '')}
                  >
                    {purchaseUrlSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save'}
                  </Button>
                </div>
              </div>
            )}

            {/* Invoices */}
            {order.status !== 'rejected' && order.status !== 'cancelled' && (
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
                {order.invoices && order.invoices.length > 0 ? (
                  <div className="border rounded-lg divide-y">
                    {order.invoices.map((inv: OrderInvoice) => (
                      <div key={inv.id} className="flex items-center justify-between px-3 py-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <FileText className="h-4 w-4 text-[hsl(var(--muted-foreground))] shrink-0" />
                          <span className="text-sm truncate">{inv.filename}</span>
                          <span className="text-xs text-[hsl(var(--muted-foreground))] shrink-0">{formatDate(inv.uploaded_at)}</span>
                        </div>
                        <div className="flex gap-1 shrink-0">
                          <Button size="icon" variant="ghost" className="h-7 w-7"
                            onClick={() => handleInvoiceDownload(order.id, inv.id, inv.filename)}>
                            <Download className="h-3 w-3" />
                          </Button>
                          <Button size="icon" variant="ghost" className="h-7 w-7 text-red-600 hover:text-red-700"
                            onClick={() => handleInvoiceDelete(order.id, inv.id)}>
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

            {/* Actions bar */}
            {(actionButtons[order.status] || order.status === 'delivered') && (
              <div className="pt-2 border-t">
                {/* Status transition buttons or inline form */}
                {pendingAction ? (
                  <div className="space-y-3">
                    <div className="text-sm font-medium">
                      {pendingAction === 'ordered' && 'Approve Order'}
                      {pendingAction === 'rejected' && 'Reject Order'}
                      {pendingAction === 'delivered' && 'Mark as Delivered'}
                      {pendingAction === 'cancelled' && 'Cancel Order'}
                    </div>

                    {pendingAction === 'ordered' && (
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

                    <div>
                      <label className="text-sm font-medium">
                        {pendingAction === 'rejected' ? 'Reason (required)' : 'Note (optional)'}
                      </label>
                      <Input
                        value={adminNote}
                        onChange={(e) => setAdminNote(e.target.value)}
                        placeholder={pendingAction === 'rejected' ? 'Enter reason...' : 'Enter note...'}
                        className="mt-1"
                      />
                    </div>

                    <div className="flex gap-2">
                      <Button
                        onClick={handleStatusConfirm}
                        disabled={statusLoading || (pendingAction === 'rejected' && !adminNote)}
                      >
                        {statusLoading ? <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Updating...</> : 'Confirm'}
                      </Button>
                      <Button variant="outline" onClick={() => setPendingAction(null)} disabled={statusLoading}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {actionButtons[order.status]?.map((btn) => (
                      <Button key={btn.action} variant={btn.variant} onClick={() => startAction(btn.action)}>
                        {btn.label}
                      </Button>
                    ))}
                  </div>
                )}

                {/* HiBob sync */}
                {order.status === 'delivered' && !pendingAction && (
                  <div className="flex items-center gap-2 mt-3">
                    {order.hibob_synced_at ? (
                      <div className="flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))]">
                        <Check className="h-4 w-4 text-green-600" />
                        <span>Synced to HiBob on {formatDate(order.hibob_synced_at)}</span>
                      </div>
                    ) : showHiBobConfirm ? (
                      <div className="flex items-center gap-2">
                        <span className="text-sm">
                          This will sync {order.items.length} entr{order.items.length === 1 ? 'y' : 'ies'} to HiBob.
                        </span>
                        <Button size="sm" onClick={handleHiBobSync} disabled={hibobSyncing}>
                          {hibobSyncing ? <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Syncing...</> : 'Confirm'}
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setShowHiBobConfirm(false)} disabled={hibobSyncing}>
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <Button variant="outline" onClick={() => setShowHiBobConfirm(true)}>
                        <CloudUpload className="h-4 w-4 mr-1" /> Sync to HiBob
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
