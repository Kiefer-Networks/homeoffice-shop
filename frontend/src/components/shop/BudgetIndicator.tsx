import { formatCents } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'

export function BudgetIndicator() {
  const { user } = useAuthStore()
  if (!user) return null

  const total = user.total_budget_cents
  const available = user.available_budget_cents
  const spent = total - available
  const percentage = total > 0 ? Math.min((spent / total) * 100, 100) : 0

  return (
    <div className="bg-white rounded-lg border p-4">
      <div className="flex justify-between text-sm mb-2">
        <span className="text-[hsl(var(--muted-foreground))]">Budget</span>
        <span className="font-semibold">{formatCents(available)} remaining</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${percentage > 90 ? 'bg-red-500' : percentage > 70 ? 'bg-yellow-500' : 'bg-[hsl(var(--primary))]'}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-[hsl(var(--muted-foreground))] mt-1">
        <span>{formatCents(spent)} spent</span>
        <span>{formatCents(total)} total</span>
      </div>
    </div>
  )
}
