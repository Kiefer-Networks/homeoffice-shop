import { useCallback, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { adminApi } from '@/services/adminApi'
import { formatDate } from '@/lib/utils'
import { getErrorMessage } from '@/lib/error'
import { useUiStore } from '@/stores/uiStore'
import { Download, ChevronRight, Search, X } from 'lucide-react'
import type { AuditLogEntry } from '@/types'

const PER_PAGE = 30

function getActionBadgeVariant(action: string): 'default' | 'secondary' | 'success' | 'warning' | 'outline' | 'destructive' {
  if (action.startsWith('auth.')) return 'default'
  if (action.startsWith('admin.order.')) return 'secondary'
  if (action.startsWith('admin.product.')) return 'success'
  if (action.startsWith('admin.user.')) return 'warning'
  if (action.startsWith('admin.budget') || action.startsWith('admin.budget_rule') || action.startsWith('admin.budget_override')) return 'outline'
  if (action.startsWith('admin.hibob.')) return 'destructive'
  return 'secondary'
}

function renderDetailValue(value: unknown, depth = 0): React.ReactNode {
  if (value === null || value === undefined) return <span className="text-[hsl(var(--muted-foreground))]">null</span>
  if (typeof value === 'boolean') return <span>{value ? 'true' : 'false'}</span>
  if (typeof value === 'number') return <span>{value}</span>
  if (typeof value === 'string') {
    const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
    if (isUuid) return <span className="font-mono text-xs">{value}</span>
    return <span>{value}</span>
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-[hsl(var(--muted-foreground))]">[]</span>
    return (
      <ul className="list-disc ml-4 mt-1">
        {value.map((item, i) => (
          <li key={i} className="text-xs">{renderDetailValue(item, depth + 1)}</li>
        ))}
      </ul>
    )
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    if (entries.length === 0) return <span className="text-[hsl(var(--muted-foreground))]]">{'{}'}</span>
    return (
      <div className={depth > 0 ? 'ml-4 mt-1' : ''}>
        {entries.map(([k, v]) => (
          <div key={k} className="text-xs py-0.5">
            <span className="font-semibold">{k}:</span>{' '}
            {typeof v === 'object' && v !== null ? renderDetailValue(v, depth + 1) : renderDetailValue(v, depth + 1)}
          </div>
        ))}
      </div>
    )
  }
  return <span>{String(value)}</span>
}

export function AdminAuditLogPage() {
  const { addToast } = useUiStore()

  const [logs, setLogs] = useState<AuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [resourceTypeFilter, setResourceTypeFilter] = useState('')
  const [actionFilter, setActionFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [availableFilters, setAvailableFilters] = useState<{ actions: string[]; resource_types: string[] }>({ actions: [], resource_types: [] })

  // Load filter options
  useEffect(() => {
    adminApi.getAuditFilters()
      .then(({ data }) => setAvailableFilters(data))
      .catch(() => {})
  }, [])

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  // Reset page when filters change
  useEffect(() => { setPage(1) }, [debouncedSearch, resourceTypeFilter, actionFilter, dateFrom, dateTo])

  const loadLogs = useCallback(() => {
    setLoading(true)
    const params: Record<string, string | number> = { page, per_page: PER_PAGE }
    if (debouncedSearch) params.q = debouncedSearch
    if (resourceTypeFilter) params.resource_type = resourceTypeFilter
    if (actionFilter) params.action = actionFilter
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    adminApi.listAuditLogs(params)
      .then(({ data }) => { setLogs(data.items); setTotal(data.total) })
      .catch((err: unknown) => addToast({ title: 'Error loading audit logs', description: getErrorMessage(err), variant: 'destructive' }))
      .finally(() => setLoading(false))
  }, [page, debouncedSearch, resourceTypeFilter, actionFilter, dateFrom, dateTo, addToast])

  useEffect(() => { loadLogs() }, [loadLogs])

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE))

  const hasActiveFilters = search || resourceTypeFilter || actionFilter || dateFrom || dateTo

  const handleReset = () => {
    setSearch('')
    setResourceTypeFilter('')
    setActionFilter('')
    setDateFrom('')
    setDateTo('')
  }

  const handleExport = async () => {
    const params: Record<string, string> = {}
    if (debouncedSearch) params.q = debouncedSearch
    if (resourceTypeFilter) params.resource_type = resourceTypeFilter
    if (actionFilter) params.action = actionFilter
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    try {
      const { data } = await adminApi.exportAuditCsv(params)
      const url = window.URL.createObjectURL(new Blob([data]))
      const a = document.createElement('a'); a.href = url; a.download = 'audit_log.csv'; a.click()
      window.URL.revokeObjectURL(url)
    } catch (err: unknown) {
      addToast({ title: 'Export failed', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Audit Log ({total.toLocaleString()})</h1>
        <Button variant="outline" onClick={handleExport}>
          <Download className="h-4 w-4 mr-1" /> Export CSV
        </Button>
      </div>

      {/* Filter Bar */}
      <Card className="mb-4">
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[hsl(var(--muted-foreground))]" />
              <Input
                placeholder="Search..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <select
              value={resourceTypeFilter}
              onChange={(e) => setResourceTypeFilter(e.target.value)}
              className="h-9 rounded-md border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-3 text-sm"
              aria-label="Filter by resource type"
            >
              <option value="">All Resources</option>
              {availableFilters.resource_types.map((rt) => (
                <option key={rt} value={rt}>{rt}</option>
              ))}
            </select>
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="h-9 rounded-md border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-3 text-sm"
              aria-label="Filter by action"
            >
              <option value="">All Actions</option>
              {availableFilters.actions.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-[160px]"
              aria-label="Date from"
            />
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-[160px]"
              aria-label="Date to"
            />
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={handleReset} className="h-9">
                <X className="h-4 w-4 mr-1" /> Reset
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Time</th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">User</th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Action</th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Resource</th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">IP</th>
                  <th className="w-10 px-2 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {loading && logs.length === 0 ? (
                  [...Array(6)].map((_, i) => (
                    <tr key={i} className="border-b border-[hsl(var(--border))]">
                      <td colSpan={6} className="px-4 py-4">
                        <div className="h-5 bg-gray-100 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))
                ) : logs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
                      No audit log entries found.
                    </td>
                  </tr>
                ) : (
                  logs.map((log) => (
                    <>
                      <tr
                        key={log.id}
                        className="border-b border-[hsl(var(--border))] hover:bg-[hsl(var(--muted)/0.5)] cursor-pointer"
                        onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                      >
                        <td className="px-4 py-3 whitespace-nowrap font-mono text-xs">
                          {formatDate(log.created_at)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          {log.user_email || log.user_id.slice(0, 8) + '...'}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={getActionBadgeVariant(log.action)}>{log.action}</Badge>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span>{log.resource_type}</span>
                          {log.resource_id && (
                            <span className="text-[hsl(var(--muted-foreground))] ml-1 font-mono text-xs">
                              {log.resource_id.slice(0, 8)}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap font-mono text-xs text-[hsl(var(--muted-foreground))]">
                          {log.ip_address || '-'}
                        </td>
                        <td className="px-2 py-3">
                          <ChevronRight
                            className={`h-4 w-4 text-[hsl(var(--muted-foreground))] transition-transform ${expandedId === log.id ? 'rotate-90' : ''}`}
                          />
                        </td>
                      </tr>
                      {expandedId === log.id && (
                        <tr key={`${log.id}-detail`} className="border-b border-[hsl(var(--border))]">
                          <td colSpan={6} className="px-6 py-4 bg-[hsl(var(--muted)/0.3)]">
                            <div className="space-y-2 text-sm">
                              {log.resource_id && (
                                <div className="text-xs">
                                  <span className="font-semibold">Resource ID:</span>{' '}
                                  <span className="font-mono">{log.resource_id}</span>
                                </div>
                              )}
                              {log.correlation_id && (
                                <div className="text-xs">
                                  <span className="font-semibold">Correlation ID:</span>{' '}
                                  <span className="font-mono">{log.correlation_id}</span>
                                </div>
                              )}
                              {log.user_agent && (
                                <div className="text-xs">
                                  <span className="font-semibold">User Agent:</span>{' '}
                                  <span className="truncate inline-block max-w-[600px] align-bottom" title={log.user_agent}>
                                    {log.user_agent.length > 80 ? log.user_agent.slice(0, 80) + '...' : log.user_agent}
                                  </span>
                                </div>
                              )}
                              {log.details && Object.keys(log.details).length > 0 && (
                                <div className="text-xs">
                                  <span className="font-semibold">Details:</span>
                                  {renderDetailValue(log.details)}
                                </div>
                              )}
                              {(!log.details || Object.keys(log.details).length === 0) && !log.user_agent && !log.correlation_id && !log.resource_id && (
                                <div className="text-xs text-[hsl(var(--muted-foreground))]">No additional details.</div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 mt-2">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Previous</Button>
          <span className="text-sm text-[hsl(var(--muted-foreground))]">Page {page} of {totalPages}</span>
          <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next</Button>
        </div>
      )}
    </div>
  )
}
