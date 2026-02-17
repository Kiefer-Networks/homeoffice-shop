import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { adminApi } from '@/services/adminApi'
import { formatDate } from '@/lib/utils'
import { Download } from 'lucide-react'
import type { AuditLogEntry } from '@/types'

export function AdminAuditLogPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [actionFilter, setActionFilter] = useState('')

  useEffect(() => {
    const params: Record<string, string | number> = { page, per_page: 50 }
    if (actionFilter) params.action = actionFilter
    adminApi.listAuditLogs(params).then(({ data }) => { setLogs(data.items); setTotal(data.total) })
  }, [page, actionFilter])

  const handleExport = async () => {
    const { data } = await adminApi.exportAuditCsv()
    const url = window.URL.createObjectURL(new Blob([data]))
    const a = document.createElement('a'); a.href = url; a.download = 'audit_log.csv'; a.click()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Audit Log ({total})</h1>
        <Button variant="outline" onClick={handleExport}><Download className="h-4 w-4 mr-1" /> Export CSV</Button>
      </div>
      <Input placeholder="Filter by action (e.g. auth.login)" value={actionFilter}
        onChange={(e) => { setActionFilter(e.target.value); setPage(1) }} className="mb-4" />
      <div className="space-y-2">
        {logs.map((log) => (
          <Card key={log.id}>
            <CardContent className="p-3">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-sm font-mono font-medium">{log.action}</span>
                  <span className="text-xs text-[hsl(var(--muted-foreground))] ml-2">{log.resource_type}{log.resource_id && `:${log.resource_id.slice(0, 8)}`}</span>
                </div>
                <span className="text-xs text-[hsl(var(--muted-foreground))]">{formatDate(log.created_at)}</span>
              </div>
              <div className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                {log.user_email || log.user_id.slice(0, 8)} {log.ip_address && `from ${log.ip_address}`}
              </div>
              {log.details && <pre className="text-xs bg-gray-50 p-2 mt-1 rounded overflow-x-auto">{JSON.stringify(log.details, null, 2)}</pre>}
            </CardContent>
          </Card>
        ))}
      </div>
      {total > 50 && (
        <div className="flex justify-center gap-2 mt-4">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Previous</Button>
          <span className="text-sm self-center">Page {page}</span>
          <Button size="sm" variant="outline" disabled={page * 50 >= total} onClick={() => setPage(p => p + 1)}>Next</Button>
        </div>
      )}
    </div>
  )
}
