import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { SortHeader } from '@/components/ui/SortHeader'
import {
  RefreshCcw, Archive, ArchiveRestore, Pencil, Eye, EyeOff,
} from 'lucide-react'
import type { Product, Category } from '@/types'

export type SortKey = 'name_asc' | 'name_desc' | 'price_asc' | 'price_desc' | 'newest'

interface ProductTableProps {
  products: Product[]
  categories: Category[]
  sort: SortKey
  onSort: (k: SortKey) => void
  onEdit: (p: Product) => void
  onActivate: (p: Product) => void
  onDeactivate: (p: Product) => void
  onArchive: (p: Product) => void
  onRestore: (p: Product) => void
  onRefresh: (p: Product, e: React.MouseEvent) => void
  formatCents: (cents: number) => string
  archiveFilter: 'live' | 'archived'
}

export function ProductTable({
  products, categories, sort, onSort, onEdit,
  onActivate, onDeactivate, onArchive, onRestore, onRefresh,
  formatCents, archiveFilter,
}: ProductTableProps) {
  const apiUrl = import.meta.env.VITE_API_URL || ''

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
            <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))] w-12"></th>
            <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
              <SortHeader label="Name" ascKey="name_asc" descKey="name_desc" currentSort={sort} onSort={onSort} />
            </th>
            <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Category</th>
            <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
              <SortHeader label="Price" ascKey="price_asc" descKey="price_desc" currentSort={sort} onSort={onSort} />
            </th>
            <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Status</th>
            <th className="text-right px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Actions</th>
          </tr>
        </thead>
        <tbody>
          {products.map((p) => {
            const cat = categories.find(c => c.id === p.category_id)
            const imgUrl = p.image_url ? `${apiUrl}${p.image_url}` : null
            return (
              <tr key={p.id} className="border-b border-[hsl(var(--border))] hover:bg-[hsl(var(--muted)/0.5)]">
                <td className="px-4 py-3">
                  {imgUrl ? (
                    <img src={imgUrl} alt="" className="h-10 w-10 rounded object-contain bg-gray-50" />
                  ) : (
                    <div className="h-10 w-10 rounded bg-[hsl(var(--muted))] flex items-center justify-center text-xs font-medium">
                      {p.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium">
                    {p.name}
                    {p.variants && p.variants.length > 0 && (
                      <Badge variant="secondary" className="ml-2 text-xs">{p.variants.length} variants</Badge>
                    )}
                  </div>
                  <div className="text-xs text-[hsl(var(--muted-foreground))]">
                    {p.brand}{p.amazon_asin && ` · ${p.amazon_asin}`}
                  </div>
                </td>
                <td className="px-4 py-3">{cat?.name || '—'}</td>
                <td className="px-4 py-3 font-medium">{formatCents(p.price_cents)}</td>
                <td className="px-4 py-3">
                  <Badge variant={p.is_active ? 'success' : 'secondary'}>
                    {p.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex justify-end gap-1">
                    {archiveFilter === 'archived' ? (
                      <Button size="sm" variant="outline" onClick={() => onRestore(p)}>
                        <ArchiveRestore className="h-3 w-3 mr-1" /> Restore
                      </Button>
                    ) : (
                      <>
                        <Button size="sm" variant="outline" aria-label="Edit product" onClick={() => onEdit(p)}>
                          <Pencil className="h-3 w-3" />
                        </Button>
                        <Button size="sm" variant="outline" aria-label={p.is_active ? 'Deactivate product' : 'Activate product'} onClick={() => p.is_active ? onDeactivate(p) : onActivate(p)}>
                          {p.is_active ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                        </Button>
                        {p.amazon_asin && (
                          <Button size="sm" variant="ghost" aria-label="Refresh price" onClick={(e) => onRefresh(p, e)}>
                            <RefreshCcw className="h-3 w-3" />
                          </Button>
                        )}
                        <Button size="sm" variant="outline" aria-label="Archive product" className="text-orange-600 hover:text-orange-700" onClick={() => onArchive(p)}>
                          <Archive className="h-3 w-3" />
                        </Button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            )
          })}
          {products.length === 0 && (
            <tr>
              <td colSpan={6} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
                No products found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
