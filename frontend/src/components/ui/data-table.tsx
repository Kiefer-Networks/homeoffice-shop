import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

export interface Column<T> {
  header: string | ReactNode
  accessor: (row: T) => ReactNode
  className?: string // applied to both th and td (e.g. "text-right", "text-center")
}

export interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  rowKey: (row: T) => string
  emptyMessage?: string
  onRowClick?: (row: T) => void
  children?: ReactNode // rendered inside CardContent after the table (e.g. Pagination)
}

export function DataTable<T>({
  columns,
  data,
  rowKey,
  emptyMessage = 'No data found.',
  onRowClick,
  children,
}: DataTableProps<T>) {
  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                {columns.map((col, i) => (
                  <th
                    key={i}
                    className={cn(
                      'text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]',
                      col.className,
                    )}
                  >
                    {col.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.length === 0 ? (
                <tr>
                  <td
                    colSpan={columns.length}
                    className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]"
                  >
                    {emptyMessage}
                  </td>
                </tr>
              ) : (
                data.map((row) => (
                  <tr
                    key={rowKey(row)}
                    className={cn(
                      'border-b border-[hsl(var(--border))] hover:bg-[hsl(var(--muted)/0.5)]',
                      onRowClick && 'cursor-pointer',
                    )}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                  >
                    {columns.map((col, i) => (
                      <td key={i} className={cn('px-4 py-3', col.className)}>
                        {col.accessor(row)}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {children}
      </CardContent>
    </Card>
  )
}
