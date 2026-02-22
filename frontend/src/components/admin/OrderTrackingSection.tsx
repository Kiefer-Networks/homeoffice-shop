import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { adminApi } from '@/services/adminApi'
import { detectCarrier, isAmazonAuthUrl, formatDate } from '@/lib/utils'
import { useUiStore } from '@/stores/uiStore'
import { ExternalLink, Loader2, Truck, MessageSquare, AlertTriangle, RefreshCw } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import type { Order } from '@/types'

interface OrderTrackingSectionProps {
  order: Order
  onUpdate: (order: Order) => void
}

export function OrderTrackingSection({ order, onUpdate }: OrderTrackingSectionProps) {
  const [trackingNumber, setTrackingNumber] = useState(order.tracking_number || '')
  const [trackingUrl, setTrackingUrl] = useState(order.tracking_url || '')
  const [trackingComment, setTrackingComment] = useState('')
  const [trackingSaving, setTrackingSaving] = useState(false)
  const [aftershipSyncing, setAftershipSyncing] = useState(false)

  const { addToast } = useUiStore()

  useEffect(() => {
    setTrackingNumber(order.tracking_number || '')
    setTrackingUrl(order.tracking_url || '')
    setTrackingComment('')
  }, [order])

  const refreshOrder = async () => {
    try {
      const { data } = await adminApi.getOrder(order.id)
      onUpdate(data)
    } catch { /* ignore */ }
  }

  const handleSaveTracking = async () => {
    setTrackingSaving(true)
    try {
      await adminApi.updateOrderTracking(order.id, {
        tracking_number: trackingNumber || null,
        tracking_url: trackingUrl || null,
        comment: trackingComment || null,
      })
      setTrackingComment('')
      await refreshOrder()
      addToast({ title: 'Tracking updated & employee notified' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setTrackingSaving(false)
    }
  }

  const handleAftershipSync = async () => {
    setAftershipSyncing(true)
    try {
      await adminApi.syncAfterShipTracking(order.id)
      await refreshOrder()
      addToast({ title: 'AfterShip sync complete' })
    } catch (err: unknown) {
      addToast({ title: 'AfterShip sync failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setAftershipSyncing(false)
    }
  }

  const detected = detectCarrier(trackingNumber)
  const amazonAuthWarning = isAmazonAuthUrl(trackingUrl)

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Truck className="h-4 w-4" />
        <h3 className="font-medium">Tracking</h3>
      </div>
      <div className="space-y-2">
        <div>
          <label className="text-sm font-medium block mb-1">Tracking Number</label>
          <Input
            value={trackingNumber}
            onChange={(e) => {
              const val = e.target.value
              setTrackingNumber(val)
              // Auto-fill tracking URL when carrier is detected and URL is empty or was auto-filled
              const carrier = detectCarrier(val.trim())
              if (carrier && (!trackingUrl || detectCarrier(order.tracking_number || '')?.trackingUrl === trackingUrl)) {
                setTrackingUrl(carrier.trackingUrl)
              }
            }}
            placeholder="e.g. DE5240663797, 1Z999AA1..."
          />
          {detected && (
            <div className="text-xs text-green-600 mt-1">
              Erkannt: <strong>{detected.name}</strong>
            </div>
          )}
        </div>
        <div>
          <label className="text-sm font-medium block mb-1">Tracking URL</label>
          <div className="flex gap-2">
            <Input
              value={trackingUrl}
              onChange={(e) => setTrackingUrl(e.target.value)}
              placeholder="https://..."
              className="flex-1"
            />
            {trackingUrl && (
              <Button size="icon" variant="outline" asChild>
                <a href={trackingUrl} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="h-4 w-4" />
                </a>
              </Button>
            )}
          </div>
          {amazonAuthWarning && (
            <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2 mt-1 flex items-start gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              <span>
                Diese Amazon-URL erfordert Login und funktioniert nicht für Mitarbeiter.
                Bitte stattdessen die Carrier-Tracking-URL verwenden (z.B. DHL, Swiship).
              </span>
            </div>
          )}
        </div>
        <div>
          <label className="text-sm font-medium block mb-1">Comment (optional)</label>
          <Input
            value={trackingComment}
            onChange={(e) => setTrackingComment(e.target.value)}
            placeholder="Status update for the employee..."
          />
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={handleSaveTracking}
            disabled={trackingSaving || (
              trackingNumber === (order.tracking_number || '') &&
              trackingUrl === (order.tracking_url || '') &&
              !trackingComment
            )}
          >
            {trackingSaving ? <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Saving...</> : 'Save & Notify Employee'}
          </Button>
          {order.tracking_number && (
            <Button
              size="sm"
              variant="outline"
              onClick={handleAftershipSync}
              disabled={aftershipSyncing}
            >
              {aftershipSyncing ? <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Syncing...</> : <><RefreshCw className="h-3 w-3 mr-1" /> AfterShip Sync</>}
            </Button>
          )}
        </div>
        {order.aftership_tracking_id && (
          <div className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
            AfterShip: {order.aftership_slug} ({order.aftership_tracking_id.slice(0, 12)}...)
          </div>
        )}
      </div>

      {/* Timeline */}
      {order.tracking_updates && order.tracking_updates.length > 0 && (
        <div className="mt-4">
          <h4 className="text-sm font-medium mb-2 flex items-center gap-1">
            <MessageSquare className="h-3 w-3" /> Updates
          </h4>
          <div className="space-y-2">
            {order.tracking_updates.map((update) => (
              <div key={update.id} className="text-sm p-2 rounded bg-[hsl(var(--muted)/0.5)] border">
                <div className="text-[hsl(var(--muted-foreground))] text-xs mb-1">
                  {update.created_by_name || 'Admin'} — {formatDate(update.created_at)}
                </div>
                <div>{update.comment}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
