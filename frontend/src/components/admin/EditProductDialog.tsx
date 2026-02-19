import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { parseEuroToCents, centsToEuroInput } from '@/lib/utils'
import { VariantTable } from '@/components/admin/VariantTable'
import { Loader2 } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import { useUiStore } from '@/stores/uiStore'
import type { Product, Category, Brand } from '@/types'

interface EditProductDialogProps {
  product: Product | null
  open: boolean
  onClose: () => void
  onUpdated: () => void
  categories: Category[]
  brands: Brand[]
}

export function EditProductDialog({ product, open, onClose, onUpdated, categories, brands }: EditProductDialogProps) {
  const [editForm, setEditForm] = useState({ name: '', category_id: '', price_euro: '', external_url: '', brand: '', brand_id: '', description: '', is_active: true })
  const [updating, setUpdating] = useState(false)

  const { addToast } = useUiStore()

  useEffect(() => {
    if (product) {
      setEditForm({
        name: product.name,
        category_id: product.category_id,
        price_euro: centsToEuroInput(product.price_cents),
        external_url: product.external_url,
        brand: product.brand || '',
        brand_id: product.brand_id || '',
        description: product.description || '',
        is_active: product.is_active,
      })
    }
  }, [product])

  const handleUpdate = async () => {
    if (!product) return
    if (!editForm.name.trim()) return addToast({ title: 'Name is required', variant: 'destructive' })
    if (!editForm.category_id) return addToast({ title: 'Category is required', variant: 'destructive' })
    const priceCents = parseEuroToCents(editForm.price_euro)
    setUpdating(true)
    try {
      const selectedBrand = brands.find(b => b.id === editForm.brand_id)
      await adminApi.updateProduct(product.id, {
        name: editForm.name,
        category_id: editForm.category_id,
        price_cents: priceCents,
        external_url: editForm.external_url,
        brand: selectedBrand?.name || editForm.brand || undefined,
        brand_id: editForm.brand_id || undefined,
        description: editForm.description || undefined,
        is_active: editForm.is_active,
      })
      onClose()
      onUpdated()
      addToast({ title: 'Product updated' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setUpdating(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Edit Product</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <Input placeholder="Product name *" value={editForm.name} onChange={(e) => setEditForm(f => ({ ...f, name: e.target.value }))} />
          <select value={editForm.brand_id} onChange={(e) => setEditForm(f => ({ ...f, brand_id: e.target.value }))}
            className="w-full rounded-md border px-3 py-2 text-sm">
            <option value="">Select brand</option>
            {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <select value={editForm.category_id} onChange={(e) => setEditForm(f => ({ ...f, category_id: e.target.value }))}
            className="w-full rounded-md border px-3 py-2 text-sm">
            <option value="">Select category *</option>
            {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <Input placeholder="Price in EUR (e.g. 1,299.99)" value={editForm.price_euro} onChange={(e) => setEditForm(f => ({ ...f, price_euro: e.target.value }))} />
          <Input placeholder="External URL *" value={editForm.external_url} onChange={(e) => setEditForm(f => ({ ...f, external_url: e.target.value }))} />
          <textarea placeholder="Description" value={editForm.description} onChange={(e) => setEditForm(f => ({ ...f, description: e.target.value }))}
            className="w-full rounded-md border px-3 py-2 text-sm min-h-[80px]" />

          {product?.variants && <VariantTable variants={product.variants} />}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleUpdate} disabled={updating}>
            {updating ? <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Saving...</> : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
