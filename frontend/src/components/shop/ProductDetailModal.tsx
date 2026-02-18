import { useState, useEffect, useMemo } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { formatCents } from '@/lib/utils'
import { ShoppingCart, ExternalLink, ChevronLeft, ChevronRight } from 'lucide-react'
import { useCartStore } from '@/stores/cartStore'
import { useUiStore } from '@/stores/uiStore'
import { cartApi } from '@/services/cartApi'
import { getErrorMessage } from '@/lib/error'
import type { Product, ProductVariant } from '@/types'

interface Props {
  product: Product | null
  open: boolean
  onClose: () => void
  onRefreshCart: () => void
}

export function ProductDetailModal({ product, open, onClose, onRefreshCart }: Props) {
  const [currentImage, setCurrentImage] = useState(0)
  const [selectedVariant, setSelectedVariant] = useState<ProductVariant | null>(null)
  const { addToast } = useUiStore()
  const setCartOpen = useCartStore((s) => s.setOpen)

  const variants = product?.variants ?? []
  const hasVariants = variants.length > 0

  // Group variants by group name
  const variantGroups = useMemo(() => {
    const groups: Record<string, ProductVariant[]> = {}
    for (const v of variants) {
      if (!groups[v.group]) groups[v.group] = []
      groups[v.group].push(v)
    }
    return groups
  }, [variants])

  // Reset state when product changes
  useEffect(() => {
    setCurrentImage(0)
    if (hasVariants) {
      // Default: variant matching product ASIN, or the selected one, or first
      const match = variants.find(v => v.asin === product?.amazon_asin)
        || variants.find(v => v.is_selected)
        || variants[0]
      setSelectedVariant(match ?? null)
    } else {
      setSelectedVariant(null)
    }
  }, [product?.id])

  if (!product) return null

  const apiUrl = import.meta.env.VITE_API_URL || ''

  // Use variant image if selected and available
  const variantImageUrl = selectedVariant?.image_url || null
  const allImages = [
    variantImageUrl || (product.image_url ? `${apiUrl}${product.image_url}` : null),
    ...(product.image_gallery || []).map(url => `${apiUrl}${url}`),
  ].filter(Boolean) as string[]

  // Use variant price if selected
  const displayPrice = selectedVariant?.price_cents && selectedVariant.price_cents > 0
    ? selectedVariant.price_cents
    : product.price_cents

  const handleAddToCart = async () => {
    try {
      await cartApi.addItem(product.id, 1, selectedVariant?.asin)
      onRefreshCart()
      setCartOpen(true)
      onClose()
      const desc = selectedVariant?.value
        ? `${product.name} — ${selectedVariant.value}`
        : product.name
      addToast({ title: 'Added to cart', description: desc })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-lg">{product.name}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Image Gallery */}
          {allImages.length > 0 && (
            <div className="relative bg-gray-50 rounded-lg overflow-hidden">
              <div className="aspect-square flex items-center justify-center">
                <img
                  src={allImages[currentImage]}
                  alt={product.name}
                  className="max-h-full max-w-full object-contain p-4"
                />
              </div>
              {allImages.length > 1 && (
                <>
                  <button
                    onClick={() => setCurrentImage(i => (i - 1 + allImages.length) % allImages.length)}
                    className="absolute left-2 top-1/2 -translate-y-1/2 bg-white/80 rounded-full p-1 hover:bg-white shadow"
                  >
                    <ChevronLeft className="h-5 w-5" />
                  </button>
                  <button
                    onClick={() => setCurrentImage(i => (i + 1) % allImages.length)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 bg-white/80 rounded-full p-1 hover:bg-white shadow"
                  >
                    <ChevronRight className="h-5 w-5" />
                  </button>
                  <div className="flex justify-center gap-1.5 p-2">
                    {allImages.map((_, i) => (
                      <button
                        key={i}
                        onClick={() => setCurrentImage(i)}
                        className={`w-2 h-2 rounded-full transition-colors ${i === currentImage ? 'bg-[hsl(var(--primary))]' : 'bg-gray-300'}`}
                      />
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {/* Variant Selector */}
          {hasVariants && Object.entries(variantGroups).map(([group, groupVariants]) => (
            <div key={group}>
              <h4 className="font-medium mb-2 text-sm capitalize">{group}</h4>
              <div className="flex flex-wrap gap-2">
                {groupVariants.map((v) => {
                  const isSelected = selectedVariant?.asin === v.asin
                  // Color-like groups: show image swatches
                  if (v.image_url && group.toLowerCase().match(/^(farbe|color|colour)$/)) {
                    return (
                      <button
                        key={v.asin}
                        onClick={() => { setSelectedVariant(v); setCurrentImage(0) }}
                        className={`w-10 h-10 rounded-full border-2 overflow-hidden transition-all ${
                          isSelected ? 'border-[hsl(var(--primary))] ring-2 ring-[hsl(var(--primary))] ring-offset-1' : 'border-gray-200 hover:border-gray-400'
                        }`}
                        title={v.value}
                      >
                        <img src={v.image_url} alt={v.value} className="w-full h-full object-cover" />
                      </button>
                    )
                  }
                  // Other groups: pill buttons
                  return (
                    <button
                      key={v.asin}
                      onClick={() => { setSelectedVariant(v); setCurrentImage(0) }}
                      className={`px-3 py-1.5 rounded-full text-sm border transition-all ${
                        isSelected
                          ? 'border-[hsl(var(--primary))] bg-[hsl(var(--primary))] text-white'
                          : 'border-gray-200 hover:border-gray-400'
                      }`}
                    >
                      {v.value}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}

          {/* Brand + Product Info + Price */}
          <div className="flex items-center justify-between">
            <div>
              {product.brand && <p className="text-sm text-[hsl(var(--muted-foreground))]">{product.brand}</p>}
              {product.model && <p className="text-xs text-[hsl(var(--muted-foreground))]">Model: {product.model}</p>}
              {product.color && <p className="text-xs text-[hsl(var(--muted-foreground))]">Color: {product.color}</p>}
              {product.material && <p className="text-xs text-[hsl(var(--muted-foreground))]">Material: {product.material}</p>}
              {product.product_dimensions && <p className="text-xs text-[hsl(var(--muted-foreground))]">Dimensions: {product.product_dimensions}</p>}
              {product.item_weight && <p className="text-xs text-[hsl(var(--muted-foreground))]">Weight: {product.item_weight}</p>}
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold">{formatCents(displayPrice)}</div>
              {!selectedVariant && product.price_min_cents && product.price_max_cents && product.price_min_cents !== product.price_max_cents && (
                <p className="text-xs text-[hsl(var(--muted-foreground))]">
                  Price range: {formatCents(product.price_min_cents)} - {formatCents(product.price_max_cents)}
                </p>
              )}
            </div>
          </div>

          {/* Description */}
          {product.description && (
            <div>
              <h4 className="font-medium mb-1">Description</h4>
              <p className="text-sm text-[hsl(var(--muted-foreground))] whitespace-pre-line">{product.description}</p>
            </div>
          )}

          {/* Specifications */}
          {product.specifications && Object.keys(product.specifications).length > 0 && (
            <div>
              <h4 className="font-medium mb-2">Specifications</h4>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                {Object.entries(product.specifications).map(([key, value]) => (
                  <div key={key} className="contents">
                    <span className="text-[hsl(var(--muted-foreground))]">{key}</span>
                    <span>{String(value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 pt-2 border-t">
            <Button onClick={handleAddToCart} disabled={!product.is_active} className="flex-1">
              <ShoppingCart className="h-4 w-4 mr-2" />
              Add to cart
            </Button>
            {product.external_url && (
              <Button variant="outline" asChild>
                <a href={product.external_url} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="h-4 w-4 mr-1" />
                  Amazon
                </a>
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
