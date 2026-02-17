import { useEffect, useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { useUiStore } from '@/stores/uiStore'
import { adminApi } from '@/services/adminApi'
import { productApi } from '@/services/productApi'
import { formatCents, parseEuroToCents, centsToEuroInput } from '@/lib/utils'
import {
  Plus, Search, RefreshCcw, Loader2, ChevronDown, ChevronUp, Link,
  Trash2, Pencil, Eye, EyeOff,
} from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import type { Product, Category } from '@/types'

interface AmazonSearchResult {
  name: string
  asin: string
  price_cents: number
  image_url: string | null
  url: string | null
  rating: number | null
  reviews: number | null
}

const PER_PAGE = 20

type SortKey = 'name_asc' | 'name_desc' | 'price_asc' | 'price_desc' | 'newest'

function SortHeader({
  label, sortKey, currentSort, onSort,
}: {
  label: string; sortKey: SortKey; currentSort: SortKey; onSort: (k: SortKey) => void
}) {
  const isNameSort = sortKey === 'name_asc'
  const isPriceSort = sortKey === 'price_asc'
  const isActive = isNameSort
    ? currentSort === 'name_asc' || currentSort === 'name_desc'
    : isPriceSort
      ? currentSort === 'price_asc' || currentSort === 'price_desc'
      : currentSort === sortKey

  const handleClick = () => {
    if (isNameSort) onSort(currentSort === 'name_asc' ? 'name_desc' : 'name_asc')
    else if (isPriceSort) onSort(currentSort === 'price_asc' ? 'price_desc' : 'price_asc')
    else onSort(sortKey)
  }

  const isDesc = currentSort === 'name_desc' || currentSort === 'price_desc'
  return (
    <button onClick={handleClick} className="inline-flex items-center gap-1 hover:text-[hsl(var(--foreground))] transition-colors">
      {label}
      {isActive && (isDesc ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />)}
    </button>
  )
}

export function AdminProductsPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState<SortKey>('name_asc')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [editProduct, setEditProduct] = useState<Product | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<Product | null>(null)

  // Create form
  const [form, setForm] = useState({ name: '', category_id: '', price_euro: '', external_url: '', amazon_asin: '', brand: '', description: '' })
  const [amazonUrl, setAmazonUrl] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<AmazonSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [loadingProduct, setLoadingProduct] = useState(false)
  const [showKeywordSearch, setShowKeywordSearch] = useState(false)

  // Edit form
  const [editForm, setEditForm] = useState({ name: '', category_id: '', price_euro: '', external_url: '', brand: '', description: '', is_active: true })

  const { addToast } = useUiStore()

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  useEffect(() => {
    productApi.getCategories().then(({ data }) => setCategories(data))
  }, [])

  const load = useCallback(() => {
    const params = new URLSearchParams()
    params.set('page', String(page))
    params.set('per_page', String(PER_PAGE))
    params.set('sort', sort)
    if (debouncedSearch) params.set('q', debouncedSearch)
    if (categoryFilter) params.set('category', categoryFilter)
    // We need to fetch all (active+inactive) for admin
    productApi.search(params).then(({ data }) => {
      setProducts(data.items)
      setTotal(data.total)
    })
  }, [page, sort, debouncedSearch, categoryFilter, activeFilter])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [debouncedSearch, categoryFilter, activeFilter, sort])

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE))

  const filteredProducts = activeFilter
    ? products.filter(p => activeFilter === 'active' ? p.is_active : !p.is_active)
    : products

  // Amazon URL ASIN extraction
  const extractAsin = (url: string): string | null => {
    const match = url.match(/\/dp\/([A-Z0-9]{10})/) || url.match(/\/gp\/product\/([A-Z0-9]{10})/)
    return match ? match[1] : null
  }

  const handleAmazonUrl = async (url: string) => {
    setAmazonUrl(url)
    const asin = extractAsin(url)
    if (!asin) return
    setLoadingProduct(true)
    try {
      const { data } = await adminApi.amazonProduct(asin)
      setForm(f => ({
        ...f,
        name: data.name || f.name,
        brand: data.brand || f.brand,
        description: data.description || (data.feature_bullets?.length ? data.feature_bullets.join('\n') : '') || f.description,
        price_euro: data.price_cents ? centsToEuroInput(data.price_cents) : f.price_euro,
        amazon_asin: asin,
        external_url: data.url || f.external_url,
      }))
      addToast({ title: 'Produktdaten geladen' })
    } catch {
      addToast({ title: 'Fehler beim Laden', variant: 'destructive' })
    } finally {
      setLoadingProduct(false)
    }
  }

  const handleAmazonSearch = async () => {
    if (!searchQuery) return
    setSearching(true)
    setSearchResults([])
    try {
      const { data } = await adminApi.amazonSearch(searchQuery)
      setSearchResults(data)
      if (data.length === 0) addToast({ title: 'Keine Ergebnisse' })
    } catch {
      addToast({ title: 'Suche fehlgeschlagen', variant: 'destructive' })
    } finally {
      setSearching(false)
    }
  }

  const handleSelectResult = async (result: AmazonSearchResult) => {
    setLoadingProduct(true)
    try {
      const { data } = await adminApi.amazonProduct(result.asin)
      setForm(f => ({
        ...f,
        name: data.name || result.name || f.name,
        brand: data.brand || f.brand,
        description: data.description || (data.feature_bullets?.length ? data.feature_bullets.join('\n') : '') || f.description,
        price_euro: data.price_cents ? centsToEuroInput(data.price_cents) : (result.price_cents ? centsToEuroInput(result.price_cents) : f.price_euro),
        amazon_asin: result.asin,
        external_url: data.url || result.url || f.external_url,
      }))
      setSearchResults([])
      addToast({ title: 'Produktdaten geladen' })
    } catch {
      addToast({ title: 'Fehler beim Laden', variant: 'destructive' })
    } finally {
      setLoadingProduct(false)
    }
  }

  const handleCreate = async () => {
    if (!form.name.trim()) return addToast({ title: 'Name ist erforderlich', variant: 'destructive' })
    if (!form.category_id) return addToast({ title: 'Kategorie ist erforderlich', variant: 'destructive' })
    if (!form.external_url.trim()) return addToast({ title: 'URL ist erforderlich', variant: 'destructive' })
    const priceCents = parseEuroToCents(form.price_euro)
    try {
      await adminApi.createProduct({
        ...form,
        category_id: form.category_id,
        price_cents: priceCents,
        amazon_asin: form.amazon_asin || undefined,
      })
      setShowCreate(false)
      setForm({ name: '', category_id: '', price_euro: '', external_url: '', amazon_asin: '', brand: '', description: '' })
      setAmazonUrl('')
      setSearchResults([])
      setSearchQuery('')
      setShowKeywordSearch(false)
      load()
      addToast({ title: 'Produkt erstellt' })
    } catch (err: unknown) {
      addToast({ title: 'Fehler', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const openEdit = (p: Product) => {
    setEditProduct(p)
    setEditForm({
      name: p.name,
      category_id: p.category_id,
      price_euro: centsToEuroInput(p.price_cents),
      external_url: p.external_url,
      brand: p.brand || '',
      description: p.description || '',
      is_active: p.is_active,
    })
  }

  const handleUpdate = async () => {
    if (!editProduct) return
    if (!editForm.name.trim()) return addToast({ title: 'Name ist erforderlich', variant: 'destructive' })
    if (!editForm.category_id) return addToast({ title: 'Kategorie ist erforderlich', variant: 'destructive' })
    const priceCents = parseEuroToCents(editForm.price_euro)
    try {
      await adminApi.updateProduct(editProduct.id, {
        name: editForm.name,
        category_id: editForm.category_id,
        price_cents: priceCents,
        external_url: editForm.external_url,
        brand: editForm.brand || undefined,
        description: editForm.description || undefined,
        is_active: editForm.is_active,
      })
      setEditProduct(null)
      load()
      addToast({ title: 'Produkt aktualisiert' })
    } catch (err: unknown) {
      addToast({ title: 'Fehler', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const toggleActive = async (product: Product) => {
    try {
      if (product.is_active) {
        await adminApi.deactivateProduct(product.id)
      } else {
        await adminApi.activateProduct(product.id)
      }
      load()
    } catch (err: unknown) {
      addToast({ title: 'Fehler', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return
    try {
      await adminApi.deleteProduct(deleteConfirm.id)
      setDeleteConfirm(null)
      load()
      addToast({ title: 'Produkt gelöscht' })
    } catch (err: unknown) {
      addToast({ title: 'Fehler', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const redownloadImages = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await adminApi.redownloadImages(id)
      load()
      addToast({ title: 'Bilder neu geladen' })
    } catch (err: unknown) {
      addToast({ title: 'Fehler', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const apiUrl = import.meta.env.VITE_API_URL || ''

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Produkte ({total})</h1>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4 mr-1" /> Produkt anlegen
        </Button>
      </div>

      {/* Search */}
      <div className="mb-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input placeholder="Suche nach Name, Marke..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10 max-w-sm" />
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-4 items-center">
        {/* Category filter */}
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}
          className="h-9 rounded-md border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-3 text-sm">
          <option value="">Alle Kategorien</option>
          {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        {/* Active filter */}
        <div className="flex gap-1">
          {[
            { label: 'Alle', value: '' },
            { label: 'Aktiv', value: 'active' },
            { label: 'Inaktiv', value: 'inactive' },
          ].map((a) => (
            <Button key={a.value} size="sm" variant={activeFilter === a.value ? 'default' : 'outline'} onClick={() => setActiveFilter(a.value)}>
              {a.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))] w-12"></th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
                    <SortHeader label="Name" sortKey="name_asc" currentSort={sort} onSort={setSort} />
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Kategorie</th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
                    <SortHeader label="Preis" sortKey="price_asc" currentSort={sort} onSort={setSort} />
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Status</th>
                  <th className="text-right px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Aktionen</th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.map((p) => {
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
                        <div className="font-medium">{p.name}</div>
                        <div className="text-xs text-[hsl(var(--muted-foreground))]">
                          {p.brand}{p.amazon_asin && ` · ${p.amazon_asin}`}
                        </div>
                      </td>
                      <td className="px-4 py-3">{cat?.name || '—'}</td>
                      <td className="px-4 py-3 font-medium">{formatCents(p.price_cents)}</td>
                      <td className="px-4 py-3">
                        <Badge variant={p.is_active ? 'success' : 'secondary'}>
                          {p.is_active ? 'Aktiv' : 'Inaktiv'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-1">
                          <Button size="sm" variant="outline" onClick={() => openEdit(p)}>
                            <Pencil className="h-3 w-3" />
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => toggleActive(p)}>
                            {p.is_active ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                          </Button>
                          {p.amazon_asin && (
                            <Button size="sm" variant="ghost" onClick={(e) => redownloadImages(p.id, e)}>
                              <RefreshCcw className="h-3 w-3" />
                            </Button>
                          )}
                          <Button size="sm" variant="outline" className="text-red-600 hover:text-red-700" onClick={() => setDeleteConfirm(p)}>
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
                {filteredProducts.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
                      Keine Produkte gefunden.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-[hsl(var(--border))]">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
                Zurück
              </Button>
              <span className="text-sm text-[hsl(var(--muted-foreground))]">
                Seite {page} von {totalPages}
              </span>
              <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
                Weiter
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Produkt anlegen</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="relative">
              <Link className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input placeholder="Amazon URL einfügen" value={amazonUrl}
                onChange={(e) => handleAmazonUrl(e.target.value)} className="pl-10" />
            </div>

            {loadingProduct && (
              <div className="flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))]">
                <Loader2 className="h-4 w-4 animate-spin" /> Lade Produktdaten...
              </div>
            )}

            <button type="button" onClick={() => setShowKeywordSearch(!showKeywordSearch)}
              className="flex items-center gap-1 text-sm text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]">
              {showKeywordSearch ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              Amazon Keyword-Suche
            </button>

            {showKeywordSearch && (
              <>
                <div className="flex gap-2">
                  <Input placeholder="EAN, Name, etc." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAmazonSearch()} />
                  <Button variant="outline" onClick={handleAmazonSearch} disabled={searching}>
                    {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Suchen'}
                  </Button>
                </div>
                {searchResults.length > 0 && (
                  <div className="border rounded-md max-h-48 overflow-y-auto">
                    {searchResults.map((r) => (
                      <button key={r.asin} onClick={() => handleSelectResult(r)} disabled={loadingProduct}
                        className="w-full flex items-center gap-3 p-2 hover:bg-[hsl(var(--muted))] text-left border-b last:border-b-0">
                        {r.image_url && <img src={r.image_url} alt="" className="w-10 h-10 object-contain shrink-0" />}
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium truncate">{r.name}</div>
                          <div className="text-xs text-[hsl(var(--muted-foreground))]">
                            ASIN: {r.asin} {r.price_cents > 0 && `| ${formatCents(r.price_cents)}`}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}

            <Input placeholder="Produktname *" value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} />
            <Input placeholder="Marke" value={form.brand} onChange={(e) => setForm(f => ({ ...f, brand: e.target.value }))} />
            <select value={form.category_id} onChange={(e) => setForm(f => ({ ...f, category_id: e.target.value }))}
              className="w-full rounded-md border px-3 py-2 text-sm">
              <option value="">Kategorie wählen *</option>
              {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <Input placeholder="Preis in Euro (z.B. 1.299,99)" value={form.price_euro} onChange={(e) => setForm(f => ({ ...f, price_euro: e.target.value }))} />
            <Input placeholder="Externe URL *" value={form.external_url} onChange={(e) => setForm(f => ({ ...f, external_url: e.target.value }))} />
            <textarea placeholder="Beschreibung" value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))}
              className="w-full rounded-md border px-3 py-2 text-sm min-h-[80px]" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>Abbrechen</Button>
            <Button onClick={handleCreate} disabled={!form.name || !form.category_id || !form.external_url}>Erstellen</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={!!editProduct} onOpenChange={() => setEditProduct(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Produkt bearbeiten</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Input placeholder="Produktname *" value={editForm.name} onChange={(e) => setEditForm(f => ({ ...f, name: e.target.value }))} />
            <Input placeholder="Marke" value={editForm.brand} onChange={(e) => setEditForm(f => ({ ...f, brand: e.target.value }))} />
            <select value={editForm.category_id} onChange={(e) => setEditForm(f => ({ ...f, category_id: e.target.value }))}
              className="w-full rounded-md border px-3 py-2 text-sm">
              <option value="">Kategorie wählen *</option>
              {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <Input placeholder="Preis in Euro (z.B. 1.299,99)" value={editForm.price_euro} onChange={(e) => setEditForm(f => ({ ...f, price_euro: e.target.value }))} />
            <Input placeholder="Externe URL *" value={editForm.external_url} onChange={(e) => setEditForm(f => ({ ...f, external_url: e.target.value }))} />
            <textarea placeholder="Beschreibung" value={editForm.description} onChange={(e) => setEditForm(f => ({ ...f, description: e.target.value }))}
              className="w-full rounded-md border px-3 py-2 text-sm min-h-[80px]" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditProduct(null)}>Abbrechen</Button>
            <Button onClick={handleUpdate}>Speichern</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Produkt löschen?</DialogTitle></DialogHeader>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Soll <strong>{deleteConfirm?.name}</strong> wirklich gelöscht werden? Diese Aktion kann nicht rückgängig gemacht werden.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Abbrechen</Button>
            <Button variant="destructive" onClick={handleDelete}>Löschen</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
