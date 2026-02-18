import { X, Trash2, Plus, Minus, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useCartStore } from '@/stores/cartStore'
import { useUiStore } from '@/stores/uiStore'
import { cartApi } from '@/services/cartApi'
import { formatCents } from '@/lib/utils'
import { getErrorMessage } from '@/lib/error'

interface Props {
  onRefreshCart: () => void
  onCheckout: () => void
}

export function CartDrawer({ onRefreshCart, onCheckout }: Props) {
  const { cart, isOpen, setOpen } = useCartStore()
  const { addToast } = useUiStore()

  if (!isOpen) return null

  const handleUpdateQty = async (productId: string, qty: number) => {
    try {
      if (qty <= 0) {
        await cartApi.removeItem(productId)
      } else {
        await cartApi.updateItem(productId, qty)
      }
      onRefreshCart()
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const handleRemove = async (productId: string) => {
    try {
      await cartApi.removeItem(productId)
      onRefreshCart()
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Shopping cart"
      onKeyDown={(e) => { if (e.key === 'Escape') setOpen(false) }}>
      <div className="fixed inset-0 bg-black/50" onClick={() => setOpen(false)} />
      <div className="fixed right-0 top-0 bottom-0 w-full max-w-md bg-white shadow-xl flex flex-col">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">Shopping Cart</h2>
          <Button variant="ghost" size="icon" onClick={() => setOpen(false)} aria-label="Close cart">
            <X className="h-5 w-5" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {!cart?.items.length ? (
            <p className="text-center text-[hsl(var(--muted-foreground))] py-8">Your cart is empty</p>
          ) : (
            cart.items.map((item) => (
              <div key={item.id} className="flex gap-3 border-b pb-4">
                <div className="flex-1">
                  <h4 className="font-medium text-sm">
                    {item.product_name}
                    {item.variant_value && (
                      <span className="text-[hsl(var(--muted-foreground))] font-normal"> — {item.variant_value}</span>
                    )}
                  </h4>
                  <p className="text-sm font-semibold mt-1">{formatCents(item.current_price_cents)}</p>
                  {item.price_changed && (
                    <div className="flex items-center gap-1 mt-1">
                      <AlertTriangle className="h-3 w-3 text-yellow-600" />
                      <span className="text-xs text-yellow-600">
                        Price changed: was {formatCents(item.price_at_add_cents)} (
                        {item.price_diff_cents > 0 ? '+' : ''}{formatCents(item.price_diff_cents)})
                      </span>
                    </div>
                  )}
                  {!item.product_active && (
                    <Badge variant="destructive" className="mt-1 text-xs">Unavailable</Badge>
                  )}
                  <div className="flex items-center gap-2 mt-2">
                    <Button variant="outline" size="icon" className="h-7 w-7"
                      onClick={() => handleUpdateQty(item.product_id, item.quantity - 1)}
                      aria-label={`Decrease quantity of ${item.product_name}`}>
                      <Minus className="h-3 w-3" />
                    </Button>
                    <span className="text-sm w-8 text-center" aria-label={`Quantity: ${item.quantity}`}>{item.quantity}</span>
                    <Button variant="outline" size="icon" className="h-7 w-7"
                      onClick={() => handleUpdateQty(item.product_id, item.quantity + 1)}
                      disabled={item.quantity >= item.max_quantity_per_user}
                      aria-label={`Increase quantity of ${item.product_name}`}>
                      <Plus className="h-3 w-3" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7 ml-auto text-red-500"
                      onClick={() => handleRemove(item.product_id)}
                      aria-label={`Remove ${item.product_name} from cart`}>
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {cart?.items.length ? (
          <div className="border-t p-4 space-y-3">
            <div className="flex justify-between text-sm">
              <span>Total</span>
              <span className="font-bold">{formatCents(cart.total_current_cents)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span>Available Budget</span>
              <span className={cart.budget_exceeded ? 'text-red-600 font-bold' : 'font-medium'}>
                {formatCents(cart.available_budget_cents)}
              </span>
            </div>
            {cart.budget_exceeded && (
              <p className="text-xs text-red-600">Your cart total exceeds your available budget.</p>
            )}
            {cart.has_unavailable_items && (
              <p className="text-xs text-red-600">Please remove unavailable items before ordering.</p>
            )}
            <Button
              className="w-full"
              disabled={cart.budget_exceeded || cart.has_unavailable_items || !cart.items.length}
              onClick={onCheckout}
            >
              Place Order
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  )
}
