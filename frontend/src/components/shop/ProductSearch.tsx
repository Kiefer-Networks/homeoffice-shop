import { useState, useEffect, useRef, useCallback } from 'react'
import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { useFilterStore } from '@/stores/filterStore'
import { productApi } from '@/services/productApi'
import { SEARCH_DEBOUNCE_MS } from '@/lib/constants'
import type { SearchSuggestion } from '@/types'

const SEARCH_TIPS = [
  { label: '"quotes"', desc: 'Exact phrase match' },
  { label: 'OR', desc: 'Match either term' },
  { label: '-exclude', desc: 'Exclude a term' },
]

const SUGGESTION_DEBOUNCE_MS = 300

export function ProductSearch() {
  const { q, setFilter } = useFilterStore()
  const [local, setLocal] = useState(q)
  const [showTips, setShowTips] = useState(false)
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(-1)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const suggestionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

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

  // Fetch suggestions with debounce
  const fetchSuggestions = useCallback((value: string) => {
    if (suggestionTimerRef.current) clearTimeout(suggestionTimerRef.current)

    if (value.trim().length < 2) {
      setSuggestions([])
      setShowSuggestions(false)
      return
    }

    suggestionTimerRef.current = setTimeout(async () => {
      // Cancel any in-flight request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      const controller = new AbortController()
      abortControllerRef.current = controller

      try {
        const { data } = await productApi.getSearchSuggestions(value)
        if (!controller.signal.aborted) {
          setSuggestions(data)
          setShowSuggestions(data.length > 0)
          setActiveSuggestionIndex(-1)
        }
      } catch {
        // Ignore aborted requests and errors
        if (!controller.signal.aborted) {
          setSuggestions([])
          setShowSuggestions(false)
        }
      }
    }, SUGGESTION_DEBOUNCE_MS)
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (suggestionTimerRef.current) clearTimeout(suggestionTimerRef.current)
      if (abortControllerRef.current) abortControllerRef.current.abort()
    }
  }, [])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowTips(false)
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setLocal(value)
    setShowTips(false)
    fetchSuggestions(value)
  }

  const handleSuggestionClick = (suggestion: SearchSuggestion) => {
    setLocal(suggestion.name)
    setFilter('q', suggestion.name)
    setShowSuggestions(false)
    setSuggestions([])
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setShowSuggestions(false)
      setShowTips(false)
      return
    }

    if (!showSuggestions || suggestions.length === 0) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveSuggestionIndex((prev) =>
        prev < suggestions.length - 1 ? prev + 1 : 0
      )
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveSuggestionIndex((prev) =>
        prev > 0 ? prev - 1 : suggestions.length - 1
      )
    } else if (e.key === 'Enter' && activeSuggestionIndex >= 0) {
      e.preventDefault()
      handleSuggestionClick(suggestions[activeSuggestionIndex])
    }
  }

  const handleFocus = () => {
    if (!local) {
      setShowTips(true)
    } else if (suggestions.length > 0) {
      setShowSuggestions(true)
    }
  }

  return (
    <div className="relative" ref={wrapperRef}>
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[hsl(var(--muted-foreground))]" />
      <Input
        type="search"
        placeholder="Search products, brands, categories..."
        value={local}
        onChange={handleInputChange}
        onFocus={handleFocus}
        onKeyDown={handleKeyDown}
        className="pl-10"
        role="combobox"
        aria-expanded={showSuggestions}
        aria-autocomplete="list"
        aria-controls="search-suggestions-list"
        aria-activedescendant={
          activeSuggestionIndex >= 0
            ? `suggestion-${activeSuggestionIndex}`
            : undefined
        }
      />

      {/* Autocomplete suggestions dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <div
          id="search-suggestions-list"
          role="listbox"
          className="absolute top-full left-0 right-0 mt-1 z-50 rounded-md border bg-[hsl(var(--background))] shadow-md overflow-hidden"
        >
          {suggestions.map((suggestion, index) => (
            <button
              key={suggestion.id}
              id={`suggestion-${index}`}
              role="option"
              aria-selected={index === activeSuggestionIndex}
              className={`w-full flex items-center gap-3 px-3 py-2 text-sm text-left transition-colors
                ${index === activeSuggestionIndex
                  ? 'bg-[hsl(var(--accent))] text-[hsl(var(--accent-foreground))]'
                  : 'hover:bg-[hsl(var(--accent))] hover:text-[hsl(var(--accent-foreground))]'
                }`}
              onMouseDown={(e) => {
                e.preventDefault()
                handleSuggestionClick(suggestion)
              }}
            >
              {suggestion.image_url ? (
                <img
                  src={suggestion.image_url}
                  alt=""
                  className="w-8 h-8 object-contain rounded flex-shrink-0"
                />
              ) : (
                <div className="w-8 h-8 rounded bg-[hsl(var(--muted))] flex-shrink-0" />
              )}
              <span className="truncate">{suggestion.name}</span>
            </button>
          ))}
        </div>
      )}

      {/* Search tips shown when input is empty and focused */}
      {showTips && !showSuggestions && (
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
