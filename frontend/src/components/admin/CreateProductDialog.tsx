import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { formatCents, parseEuroToCents, centsToEuroInput } from '@/lib/utils'
import { Loader2, ChevronDown, ChevronUp, Link } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import { useUiStore } from '@/stores/uiStore'
import type { Category, Brand, AmazonSearchResult, ProductVariant } from '@/types'

interface CreateProductDialogProps {
  open: boolean
  onClose: () => void
  onCreated: () => void
  categories: Category[]
  brands: Brand[]
}

export function CreateProductDialog({ open, onClose, onCreated, categories, brands }: CreateProductDialogProps) {
  const [form, setForm] = useState({ name: '', category_id: '', price_euro: '', external_url: '', amazon_asin: '', brand: '', brand_id: '', description: '' })
  const [loadedVariants, setLoadedVariants] = useState<ProductVariant[]>([])
  const [amazonUrl, setAmazonUrl] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<AmazonSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [loadingProduct, setLoadingProduct] = useState(false)
  const [showKeywordSearch, setShowKeywordSearch] = useState(false)
  const [creating, setCreating] = useState(false)

  const { addToast } = useUiStore()

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
      const matchedBrand = data.brand ? brands.find(b => b.name.toLowerCase() === data.brand!.toLowerCase()) : null
      setForm(f => ({
        ...f,
        name: data.name || f.name,
        brand: data.brand || f.brand,
        brand_id: matchedBrand?.id || f.brand_id,
        description: data.description || (data.feature_bullets?.length ? data.feature_bullets.join('\n') : '') || f.description,
        price_euro: data.price_cents ? centsToEuroInput(data.price_cents) : f.price_euro,
        amazon_asin: asin,
        external_url: data.url || f.external_url,
      }))
      setLoadedVariants(data.variants || [])
      addToast({ title: 'Product data loaded' })
    } catch {
      addToast({ title: 'Failed to load', variant: 'destructive' })
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
      if (data.length === 0) addToast({ title: 'No results' })
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
      const matchedBrand = data.brand ? brands.find(b => b.name.toLowerCase() === data.brand!.toLowerCase()) : null
      setForm(f => ({
        ...f,
        name: data.name || result.name || f.name,
        brand: data.brand || f.brand,
        brand_id: matchedBrand?.id || f.brand_id,
        description: data.description || (data.feature_bullets?.length ? data.feature_bullets.join('\n') : '') || f.description,
        price_euro: data.price_cents ? centsToEuroInput(data.price_cents) : (result.price_cents ? centsToEuroInput(result.price_cents) : f.price_euro),
        amazon_asin: result.asin,
        external_url: data.url || result.url || f.external_url,
      }))
      setLoadedVariants(data.variants || [])
      setSearchResults([])
      addToast({ title: 'Product data loaded' })
    } catch {
      addToast({ title: 'Failed to load', variant: 'destructive' })
    } finally {
      setLoadingProduct(false)
    }
  }

  const handleCreate = async () => {
    if (!form.name.trim()) return addToast({ title: 'Name is required', variant: 'destructive' })
    if (!form.category_id) return addToast({ title: 'Category is required', variant: 'destructive' })
    if (!form.brand_id) return addToast({ title: 'Brand is required', variant: 'destructive' })
    if (!form.external_url.trim()) return addToast({ title: 'URL is required', variant: 'destructive' })
    const priceCents = parseEuroToCents(form.price_euro)
    setCreating(true)
    try {
      await adminApi.createProduct({
        ...form,
        category_id: form.category_id,
        brand_id: form.brand_id,
        price_cents: priceCents,
        amazon_asin: form.amazon_asin || undefined,
      })
      resetForm()
      onCreated()
      addToast({ title: 'Product created' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setCreating(false)
    }
  }

  const resetForm = () => {
    setForm({ name: '', category_id: '', price_euro: '', external_url: '', amazon_asin: '', brand: '', brand_id: '', description: '' })
    setLoadedVariants([])
    setAmazonUrl('')
    setSearchResults([])
    setSearchQuery('')
    setShowKeywordSearch(false)
  }

  const handleClose = () => {
    resetForm()
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) handleClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Add Product</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div className="relative">
            <Link className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input placeholder="Paste Amazon URL" value={amazonUrl}
              onChange={(e) => handleAmazonUrl(e.target.value)} className="pl-10" />
          </div>

          {loadingProduct && (
            <div className="flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))]">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading product data...
            </div>
          )}

          <button type="button" onClick={() => setShowKeywordSearch(!showKeywordSearch)}
            className="flex items-center gap-1 text-sm text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]">
            {showKeywordSearch ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            Amazon Keyword Search
          </button>

          {showKeywordSearch && (
            <>
              <div className="flex gap-2">
                <Input placeholder="EAN, Name, etc." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
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
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </>
          )}

          <Input placeholder="Product name *" value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} />
          <select value={form.brand_id} onChange={(e) => setForm(f => ({ ...f, brand_id: e.target.value }))}
            className="w-full rounded-md border px-3 py-2 text-sm">
            <option value="">Select brand *</option>
            {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <select value={form.category_id} onChange={(e) => setForm(f => ({ ...f, category_id: e.target.value }))}
            className="w-full rounded-md border px-3 py-2 text-sm">
            <option value="">Select category *</option>
            {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <Input placeholder="Price in EUR (e.g. 1,299.99)" value={form.price_euro} onChange={(e) => setForm(f => ({ ...f, price_euro: e.target.value }))} />
          <Input placeholder="External URL *" value={form.external_url} onChange={(e) => setForm(f => ({ ...f, external_url: e.target.value }))} />
          <textarea placeholder="Description" value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))}
            className="w-full rounded-md border px-3 py-2 text-sm min-h-[80px]" />

          {loadedVariants.length > 0 && (
            <div>
              <h4 className="font-medium text-sm mb-2">Variants ({loadedVariants.length})</h4>
              <div className="border rounded-md max-h-48 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b bg-[hsl(var(--muted))]">
                      <th className="text-left px-2 py-1">Group</th>
                      <th className="text-left px-2 py-1">Value</th>
                      <th className="text-left px-2 py-1">ASIN</th>
                      <th className="text-right px-2 py-1">Price</th>
                    </tr>
                  </thead>
                  <tbody>
                    {loadedVariants.map((v) => (
                      <tr key={v.asin} className="border-b last:border-b-0">
                        <td className="px-2 py-1 capitalize">{v.group}</td>
                        <td className="px-2 py-1">{v.value}</td>
                        <td className="px-2 py-1 font-mono">{v.asin}</td>
                        <td className="px-2 py-1 text-right">{v.price_cents > 0 ? formatCents(v.price_cents) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>Cancel</Button>
          <Button onClick={handleCreate} disabled={creating || !form.name || !form.category_id || !form.brand_id || !form.external_url}>
            {creating ? <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Creating...</> : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
