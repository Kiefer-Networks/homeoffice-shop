import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { useUiStore } from '@/stores/uiStore'
import { adminApi } from '@/services/adminApi'
import { productApi } from '@/services/productApi'
import { formatCents } from '@/lib/utils'
import { Plus, Search, RefreshCcw, Loader2 } from 'lucide-react'
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

export function AdminProductsPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', category_id: '', price_cents: 0, external_url: '', amazon_asin: '', brand: '', description: '' })
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<AmazonSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [loadingProduct, setLoadingProduct] = useState(false)
  const { addToast } = useUiStore()

  useEffect(() => {
    const params = new URLSearchParams()
    if (search) params.set('q', search)
    params.set('per_page', '100')
    productApi.search(params).then(({ data }) => setProducts(data.items))
    productApi.getCategories().then(({ data }) => setCategories(data))
  }, [search])

  const handleAmazonSearch = async () => {
    if (!searchQuery) return
    setSearching(true)
    setSearchResults([])
    try {
      const { data } = await adminApi.amazonSearch(searchQuery)
      setSearchResults(data)
      if (data.length === 0) {
        addToast({ title: 'No results found' })
      }
    } catch {
      addToast({ title: 'Search failed', variant: 'destructive' })
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
        price_cents: data.price_cents || result.price_cents || f.price_cents,
        amazon_asin: result.asin,
        external_url: data.url || result.url || f.external_url,
      }))
      setSearchResults([])
      addToast({ title: 'Product data loaded' })
    } catch {
      addToast({ title: 'Failed to load product details', variant: 'destructive' })
    } finally {
      setLoadingProduct(false)
    }
  }

  const handleCreate = async () => {
    try {
      await adminApi.createProduct({
        ...form,
        category_id: form.category_id,
        price_cents: Number(form.price_cents),
        amazon_asin: form.amazon_asin || undefined,
      })
      setShowCreate(false)
      setForm({ name: '', category_id: '', price_cents: 0, external_url: '', amazon_asin: '', brand: '', description: '' })
      setSearchResults([])
      setSearchQuery('')
      const params = new URLSearchParams(); params.set('per_page', '100')
      productApi.search(params).then(({ data }) => setProducts(data.items))
      addToast({ title: 'Product created' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const toggleActive = async (product: Product) => {
    try {
      if (product.is_active) {
        await adminApi.deactivateProduct(product.id)
      } else {
        await adminApi.activateProduct(product.id)
      }
      setProducts(prev => prev.map(p => p.id === product.id ? { ...p, is_active: !p.is_active } : p))
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const redownloadImages = async (id: string) => {
    try {
      await adminApi.redownloadImages(id)
      addToast({ title: 'Images re-downloaded' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Products</h1>
        <Button onClick={() => setShowCreate(true)}><Plus className="h-4 w-4 mr-1" /> Add Product</Button>
      </div>

      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <Input placeholder="Search products..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" />
      </div>

      <div className="space-y-2">
        {products.map((p) => (
          <Card key={p.id}>
            <CardContent className="flex items-center justify-between p-4">
              <div>
                <div className="font-medium">{p.name}</div>
                <div className="text-sm text-[hsl(var(--muted-foreground))]">{p.brand} {p.amazon_asin && `(${p.amazon_asin})`}</div>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-bold">{formatCents(p.price_cents)}</span>
                <Badge variant={p.is_active ? 'success' : 'secondary'}>{p.is_active ? 'Active' : 'Inactive'}</Badge>
                <Button size="sm" variant="outline" onClick={() => toggleActive(p)}>
                  {p.is_active ? 'Deactivate' : 'Activate'}
                </Button>
                {p.amazon_asin && (
                  <Button size="sm" variant="ghost" onClick={() => redownloadImages(p.id)}>
                    <RefreshCcw className="h-3 w-3" />
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Add Product</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="flex gap-2">
              <Input placeholder="Search Amazon (EAN, name, etc.)" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAmazonSearch()} />
              <Button variant="outline" onClick={handleAmazonSearch} disabled={searching}>
                {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Search'}
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
                        {r.rating && ` | ${r.rating}*`}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}

            {loadingProduct && (
              <div className="flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))]">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading product details...
              </div>
            )}

            <Input placeholder="Product Name *" value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} />
            <Input placeholder="Brand" value={form.brand} onChange={(e) => setForm(f => ({ ...f, brand: e.target.value }))} />
            <select value={form.category_id} onChange={(e) => setForm(f => ({ ...f, category_id: e.target.value }))}
              className="w-full rounded-md border px-3 py-2 text-sm">
              <option value="">Select Category *</option>
              {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <Input type="number" placeholder="Price (cents)" value={form.price_cents || ''} onChange={(e) => setForm(f => ({ ...f, price_cents: parseInt(e.target.value) || 0 }))} />
            <Input placeholder="External URL *" value={form.external_url} onChange={(e) => setForm(f => ({ ...f, external_url: e.target.value }))} />
            <textarea placeholder="Description" value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))}
              className="w-full rounded-md border px-3 py-2 text-sm min-h-[80px]" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={!form.name || !form.category_id || !form.external_url}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
