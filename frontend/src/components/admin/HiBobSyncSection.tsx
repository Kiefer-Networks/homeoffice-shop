import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { formatDate } from '@/lib/utils'
import { useUiStore } from '@/stores/uiStore'
import { Trash2, Loader2, CloudUpload, Check } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import type { Order } from '@/types'

interface HiBobSyncSectionProps {
  order: Order
  onSyncChange: () => void
}

export function HiBobSyncSection({ order, onSyncChange }: HiBobSyncSectionProps) {
  const [showHiBobConfirm, setShowHiBobConfirm] = useState(false)
  const [hibobSyncing, setHibobSyncing] = useState(false)
  const [showHiBobDeleteModal, setShowHiBobDeleteModal] = useState(false)
  const [hibobDeleteInput, setHibobDeleteInput] = useState('')
  const [hibobDeleting, setHibobDeleting] = useState(false)

  const { addToast } = useUiStore()

  useEffect(() => {
    setShowHiBobConfirm(false)
    setShowHiBobDeleteModal(false)
    setHibobDeleteInput('')
  }, [order.id])

  const handleHiBobSync = async () => {
    setHibobSyncing(true)
    try {
      const { data } = await adminApi.syncOrderToHiBob(order.id)
      setShowHiBobConfirm(false)
      onSyncChange()
      addToast({ title: data.detail })
    } catch (err: unknown) {
      addToast({ title: 'Sync failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setHibobSyncing(false)
    }
  }

  const handleHiBobUnsync = async () => {
    setHibobDeleting(true)
    try {
      const { data } = await adminApi.unsyncOrderFromHiBob(order.id)
      setShowHiBobDeleteModal(false)
      setHibobDeleteInput('')
      onSyncChange()
      addToast({ title: data.detail })
    } catch (err: unknown) {
      addToast({ title: 'Unsync failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setHibobDeleting(false)
    }
  }

  return (
    <>
      <div className="flex items-center gap-2 mt-3">
        {order.hibob_synced_at ? (
          <div className="flex items-center gap-2 text-sm">
            <Check className="h-4 w-4 text-green-600" />
            <span className="text-[hsl(var(--muted-foreground))]">Synced to HiBob on {formatDate(order.hibob_synced_at)}</span>
            <Button size="sm" variant="ghost" className="text-red-600 hover:text-red-700 h-7 px-2"
              onClick={() => setShowHiBobDeleteModal(true)}>
              <Trash2 className="h-3 w-3 mr-1" /> Remove
            </Button>
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

      <Dialog open={showHiBobDeleteModal} onOpenChange={(open) => {
        if (!open) { setShowHiBobDeleteModal(false); setHibobDeleteInput('') }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove HiBob Sync</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              This will delete the synced entries from the employee's HiBob profile.
              This action affects a <strong>production system</strong>.
            </p>
            <p className="text-sm">
              Type <strong>DELETE</strong> to confirm:
            </p>
            <Input
              value={hibobDeleteInput}
              onChange={(e) => setHibobDeleteInput(e.target.value)}
              placeholder="DELETE"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowHiBobDeleteModal(false); setHibobDeleteInput('') }}
              disabled={hibobDeleting}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleHiBobUnsync}
              disabled={hibobDeleteInput !== 'DELETE' || hibobDeleting}>
              {hibobDeleting ? <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Deleting...</> : 'Delete from HiBob'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
