// ---------------------------------------------------------------------------
// Time formatting - date on top, time below
// ---------------------------------------------------------------------------
export function formatTimestamp(iso: string): { date: string; time: string } {
  const d = new Date(iso)
  const date = d.toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' })
  const time = d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  return { date, time }
}

// ---------------------------------------------------------------------------
// Action - subtle colored dot + text
// ---------------------------------------------------------------------------
export function actionDotColor(action: string): string {
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
export interface ParsedUA { browser: string; os: string; device: 'desktop' | 'mobile' | 'tablet' }

export function parseUserAgent(ua: string): ParsedUA {
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

  // Browser detection (order matters - check specific before generic)
  if (/Edg\//.test(ua)) browser = 'Edge'
  else if (/OPR\/|Opera/.test(ua)) browser = 'Opera'
  else if (/Firefox\//.test(ua)) browser = 'Firefox'
  else if (/Chrome\//.test(ua) && !/Edg\//.test(ua)) browser = 'Chrome'
  else if (/Safari\//.test(ua) && !/Chrome\//.test(ua)) browser = 'Safari'

  return { browser, os, device }
}

// ---------------------------------------------------------------------------
// Detail value renderer - clean key-value table
// ---------------------------------------------------------------------------
export function flattenDetails(obj: Record<string, unknown>, prefix = ''): { key: string; value: string }[] {
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
