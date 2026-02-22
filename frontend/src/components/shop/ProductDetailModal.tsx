import React, { useState, useEffect, useMemo } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { formatCents } from '@/lib/utils'
import { ShoppingCart, ExternalLink, ChevronLeft, ChevronRight } from 'lucide-react'
import { useCartStore } from '@/stores/cartStore'
import { useUiStore } from '@/stores/uiStore'
import { cartApi } from '@/services/cartApi'
import { getErrorMessage } from '@/lib/error'
import { formatGroupLabel } from '@/lib/product-utils'
import type { Product, ProductVariant } from '@/types'

function formatVariantValue(value: string): string {
  return value.replace(/\.+$/, '').trim().replace(/\b\w/g, c => c.toUpperCase())
}

const INFO_FIELDS: { key: string; label: string }[] = [
  { key: 'brand', label: 'Brand' },
  { key: 'model', label: 'Model' },
  { key: 'material', label: 'Material' },
  { key: 'product_dimensions', label: 'Dimensions' },
  { key: 'item_weight', label: 'Weight' },
  { key: 'charging_time', label: 'Charging Time' },
  { key: 'water_resistance_level', label: 'Water Resistance' },
  { key: 'compatible_devices', label: 'Compatible Devices' },
  { key: 'control_type', label: 'Controls' },
  { key: 'cable_feature', label: 'Cable' },
  { key: 'included_components', label: 'Included' },
  { key: 'specific_uses_for_product', label: 'Use Cases' },
]

const VariantButton = React.memo(function VariantButton({
  variant, isSelected, onClick
}: {
  variant: { value: string; asin?: string }; isSelected: boolean; onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-full text-sm border transition-all ${
        isSelected
          ? 'border-[hsl(var(--primary))] bg-[hsl(var(--primary))] text-white'
          : 'border-gray-200 hover:border-gray-400'
      }`}
    >
      {formatVariantValue(variant.value)}
    </button>
  )
})

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
      <DialogContent className="max-w-2xl">
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
                    aria-label="Previous image"
                    onClick={() => setCurrentImage(i => (i - 1 + allImages.length) % allImages.length)}
                    className="absolute left-2 top-1/2 -translate-y-1/2 bg-white/80 rounded-full p-1 hover:bg-white shadow"
                  >
                    <ChevronLeft className="h-5 w-5" />
                  </button>
                  <button
                    aria-label="Next image"
                    onClick={() => setCurrentImage(i => (i + 1) % allImages.length)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 bg-white/80 rounded-full p-1 hover:bg-white shadow"
                  >
                    <ChevronRight className="h-5 w-5" />
                  </button>
                  <div className="flex justify-center gap-1.5 p-2">
                    {allImages.map((_, i) => (
                      <button
                        key={i}
                        aria-label={`Go to image ${i + 1}`}
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
          {hasVariants && Object.entries(variantGroups).map(([group, groupVariants]) => {
            const filtered = groupVariants.filter(v => v.value.trim() !== '')
            if (filtered.length === 0) return null
            return (
              <div key={group}>
                <h4 className="font-medium mb-2 text-sm">{formatGroupLabel(group)}</h4>
                <div className="flex flex-wrap gap-2">
                  {filtered.map((v) => {
                    const isSelected = selectedVariant?.asin === v.asin
                    const label = formatVariantValue(v.value)
                    // Color-like groups: show image swatches
                    if (v.image_url && group.toLowerCase().match(/^(farbe|color|colour)/)) {
                      return (
                        <button
                          key={v.asin}
                          onClick={() => { setSelectedVariant(v); setCurrentImage(0) }}
                          className={`w-10 h-10 rounded-full border-2 overflow-hidden transition-all ${
                            isSelected ? 'border-[hsl(var(--primary))] ring-2 ring-[hsl(var(--primary))] ring-offset-1' : 'border-gray-200 hover:border-gray-400'
                          }`}
                          title={label}
                        >
                          <img src={v.image_url} alt={label} className="w-full h-full object-cover" />
                        </button>
                      )
                    }
                    // Other groups: pill buttons
                    return (
                      <VariantButton
                        key={v.asin}
                        variant={v}
                        isSelected={isSelected}
                        onClick={() => { setSelectedVariant(v); setCurrentImage(0) }}
                      />
                    )
                  })}
                </div>
              </div>
            )
          })}

          {/* Price */}
          <div className="flex items-center justify-end">
            <div className="text-right">
              <div className="text-2xl font-bold">{formatCents(displayPrice)}</div>
              {!selectedVariant && product.price_min_cents && product.price_max_cents && product.price_min_cents !== product.price_max_cents && (
                <p className="text-xs text-[hsl(var(--muted-foreground))]">
                  Price range: {formatCents(product.price_min_cents)} - {formatCents(product.price_max_cents)}
                </p>
              )}
            </div>
          </div>

          {/* Product Details */}
          {(() => {
            const info: Record<string, string> = {}
            if (product.brand) info.brand = product.brand
            if (product.model) info.model = product.model
            if (product.color) info.color = product.color
            if (product.material) info.material = product.material
            if (product.product_dimensions) info.product_dimensions = product.product_dimensions
            if (product.item_weight) info.item_weight = product.item_weight
            const pi = product.product_information as Record<string, unknown> | null
            if (pi && typeof pi === 'object') {
              for (const [k, v] of Object.entries(pi)) {
                if (v && typeof v === 'string') info[k] = v
              }
            }
            const rows = INFO_FIELDS.filter(f => info[f.key])
            if (rows.length === 0) return null
            return (
              <div className="border rounded-lg overflow-hidden">
                <h4 className="font-medium text-sm px-3 py-2 bg-[hsl(var(--muted))]">Product Details</h4>
                <div className="divide-y">
                  {rows.map((f, i) => (
                    <div key={f.key} className={`flex px-3 py-2 text-sm ${i % 2 === 0 ? '' : 'bg-[hsl(var(--muted)/.3)]'}`}>
                      <span className="w-40 shrink-0 text-[hsl(var(--muted-foreground))]">{f.label}</span>
                      <span>{info[f.key]}</span>
                    </div>
                  ))}
                </div>
              </div>
            )
          })()}

          {/* Description */}
          {product.description && (
            <div>
              <h4 className="font-medium mb-1">Description</h4>
              <p className="text-sm text-[hsl(var(--muted-foreground))] whitespace-pre-line">{product.description}</p>
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
