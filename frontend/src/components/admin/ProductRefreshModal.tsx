import { useEffect, useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Loader2, CheckCircle2 } from 'lucide-react'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { formatCents } from '@/lib/utils'
import { getErrorMessage } from '@/lib/error'
import type { ProductFieldDiff } from '@/types'

interface Props {
  open: boolean
  onClose: () => void
  onApplied: () => void
  productId: string
  productName: string
}

function formatValue(field: string, value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (field === 'price_cents') return formatCents(value as number)
  if (typeof value === 'object') {
    const s = JSON.stringify(value)
    return s.length > 80 ? s.slice(0, 80) + '...' : s
  }
  const s = String(value)
  return s.length > 80 ? s.slice(0, 80) + '...' : s
}

export function ProductRefreshModal({ open, onClose, onApplied, productId, productName }: Props) {
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState(false)
  const [diffs, setDiffs] = useState<ProductFieldDiff[]>([])
  const [imagesUpdated, setImagesUpdated] = useState(false)
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [fetched, setFetched] = useState(false)

  const { addToast } = useUiStore()

  useEffect(() => {
    if (!open) {
      setDiffs([])
      setChecked(new Set())
      setFetched(false)
      setImagesUpdated(false)
      return
    }
    setLoading(true)
    adminApi.refreshPreview(productId)
      .then(({ data }) => {
        setDiffs(data.diffs)
        setImagesUpdated(data.images_updated)
        setChecked(new Set(data.diffs.map(d => d.field)))
        setFetched(true)
      })
      .catch((err) => {
        addToast({ title: 'Refresh failed', description: getErrorMessage(err), variant: 'destructive' })
        onClose()
      })
      .finally(() => setLoading(false))
  }, [open, productId])

  const toggle = (field: string) => {
    setChecked(prev => {
      const next = new Set(prev)
      if (next.has(field)) next.delete(field)
      else next.add(field)
      return next
    })
  }

  const handleApply = async () => {
    const selectedDiffs = diffs.filter(d => checked.has(d.field))
    if (selectedDiffs.length === 0) {
      onClose()
      return
    }
    setApplying(true)
    try {
      const fields = selectedDiffs.map(d => d.field)
      const values: Record<string, unknown> = {}
      for (const d of selectedDiffs) {
        values[d.field] = d.new_value
      }
      await adminApi.refreshApply(productId, { fields, values })
      addToast({ title: 'Product updated' })
      onApplied()
    } catch (err) {
      addToast({ title: 'Apply failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setApplying(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={() => onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Refresh: {productName}</DialogTitle>
        </DialogHeader>

        {loading && (
          <div className="flex items-center justify-center py-8 gap-2 text-sm text-[hsl(var(--muted-foreground))]">
            <Loader2 className="h-5 w-5 animate-spin" /> Fetching Amazon data...
          </div>
        )}

        {fetched && !loading && (
          <div className="space-y-4">
            {imagesUpdated && (
              <div className="flex items-center gap-2 text-sm text-green-600 bg-green-50 dark:bg-green-950/30 rounded-md px-3 py-2">
                <CheckCircle2 className="h-4 w-4" />
                Images have been updated automatically.
              </div>
            )}

            {diffs.length === 0 ? (
              <p className="text-sm text-[hsl(var(--muted-foreground))] py-4 text-center">
                {imagesUpdated ? 'No other changes detected.' : 'No changes detected.'}
              </p>
            ) : (
              <div className="overflow-x-auto border rounded-md">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-[hsl(var(--muted))]">
                      <th className="px-3 py-2 w-8"></th>
                      <th className="text-left px-3 py-2 font-medium">Field</th>
                      <th className="text-left px-3 py-2 font-medium">Current</th>
                      <th className="text-left px-3 py-2 font-medium">New</th>
                    </tr>
                  </thead>
                  <tbody>
                    {diffs.map((d) => (
                      <tr key={d.field} className="border-b last:border-b-0">
                        <td className="px-3 py-2 text-center">
                          <input
                            type="checkbox"
                            checked={checked.has(d.field)}
                            onChange={() => toggle(d.field)}
                            className="rounded"
                          />
                        </td>
                        <td className="px-3 py-2 font-medium whitespace-nowrap">{d.label}</td>
                        <td className="px-3 py-2 text-[hsl(var(--muted-foreground))] max-w-[200px] truncate">
                          {formatValue(d.field, d.old_value)}
                        </td>
                        <td className="px-3 py-2 max-w-[200px] truncate">
                          {formatValue(d.field, d.new_value)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {diffs.length === 0 ? 'Close' : 'Cancel'}
          </Button>
          {diffs.length > 0 && (
            <Button onClick={handleApply} disabled={applying || checked.size === 0}>
              {applying ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Applying...</>
              ) : (
                `Apply Selected (${checked.size})`
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
