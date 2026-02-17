import { ShoppingCart } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { formatCents } from '@/lib/utils'
import { useCartStore } from '@/stores/cartStore'
import { useUiStore } from '@/stores/uiStore'
import { cartApi } from '@/services/cartApi'
import { getErrorMessage } from '@/lib/error'
import type { Product } from '@/types'

interface Props {
  product: Product
  onRefreshCart: () => void
  onShowDetail: (product: Product) => void
}

export function ProductCard({ product, onRefreshCart, onShowDetail }: Props) {
  const { addToast } = useUiStore()

  const handleAddToCart = async (e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await cartApi.addItem(product.id)
      onRefreshCart()
      useCartStore.getState().setOpen(true)
      addToast({ title: 'Added to cart', description: product.name })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const imageUrl = product.image_url
    ? `${import.meta.env.VITE_API_URL || ''}${product.image_url}`
    : null

  return (
    <Card className="overflow-hidden hover:shadow-lg transition-shadow cursor-pointer" onClick={() => onShowDetail(product)}>
      <div className="aspect-square bg-gray-50 flex items-center justify-center overflow-hidden">
        {imageUrl ? (
          <img src={imageUrl} alt={product.name} className="h-full w-full object-contain p-4" />
        ) : (
          <div className="text-4xl font-bold text-gray-300">
            {product.name.split(' ').map(w => w[0]).join('').slice(0, 2)}
          </div>
        )}
      </div>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2 mb-2">
          <h3 className="font-semibold text-sm line-clamp-2">{product.name}</h3>
        </div>
        {product.brand && (
          <p className="text-xs text-[hsl(var(--muted-foreground))] mb-2">{product.brand}</p>
        )}
        <div className="flex items-center justify-between mt-auto">
          <span className="text-lg font-bold">{formatCents(product.price_cents)}</span>
          <Button size="sm" onClick={handleAddToCart} disabled={!product.is_active}>
            <ShoppingCart className="h-4 w-4 mr-1" />
            Add
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
