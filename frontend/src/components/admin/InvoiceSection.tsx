import { useState, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { adminApi } from '@/services/adminApi'
import { formatDate } from '@/lib/utils'
import { useUiStore } from '@/stores/uiStore'
import { Upload, Download, Trash2, Loader2, FileText } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import { getAccessToken } from '@/lib/token'
import type { Order, OrderInvoice } from '@/types'

interface InvoiceSectionProps {
  order: Order
  onInvoiceChange: () => void
}

export function InvoiceSection({ order, onInvoiceChange }: InvoiceSectionProps) {
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { addToast } = useUiStore()
  const apiUrl = import.meta.env.VITE_API_URL || ''

  const handleInvoiceUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return
    const file = e.target.files[0]
    setUploading(true)
    try {
      await adminApi.uploadInvoice(order.id, file)
      onInvoiceChange()
      addToast({ title: 'Invoice uploaded' })
    } catch (err: unknown) {
      addToast({ title: 'Upload failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleInvoiceDownload = async (invoiceId: string, filename: string) => {
    try {
      const url = `${apiUrl}${adminApi.downloadInvoiceUrl(order.id, invoiceId)}`
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

  const handleInvoiceDelete = async (invoiceId: string) => {
    try {
      await adminApi.deleteInvoice(order.id, invoiceId)
      onInvoiceChange()
      addToast({ title: 'Invoice deleted' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  return (
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
                  onClick={() => handleInvoiceDownload(inv.id, inv.filename)}>
                  <Download className="h-3 w-3" />
                </Button>
                <Button size="icon" variant="ghost" className="h-7 w-7 text-red-600 hover:text-red-700"
                  onClick={() => handleInvoiceDelete(inv.id)}>
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
  )
}
