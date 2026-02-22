import { Button } from '@/components/ui/button'

interface PaginationProps {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, totalPages, onPageChange }: PaginationProps) {
  if (totalPages <= 1) return null

  const handlePageChange = (newPage: number) => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
    onPageChange(newPage)
  }

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-[hsl(var(--border))]">
      <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => handlePageChange(page - 1)}>
        Previous
      </Button>
      <span className="text-sm text-[hsl(var(--muted-foreground))]">
        Page {page} of {totalPages}
      </span>
      <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => handlePageChange(page + 1)}>
        Next
      </Button>
    </div>
  )
}
