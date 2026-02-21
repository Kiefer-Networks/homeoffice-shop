import { useEffect, useState, useRef, useCallback } from 'react'
import { adminApi } from '@/services/adminApi'

/**
 * Polls the purchase sync status every 5 seconds.
 * Returns whether sync is currently running and calls `onSyncFinished`
 * when a running sync completes.
 */
export function usePurchaseSyncStatus(onSyncFinished: () => void) {
  const [syncRunning, setSyncRunning] = useState(false)
  const prevSyncRunning = useRef(syncRunning)

  const checkStatus = useCallback(async () => {
    try {
      const { data } = await adminApi.getPurchaseSyncStatus()
      setSyncRunning(data.running)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    checkStatus()
    const id = setInterval(checkStatus, 5000)
    return () => clearInterval(id)
  }, [checkStatus])

  useEffect(() => {
    if (prevSyncRunning.current && !syncRunning) {
      onSyncFinished()
    }
    prevSyncRunning.current = syncRunning
  }, [syncRunning, onSyncFinished])

  return syncRunning
}
