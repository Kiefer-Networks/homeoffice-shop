import { useCallback, useEffect, useState } from 'react'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { adminApi } from '@/services/adminApi'
import { getErrorMessage } from '@/lib/error'
import { useUiStore } from '@/stores/uiStore'
import {
  Download, ChevronRight, Search, X,
  Monitor, Smartphone, Tablet, Globe,
} from 'lucide-react'
import type { AuditLogEntry } from '@/types'

const PER_PAGE = 30

// ---------------------------------------------------------------------------
// Time formatting – date on top, time below
// ---------------------------------------------------------------------------
function formatTimestamp(iso: string) {
  const d = new Date(iso)
  const date = d.toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' })
  const time = d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  return { date, time }
}

// ---------------------------------------------------------------------------
// Action – subtle colored dot + text
// ---------------------------------------------------------------------------
function actionDotColor(action: string): string {
  if (action.startsWith('auth.login_blocked') || action.startsWith('admin.hibob.')) return 'bg-red-500'
  if (action.startsWith('auth.')) return 'bg-blue-500'
  if (action.startsWith('admin.order.')) return 'bg-purple-500'
  if (action.startsWith('admin.product.')) return 'bg-green-500'
  if (action.startsWith('admin.user.')) return 'bg-amber-500'
  if (action.startsWith('admin.budget') || action.startsWith('admin.budget_rule') || action.startsWith('admin.budget_override')) return 'bg-cyan-500'
  if (action.startsWith('admin.audit.')) return 'bg-gray-400'
  return 'bg-gray-500'
}

// ---------------------------------------------------------------------------
// User-Agent parser
// ---------------------------------------------------------------------------
interface ParsedUA { browser: string; os: string; device: 'desktop' | 'mobile' | 'tablet' }

function parseUserAgent(ua: string): ParsedUA {
  let browser = 'Unknown'
  let os = 'Unknown'
  let device: ParsedUA['device'] = 'desktop'

  // OS detection
  if (/iPad/.test(ua)) { os = 'iPadOS'; device = 'tablet' }
  else if (/iPhone/.test(ua)) { os = 'iOS'; device = 'mobile' }
  else if (/Android/.test(ua)) {
    os = 'Android'
    device = /Mobile/.test(ua) ? 'mobile' : 'tablet'
  }
  else if (/Mac OS X/.test(ua)) { os = 'macOS' }
  else if (/Windows/.test(ua)) { os = 'Windows' }
  else if (/Linux/.test(ua)) { os = 'Linux' }
  else if (/CrOS/.test(ua)) { os = 'ChromeOS' }

  // Browser detection (order matters – check specific before generic)
  if (/Edg\//.test(ua)) browser = 'Edge'
  else if (/OPR\/|Opera/.test(ua)) browser = 'Opera'
  else if (/Firefox\//.test(ua)) browser = 'Firefox'
  else if (/Chrome\//.test(ua) && !/Edg\//.test(ua)) browser = 'Chrome'
  else if (/Safari\//.test(ua) && !/Chrome\//.test(ua)) browser = 'Safari'

  return { browser, os, device }
}

function DeviceIcon({ device }: { device: ParsedUA['device'] }) {
  const cls = 'h-3.5 w-3.5 text-[hsl(var(--muted-foreground))]'
  if (device === 'mobile') return <Smartphone className={cls} />
  if (device === 'tablet') return <Tablet className={cls} />
  return <Monitor className={cls} />
}

// Map browser names to small SVG icon paths (inline for perf, no external deps)
function BrowserIcon({ browser }: { browser: string }) {
  const cls = 'h-3.5 w-3.5 text-[hsl(var(--muted-foreground))]'

  // Chrome
  if (browser === 'Chrome') return (
    <svg className={cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="4" />
      <line x1="21.17" y1="8" x2="12" y2="8" /><line x1="3.95" y1="6.06" x2="8.54" y2="14" />
      <line x1="10.88" y1="21.94" x2="15.46" y2="14" />
    </svg>
  )

  // Firefox
  if (browser === 'Firefox') return (
    <svg className={cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M17 12a5 5 0 0 0-5-5c-1 0-2 .3-2.8.8" />
      <path d="M12 7v5l3 3" />
    </svg>
  )

  // Safari
  if (browser === 'Safari') return (
    <svg className={cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
    </svg>
  )

  return <Globe className={cls} />
}

// ---------------------------------------------------------------------------
// Detail value renderer – clean key-value table
// ---------------------------------------------------------------------------
function flattenDetails(obj: Record<string, unknown>, prefix = ''): { key: string; value: string }[] {
  const rows: { key: string; value: string }[] = []
  for (const [k, v] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${k}` : k
    if (v === null || v === undefined) {
      rows.push({ key: fullKey, value: '-' })
    } else if (Array.isArray(v)) {
      if (v.length === 0) {
        rows.push({ key: fullKey, value: '(empty)' })
      } else if (v.every(item => typeof item !== 'object' || item === null)) {
        rows.push({ key: fullKey, value: v.map(String).join(', ') })
      } else {
        v.forEach((item, i) => {
          if (typeof item === 'object' && item !== null) {
            rows.push(...flattenDetails(item as Record<string, unknown>, `${fullKey}[${i}]`))
          } else {
            rows.push({ key: `${fullKey}[${i}]`, value: String(item) })
          }
        })
      }
    } else if (typeof v === 'object') {
      rows.push(...flattenDetails(v as Record<string, unknown>, fullKey))
    } else {
      rows.push({ key: fullKey, value: String(v) })
    }
  }
  return rows
}

function isUuid(s: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s)
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export function AdminAuditLogPage() {
  const { addToast } = useUiStore()

  const [logs, setLogs] = useState<AuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 300)
  const [resourceTypeFilter, setResourceTypeFilter] = useState('')
  const [actionFilter, setActionFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [availableFilters, setAvailableFilters] = useState<{ actions: string[]; resource_types: string[] }>({ actions: [], resource_types: [] })

  useEffect(() => {
    adminApi.getAuditFilters()
      .then(({ data }) => setAvailableFilters(data))
      .catch(() => {})
  }, [])

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
              {loading && logs.length === 0 ? (
                <tbody>
                  {[...Array(6)].map((_, i) => (
                    <tr key={i} className="border-b border-[hsl(var(--border))]">
                      <td colSpan={6} className="px-4 py-4">
                        <div className="h-5 bg-[hsl(var(--muted))] rounded animate-pulse" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              ) : logs.length === 0 ? (
                <tbody>
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
                      No audit log entries found.
                    </td>
                  </tr>
                </tbody>
              ) : (
                logs.map((log) => {
                  const { date, time } = formatTimestamp(log.created_at)
                  const isExpanded = expandedId === log.id
                  return (
                    <tbody key={log.id}>
                        <tr
                          className={`border-b border-[hsl(var(--border))] hover:bg-[hsl(var(--muted)/0.5)] cursor-pointer transition-colors ${isExpanded ? 'bg-[hsl(var(--muted)/0.3)]' : ''}`}
                          onClick={() => setExpandedId(isExpanded ? null : log.id)}
                        >
                          <td className="px-4 py-3 whitespace-nowrap">
                            <div className="font-mono text-xs font-medium">{time}</div>
                            <div className="text-[10px] text-[hsl(var(--muted-foreground))]">{date}</div>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className="text-sm">{log.user_email || log.user_id.slice(0, 8) + '\u2026'}</span>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${actionDotColor(log.action)}`} />
                              <span className="font-mono text-xs">{log.action}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className="text-xs font-medium bg-[hsl(var(--muted))] px-1.5 py-0.5 rounded">{log.resource_type}</span>
                            {log.resource_id && (
                              <span className="text-[hsl(var(--muted-foreground))] ml-1.5 font-mono text-[11px]">
                                {log.resource_id.slice(0, 8)}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap font-mono text-xs text-[hsl(var(--muted-foreground))]">
                            {log.ip_address || '-'}
                          </td>
                          <td className="px-2 py-3">
                            <ChevronRight
                              className={`h-4 w-4 text-[hsl(var(--muted-foreground))] transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`}
                            />
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr className="border-b border-[hsl(var(--border))]">
                            <td colSpan={6} className="p-0">
                              <div className="px-6 py-4 bg-[hsl(var(--muted)/0.15)]">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                  {/* Left: Metadata */}
                                  <div>
                                    <h4 className="text-xs font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))] mb-2">Metadata</h4>
                                    <table className="w-full text-xs">
                                      <tbody>
                                        {log.resource_id && (
                                          <tr className="border-b border-[hsl(var(--border)/0.5)]">
                                            <td className="py-1.5 pr-3 text-[hsl(var(--muted-foreground))] whitespace-nowrap font-medium">Resource ID</td>
                                            <td className="py-1.5 font-mono">{log.resource_id}</td>
                                          </tr>
                                        )}
                                        {log.correlation_id && (
                                          <tr className="border-b border-[hsl(var(--border)/0.5)]">
                                            <td className="py-1.5 pr-3 text-[hsl(var(--muted-foreground))] whitespace-nowrap font-medium">Correlation ID</td>
                                            <td className="py-1.5 font-mono">{log.correlation_id}</td>
                                          </tr>
                                        )}
                                        <tr className="border-b border-[hsl(var(--border)/0.5)]">
                                          <td className="py-1.5 pr-3 text-[hsl(var(--muted-foreground))] whitespace-nowrap font-medium">User ID</td>
                                          <td className="py-1.5 font-mono">{log.user_id}</td>
                                        </tr>
                                        {log.ip_address && (
                                          <tr className="border-b border-[hsl(var(--border)/0.5)]">
                                            <td className="py-1.5 pr-3 text-[hsl(var(--muted-foreground))] whitespace-nowrap font-medium">IP Address</td>
                                            <td className="py-1.5 font-mono">{log.ip_address}</td>
                                          </tr>
                                        )}
                                        {log.user_agent && (() => {
                                          const ua = parseUserAgent(log.user_agent)
                                          return (
                                            <tr className="border-b border-[hsl(var(--border)/0.5)]">
                                              <td className="py-1.5 pr-3 text-[hsl(var(--muted-foreground))] whitespace-nowrap font-medium">Client</td>
                                              <td className="py-1.5">
                                                <div className="flex items-center gap-3">
                                                  <span className="inline-flex items-center gap-1">
                                                    <BrowserIcon browser={ua.browser} />
                                                    <span>{ua.browser}</span>
                                                  </span>
                                                  <span className="inline-flex items-center gap-1">
                                                    <DeviceIcon device={ua.device} />
                                                    <span>{ua.os}</span>
                                                  </span>
                                                </div>
                                              </td>
                                            </tr>
                                          )
                                        })()}
                                        {log.user_agent && (
                                          <tr>
                                            <td className="py-1.5 pr-3 text-[hsl(var(--muted-foreground))] whitespace-nowrap font-medium align-top">User Agent</td>
                                            <td className="py-1.5 text-[hsl(var(--muted-foreground))] break-all text-[11px] leading-relaxed">{log.user_agent}</td>
                                          </tr>
                                        )}
                                      </tbody>
                                    </table>
                                  </div>

                                  {/* Right: Details */}
                                  <div>
                                    <h4 className="text-xs font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))] mb-2">Details</h4>
                                    {log.details && Object.keys(log.details).length > 0 ? (
                                      <table className="w-full text-xs">
                                        <tbody>
                                          {flattenDetails(log.details).map(({ key, value }, i) => (
                                            <tr key={i} className="border-b border-[hsl(var(--border)/0.5)]">
                                              <td className="py-1.5 pr-3 text-[hsl(var(--muted-foreground))] whitespace-nowrap font-medium align-top">{key}</td>
                                              <td className={`py-1.5 break-all ${isUuid(value) ? 'font-mono' : ''}`}>{value}</td>
                                            </tr>
                                          ))}
                                        </tbody>
                                      </table>
                                    ) : (
                                      <p className="text-xs text-[hsl(var(--muted-foreground))]">No details recorded.</p>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                    </tbody>
                  )
                })
              )}
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
