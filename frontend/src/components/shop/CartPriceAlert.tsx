import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { formatCents } from '@/lib/utils'
import type { Cart } from '@/types'

interface Props {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  cart: Cart
}

export function CartPriceAlert({ open, onClose, onConfirm, cart }: Props) {
  const changedItems = cart.items.filter(i => i.price_changed)

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Prices Have Changed</DialogTitle>
          <DialogDescription>
            Some prices have changed since you added items to your cart:
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 my-4">
          {changedItems.map((item) => (
            <div key={item.id} className="flex justify-between text-sm">
              <span>{item.product_name}</span>
              <span>
                <span className="line-through text-[hsl(var(--muted-foreground))]">
                  {formatCents(item.price_at_add_cents)}
                </span>
                {' → '}
                <span className="font-semibold">{formatCents(item.current_price_cents)}</span>
                <span className={item.price_diff_cents > 0 ? 'text-red-600 ml-1' : 'text-green-600 ml-1'}>
                  ({item.price_diff_cents > 0 ? '+' : ''}{formatCents(item.price_diff_cents)})
                </span>
              </span>
            </div>
          ))}
        </div>
        <div className="flex justify-between font-semibold text-sm border-t pt-2">
          <span>New Total</span>
          <span>{formatCents(cart.total_current_cents)}</span>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={onConfirm}>Accept & Order</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
