import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { adminApi } from '@/services/adminApi'
import { formatDate } from '@/lib/utils'
import type { HiBobSyncLog } from '@/types'

export function AdminSyncLogPage() {
  const [logs, setLogs] = useState<HiBobSyncLog[]>([])

  useEffect(() => { adminApi.getSyncLogs().then(({ data }) => setLogs(data.items)) }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">HiBob Sync Log</h1>
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
        {logs.length === 0 && <p className="text-[hsl(var(--muted-foreground))]">No sync logs yet.</p>}
      </div>
    </div>
  )
}
