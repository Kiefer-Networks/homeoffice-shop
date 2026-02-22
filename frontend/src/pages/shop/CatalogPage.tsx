import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { SlidersHorizontal, X } from 'lucide-react'
import { ProductCard } from '@/components/shop/ProductCard'
import { ProductDetailModal } from '@/components/shop/ProductDetailModal'
import { ProductFilters } from '@/components/shop/ProductFilters'
import { ProductSearch } from '@/components/shop/ProductSearch'
import { BudgetIndicator } from '@/components/shop/BudgetIndicator'
import { CartDrawer } from '@/components/shop/CartDrawer'
import { CartPriceAlert } from '@/components/shop/CartPriceAlert'
import { Pagination } from '@/components/ui/Pagination'
import { Button } from '@/components/ui/button'
import { useFilterStore } from '@/stores/filterStore'
import { useCartStore } from '@/stores/cartStore'
import { useAuthStore } from '@/stores/authStore'
import { useUiStore } from '@/stores/uiStore'
import { productApi } from '@/services/productApi'
import { orderApi } from '@/services/orderApi'
import { getErrorMessage } from '@/lib/error'
import type { Product, Category, Facets } from '@/types'

export function CatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filterStore = useFilterStore()
  const { cart, setOpen: setCartOpen } = useCartStore()
  const { addToast } = useUiStore()

  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [facets, setFacets] = useState<Facets | null>(null)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [showPriceAlert, setShowPriceAlert] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [showMobileFilters, setShowMobileFilters] = useState(false)

  useEffect(() => {
    filterStore.syncFromUrl(searchParams)
    productApi.getCategories().then(({ data }) => setCategories(data)).catch((err) => addToast({ title: 'Failed to load categories', description: getErrorMessage(err), variant: 'destructive' }))
  }, [])

  const refreshCart = useCallback(async () => {
    try {
      await useCartStore.getState().fetchCart()
    } catch {
      // Cart may not exist yet for new users - this is expected
    }
  }, [])

  useEffect(() => { refreshCart() }, [refreshCart])

  useEffect(() => {
    const params = filterStore.toSearchParams()
    setSearchParams(params, { replace: true })

    setLoading(true)
    productApi.search(params).then(({ data }) => {
      setProducts(data.items)
      setTotal(data.total)
      setFacets(data.facets)
    }).finally(() => setLoading(false))
  }, [filterStore.q, filterStore.category, filterStore.brand, filterStore.color, filterStore.material, filterStore.priceMin, filterStore.priceMax, filterStore.sort, filterStore.page])

  const handleCheckout = async () => {
    if (!cart) return
    if (cart.has_price_changes) {
      setShowPriceAlert(true)
      return
    }
    await placeOrder(false)
  }

  const placeOrder = async (confirmPriceChanges: boolean) => {
    try {
      await orderApi.create({ confirm_price_changes: confirmPriceChanges })
      setShowPriceAlert(false)
      setCartOpen(false)
      await refreshCart()
      useAuthStore.getState().refreshBudget()
      addToast({ title: 'Order placed!', description: 'Your order has been submitted for review.' })
    } catch (err: unknown) {
      addToast({ title: 'Order failed', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div>
      <div className="mb-6">
        <BudgetIndicator />
      </div>

      <div className="mb-4 md:hidden">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowMobileFilters((prev) => !prev)}
          className="w-full flex items-center justify-center gap-2"
        >
          {showMobileFilters ? (
            <>
              <X className="h-4 w-4" />
              Hide Filters
            </>
          ) : (
            <>
              <SlidersHorizontal className="h-4 w-4" />
              Show Filters
            </>
          )}
        </Button>
      </div>

      {showMobileFilters && (
        <div className="mb-6 md:hidden rounded-lg border border-[hsl(var(--border))] p-4">
          <ProductFilters facets={facets} categories={categories} idPrefix="mobile-" />
        </div>
      )}

      <div className="flex gap-6">
        <aside className="hidden md:block w-56 shrink-0">
          <ProductFilters facets={facets} categories={categories} />
        </aside>

        <div className="flex-1">
          <div className="mb-4">
            <ProductSearch />
          </div>

          <p className="text-sm text-[hsl(var(--muted-foreground))] mb-4">{total} products found</p>

          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="h-80 bg-gray-100 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : products.length === 0 ? (
            <div className="text-center py-12 text-[hsl(var(--muted-foreground))]">
              <p className="text-lg">No products found</p>
              <p className="text-sm">Try different search terms or filters.</p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {products.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    onRefreshCart={refreshCart}
                    onShowDetail={setSelectedProduct}
                  />
                ))}
              </div>

              <Pagination
                page={filterStore.page}
                totalPages={totalPages}
                onPageChange={(p) => filterStore.setFilter('page', p)}
              />
            </>
          )}
        </div>
      </div>

      <CartDrawer onCheckout={handleCheckout} />

      <ProductDetailModal
        product={selectedProduct}
        open={!!selectedProduct}
        onClose={() => setSelectedProduct(null)}
        onRefreshCart={refreshCart}
      />

      {cart && showPriceAlert && (
        <CartPriceAlert
          open={showPriceAlert}
          onClose={() => setShowPriceAlert(false)}
          onConfirm={() => placeOrder(true)}
          cart={cart}
        />
      )}
    </div>
  )
}
