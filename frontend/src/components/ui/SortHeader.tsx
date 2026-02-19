import { ChevronDown, ChevronUp } from 'lucide-react'

export function SortHeader<T extends string>({
  label,
  ascKey,
  descKey,
  currentSort,
  onSort,
}: {
  label: string
  ascKey: T
  descKey: T
  currentSort: T
  onSort: (key: T) => void
}) {
  const isAsc = currentSort === ascKey
  const isDesc = currentSort === descKey
  const handleClick = () => onSort(isAsc ? descKey : ascKey)
  return (
    <button
      onClick={handleClick}
      className="inline-flex items-center gap-1 hover:text-[hsl(var(--foreground))] transition-colors"
    >
      {label}
      {isAsc && <ChevronUp className="h-3 w-3" />}
      {isDesc && <ChevronDown className="h-3 w-3" />}
    </button>
  )
}
