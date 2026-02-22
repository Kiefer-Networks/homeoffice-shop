import { useEffect, useState, useCallback } from 'react'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Pagination } from '@/components/ui/Pagination'
import { useUiStore } from '@/stores/uiStore'
import { adminApi } from '@/services/adminApi'
import { productApi } from '@/services/productApi'
import { formatCents } from '@/lib/utils'
import { Plus, Search } from 'lucide-react'
import { DEFAULT_PAGE_SIZE, SEARCH_DEBOUNCE_MS } from '@/lib/constants'
import { getErrorMessage } from '@/lib/error'
import { ProductRefreshModal } from '@/components/admin/ProductRefreshModal'
import { ProductTable } from '@/components/admin/ProductTable'
import { ProductFormDialog } from '@/components/admin/ProductFormDialog'
import type { SortKey } from '@/components/admin/ProductTable'
import type { Product, Category, Brand } from '@/types'

export function AdminProductsPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState<SortKey>('name_asc')
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, SEARCH_DEBOUNCE_MS)
  const [categoryFilter, setCategoryFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [editProduct, setEditProduct] = useState<Product | null>(null)
  const [archiveFilter, setArchiveFilter] = useState<'live' | 'archived'>('live')

  const [brands, setBrands] = useState<Brand[]>([])
  const [refreshProduct, setRefreshProduct] = useState<Product | null>(null)

  const { addToast } = useUiStore()

  useEffect(() => {
    productApi.getCategories().then(({ data }) => setCategories(data)).catch(() => {})
    adminApi.listBrands().then(({ data }) => setBrands(data)).catch(() => {})
  }, [])

  const load = useCallback(() => {
    const params = new URLSearchParams()
    params.set('page', String(page))
    params.set('per_page', String(DEFAULT_PAGE_SIZE))
    params.set('sort', sort)
    if (debouncedSearch) params.set('q', debouncedSearch)
    if (categoryFilter) params.set('category', categoryFilter)
    if (archiveFilter === 'archived') {
      params.set('archived_only', 'true')
    } else {
      params.set('include_archived', 'false')
    }
    productApi.search(params).then(({ data }) => {
      setProducts(data.items)
      setTotal(data.total)
    })
  }, [page, sort, debouncedSearch, categoryFilter, archiveFilter])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [debouncedSearch, categoryFilter, sort, archiveFilter])

  const totalPages = Math.max(1, Math.ceil(total / DEFAULT_PAGE_SIZE))

  const filteredProducts = activeFilter
    ? products.filter(p => activeFilter === 'active' ? p.is_active : !p.is_active)
    : products

  const toggleActive = async (product: Product) => {
    try {
      if (product.is_active) {
        await adminApi.deactivateProduct(product.id)
      } else {
        await adminApi.activateProduct(product.id)
      }
      load()
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const handleArchive = async (product: Product) => {
    try {
      await adminApi.archiveProduct(product.id)
      load()
      addToast({ title: 'Product archived' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const handleRestore = async (product: Product) => {
    try {
      await adminApi.restoreProduct(product.id)
      load()
      addToast({ title: 'Product restored' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const openRefresh = (product: Product, e: React.MouseEvent) => {
    e.stopPropagation()
    setRefreshProduct(product)
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Products ({total})</h1>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4 mr-1" /> Add Product
        </Button>
      </div>

      {/* Search */}
      <div className="mb-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input placeholder="Search by name, brand..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10 max-w-sm" />
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-4 items-center">
        {/* Category filter */}
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}
          aria-label="Filter by category"
          className="h-9 rounded-md border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-3 text-sm">
          <option value="">All Categories</option>
          {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        {/* Archive filter */}
        <div className="flex gap-1">
          <Button size="sm" variant={archiveFilter === 'live' ? 'default' : 'outline'} onClick={() => setArchiveFilter('live')}>Live</Button>
          <Button size="sm" variant={archiveFilter === 'archived' ? 'default' : 'outline'} onClick={() => setArchiveFilter('archived')}>Archived</Button>
        </div>

        {/* Active filter */}
        {archiveFilter === 'live' && (
          <div className="flex gap-1">
            {[
              { label: 'All', value: '' },
              { label: 'Active', value: 'active' },
              { label: 'Inactive', value: 'inactive' },
            ].map((a) => (
              <Button key={a.value} size="sm" variant={activeFilter === a.value ? 'default' : 'outline'} onClick={() => setActiveFilter(a.value)}>
                {a.label}
              </Button>
            ))}
          </div>
        )}
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <ProductTable
            products={filteredProducts}
            categories={categories}
            sort={sort}
            onSort={setSort}
            onEdit={setEditProduct}
            onActivate={toggleActive}
            onDeactivate={toggleActive}
            onArchive={handleArchive}
            onRestore={handleRestore}
            onRefresh={openRefresh}
            formatCents={formatCents}
            archiveFilter={archiveFilter}
          />

          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <ProductFormDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSaved={() => { setShowCreate(false); load() }}
        categories={categories}
        brands={brands}
      />

      {/* Edit Dialog */}
      <ProductFormDialog
        product={editProduct}
        open={!!editProduct}
        onClose={() => setEditProduct(null)}
        onSaved={() => { setEditProduct(null); load() }}
        categories={categories}
        brands={brands}
      />

      {/* Refresh Modal */}
      {refreshProduct && (
        <ProductRefreshModal
          open={!!refreshProduct}
          onClose={() => setRefreshProduct(null)}
          onApplied={() => { setRefreshProduct(null); load() }}
          productId={refreshProduct.id}
          productName={refreshProduct.name}
        />
      )}

    </div>
  )
}
