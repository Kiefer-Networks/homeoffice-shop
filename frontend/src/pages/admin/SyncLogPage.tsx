import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { adminApi } from '@/services/adminApi'
import { formatDate } from '@/lib/utils'
import type { HiBobSyncLog, HiBobPurchaseSyncLog } from '@/types'

export function AdminSyncLogPage() {
  const [logs, setLogs] = useState<HiBobSyncLog[]>([])
  const [purchaseLogs, setPurchaseLogs] = useState<HiBobPurchaseSyncLog[]>([])
  const [tab, setTab] = useState<'employee' | 'purchase'>('employee')

  useEffect(() => {
    adminApi.getSyncLogs().then(({ data }) => setLogs(data.items))
    adminApi.getPurchaseSyncLogs().then(({ data }) => setPurchaseLogs(data.items))
  }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Sync Log</h1>

      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setTab('employee')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === 'employee'
              ? 'bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]'
              : 'bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))]'
          }`}
        >
          Employee Sync
        </button>
        <button
          onClick={() => setTab('purchase')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === 'purchase'
              ? 'bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]'
              : 'bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))]'
          }`}
        >
          Purchase Sync
        </button>
      </div>

      {tab === 'employee' && (
        <div className="space-y-2">
          {logs.map((log) => (
            <Card key={log.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Badge variant={log.status === 'completed' ? 'success' : log.status === 'failed' ? 'destructive' : 'warning'}>
                      {log.status}
                    </Badge>
                    <span className="text-sm ml-2">{formatDate(log.started_at)}</span>
                  </div>
                  <div className="text-sm text-[hsl(var(--muted-foreground))]">
                    Synced: {log.employees_synced} | Created: {log.employees_created} | Updated: {log.employees_updated} | Deactivated: {log.employees_deactivated}
                  </div>
                </div>
                {log.error_message && <p className="text-sm text-red-600 mt-2">{log.error_message}</p>}
              </CardContent>
            </Card>
          ))}
          {logs.length === 0 && <p className="text-[hsl(var(--muted-foreground))]">No employee sync logs yet.</p>}
        </div>
      )}

      {tab === 'purchase' && (
        <div className="space-y-2">
          {purchaseLogs.map((log) => (
            <Card key={log.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Badge variant={log.status === 'completed' ? 'success' : log.status === 'failed' ? 'destructive' : 'warning'}>
                      {log.status}
                    </Badge>
                    <span className="text-sm ml-2">{formatDate(log.started_at)}</span>
                  </div>
                  <div className="text-sm text-[hsl(var(--muted-foreground))]">
                    Found: {log.entries_found} | Matched: {log.matched} | Auto-Adjusted: {log.auto_adjusted} | Pending: {log.pending_review}
                  </div>
                </div>
                {log.error_message && <p className="text-sm text-red-600 mt-2">{log.error_message}</p>}
              </CardContent>
            </Card>
          ))}
          {purchaseLogs.length === 0 && <p className="text-[hsl(var(--muted-foreground))]">No purchase sync logs yet.</p>}
        </div>
      )}
    </div>
  )
}
