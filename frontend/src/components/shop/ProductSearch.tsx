import { useState, useEffect, useRef } from 'react'
import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { useFilterStore } from '@/stores/filterStore'
import { SEARCH_DEBOUNCE_MS } from '@/lib/constants'

const SEARCH_TIPS = [
  { label: '"quotes"', desc: 'Exact phrase match' },
  { label: 'OR', desc: 'Match either term' },
  { label: '-exclude', desc: 'Exclude a term' },
]

export function ProductSearch() {
  const { q, setFilter } = useFilterStore()
  const [local, setLocal] = useState(q)
  const [showTips, setShowTips] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)

  // Sync local state when store changes externally (e.g. URL sync, reset)
  useEffect(() => {
    setLocal(q)
  }, [q])

  // Debounce: push to store after 300ms of inactivity
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      if (local !== q) {
        setFilter('q', local)
      }
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [local])

  // Close tips when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowTips(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <div className="relative" ref={wrapperRef}>
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[hsl(var(--muted-foreground))]" />
      <Input
        type="search"
        placeholder="Search products, brands, categories..."
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onFocus={() => { if (!local) setShowTips(true) }}
        onBlur={() => setTimeout(() => setShowTips(false), 150)}
        className="pl-10"
      />
      {showTips && (
        <div className="absolute top-full left-0 right-0 mt-1 z-50 rounded-md border bg-[hsl(var(--background))] p-3 text-sm shadow-md">
          <p className="font-medium mb-2 text-popover-foreground">Search tips</p>
          <ul className="space-y-1">
            {SEARCH_TIPS.map((tip) => (
              <li key={tip.label} className="flex gap-2">
                <code className="rounded bg-muted px-1 py-0.5 text-xs font-mono">{tip.label}</code>
                <span className="text-muted-foreground">{tip.desc}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
