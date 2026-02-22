import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { formatCents, parseEuroToCents, centsToEuroInput } from '@/lib/utils'
import { VariantTable } from '@/components/admin/VariantTable'
import { Loader2, ChevronDown, ChevronUp, Link } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import { useUiStore } from '@/stores/uiStore'
import type { Product, Category, Brand, AmazonSearchResult, ProductVariant } from '@/types'

interface ProductFormDialogProps {
  open: boolean
  onClose: () => void
  onSaved: () => void
  categories: Category[]
  brands: Brand[]
  product?: Product | null
}

const EMPTY_FORM = { name: '', category_id: '', price_euro: '', external_url: '', amazon_asin: '', brand: '', brand_id: '', description: '', sku: '', stock_quantity: '', stock_warning_level: '5' }

export function ProductFormDialog({ open, onClose, onSaved, categories, brands, product }: ProductFormDialogProps) {
  const isEdit = !!product
  const [form, setForm] = useState(EMPTY_FORM)
  const [loadedVariants, setLoadedVariants] = useState<ProductVariant[]>([])
  const [amazonUrl, setAmazonUrl] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<AmazonSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [loadingProduct, setLoadingProduct] = useState(false)
  const [showKeywordSearch, setShowKeywordSearch] = useState(false)
  const [saving, setSaving] = useState(false)

  const { addToast } = useUiStore()

  useEffect(() => {
    if (product) {
      setForm({
        name: product.name,
        category_id: product.category_id,
        price_euro: centsToEuroInput(product.price_cents),
        external_url: product.external_url,
        brand: product.brand || '',
        brand_id: product.brand_id || '',
        description: product.description || '',
        amazon_asin: product.amazon_asin || '',
        sku: product.sku || '',
        stock_quantity: product.stock_quantity != null ? String(product.stock_quantity) : '',
        stock_warning_level: String(product.stock_warning_level ?? 5),
      })
      setLoadedVariants(product.variants || [])
    } else if (open) {
      resetForm()
    }
  }, [product, open])

  const extractAsin = (url: string): string | null => {
    const match = url.match(/\/dp\/([A-Z0-9]{10})/) || url.match(/\/gp\/product\/([A-Z0-9]{10})/)
    return match ? match[1] : null
  }

  const applyAmazonData = (data: { name?: string; brand?: string | null; description?: string | null; feature_bullets?: string[]; price_cents?: number; url?: string | null; variants?: ProductVariant[] }, asin: string, fallbackName?: string) => {
    const matchedBrand = data.brand ? brands.find(b => b.name.toLowerCase() === data.brand!.toLowerCase()) : null
    setForm(f => ({
      ...f,
      name: data.name || fallbackName || f.name,
      brand: data.brand || f.brand,
      brand_id: matchedBrand?.id || f.brand_id,
      description: data.description || (data.feature_bullets?.length ? data.feature_bullets.join('\n') : '') || f.description,
      price_euro: data.price_cents ? centsToEuroInput(data.price_cents) : f.price_euro,
      amazon_asin: asin,
      external_url: data.url || f.external_url,
    }))
    setLoadedVariants(data.variants || [])
  }

  const handleAmazonUrl = async (url: string) => {
    setAmazonUrl(url)
    const asin = extractAsin(url)
    if (!asin) return
    setLoadingProduct(true)
    try {
      const { data } = await adminApi.amazonProduct(asin)
      applyAmazonData(data, asin)
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
      applyAmazonData(data, result.asin, result.name)
      if (!form.price_euro && result.price_cents) {
        setForm(f => ({ ...f, price_euro: centsToEuroInput(result.price_cents) }))
      }
      setSearchResults([])
      addToast({ title: 'Product data loaded' })
    } catch {
      addToast({ title: 'Failed to load', variant: 'destructive' })
    } finally {
      setLoadingProduct(false)
    }
  }

  const handleSave = async () => {
    if (!form.name.trim()) return addToast({ title: 'Name is required', variant: 'destructive' })
    if (!form.category_id) return addToast({ title: 'Category is required', variant: 'destructive' })
    if (isEdit && !form.category_id) return
    if (!isEdit && !form.brand_id) return addToast({ title: 'Brand is required', variant: 'destructive' })
    if (!isEdit && !form.external_url.trim()) return addToast({ title: 'URL is required', variant: 'destructive' })

    const priceCents = parseEuroToCents(form.price_euro)
    setSaving(true)
    try {
      const stockQuantity = form.stock_quantity === '' ? null : Number(form.stock_quantity)
      const stockWarningLevel = Number(form.stock_warning_level) || 5

      if (isEdit && product) {
        const selectedBrand = brands.find(b => b.id === form.brand_id)
        await adminApi.updateProduct(product.id, {
          name: form.name,
          category_id: form.category_id,
          price_cents: priceCents,
          external_url: form.external_url,
          brand: selectedBrand?.name || form.brand || undefined,
          brand_id: form.brand_id || undefined,
          description: form.description || undefined,
          sku: form.sku || null,
          stock_quantity: stockQuantity,
          stock_warning_level: stockWarningLevel,
        })
        addToast({ title: 'Product updated' })
      } else {
        await adminApi.createProduct({
          ...form,
          category_id: form.category_id,
          brand_id: form.brand_id,
          price_cents: priceCents,
          amazon_asin: form.amazon_asin || undefined,
          sku: form.sku || undefined,
          stock_quantity: stockQuantity ?? undefined,
          stock_warning_level: stockWarningLevel,
        })
        addToast({ title: 'Product created' })
      }
      resetForm()
      onSaved()
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  const resetForm = () => {
    setForm(EMPTY_FORM)
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

  const variants = isEdit ? (product?.variants || []) : loadedVariants

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) handleClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>{isEdit ? 'Edit Product' : 'Add Product'}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          {/* Amazon import — create mode only */}
          {!isEdit && (
            <>
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
            </>
          )}

          {/* Common form fields */}
          <Input placeholder="Product name *" value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} />
          <label htmlFor={`${isEdit ? 'edit' : 'create'}-brand`} className="sr-only">Brand</label>
          <select id={`${isEdit ? 'edit' : 'create'}-brand`} value={form.brand_id} onChange={(e) => setForm(f => ({ ...f, brand_id: e.target.value }))}
            className="w-full rounded-md border px-3 py-2 text-sm">
            <option value="">{isEdit ? 'Select brand' : 'Select brand *'}</option>
            {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <label htmlFor={`${isEdit ? 'edit' : 'create'}-category`} className="sr-only">Category</label>
          <select id={`${isEdit ? 'edit' : 'create'}-category`} value={form.category_id} onChange={(e) => setForm(f => ({ ...f, category_id: e.target.value }))}
            className="w-full rounded-md border px-3 py-2 text-sm">
            <option value="">Select category *</option>
            {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <Input placeholder="Price in EUR (e.g. 1,299.99)" value={form.price_euro} onChange={(e) => setForm(f => ({ ...f, price_euro: e.target.value }))} />
          <Input placeholder="External URL *" value={form.external_url} onChange={(e) => setForm(f => ({ ...f, external_url: e.target.value }))} />
          <label htmlFor={`${isEdit ? 'edit' : 'create'}-description`} className="sr-only">Description</label>
          <textarea id={`${isEdit ? 'edit' : 'create'}-description`} placeholder="Description" value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))}
            className="w-full rounded-md border px-3 py-2 text-sm min-h-[80px]" />

          {/* Stock / SKU fields */}
          <Input placeholder="SKU / Article number (optional)" value={form.sku} onChange={(e) => setForm(f => ({ ...f, sku: e.target.value }))} />
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label htmlFor={`${isEdit ? 'edit' : 'create'}-stock-qty`} className="text-xs text-[hsl(var(--muted-foreground))]">Stock quantity (empty = unlimited)</label>
              <Input id={`${isEdit ? 'edit' : 'create'}-stock-qty`} type="number" min="0" placeholder="Unlimited" value={form.stock_quantity}
                onChange={(e) => setForm(f => ({ ...f, stock_quantity: e.target.value }))} />
            </div>
            <div>
              <label htmlFor={`${isEdit ? 'edit' : 'create'}-stock-warn`} className="text-xs text-[hsl(var(--muted-foreground))]">Low stock warning level</label>
              <Input id={`${isEdit ? 'edit' : 'create'}-stock-warn`} type="number" min="0" value={form.stock_warning_level}
                onChange={(e) => setForm(f => ({ ...f, stock_warning_level: e.target.value }))} />
            </div>
          </div>

          {variants.length > 0 && <VariantTable variants={variants} />}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving || !form.name || !form.category_id || (!isEdit && (!form.brand_id || !form.external_url))}>
            {saving
              ? <><Loader2 className="h-4 w-4 animate-spin mr-1" /> {isEdit ? 'Saving...' : 'Creating...'}</>
              : (isEdit ? 'Save' : 'Create')
            }
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
