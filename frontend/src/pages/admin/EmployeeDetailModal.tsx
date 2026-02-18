import { useEffect, useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { adminApi } from '@/services/adminApi'
import { formatCents, formatDate } from '@/lib/utils'
import type { UserDetailResponse } from '@/types'

const statusVariant: Record<string, 'default' | 'secondary' | 'success' | 'destructive' | 'warning'> = {
  pending: 'warning', ordered: 'default', delivered: 'success', rejected: 'destructive', cancelled: 'secondary',
}

interface EmployeeDetailModalProps {
  userId: string | null
  onClose: () => void
}

export function EmployeeDetailModal({ userId, onClose }: EmployeeDetailModalProps) {
  const [data, setData] = useState<UserDetailResponse | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!userId) {
      setData(null)
      return
    }
    setLoading(true)
    adminApi.getUserDetail(userId)
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false))
  }, [userId])

  return (
    <Dialog open={!!userId} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        {loading ? (
          <div className="space-y-4 py-8">
            <div className="h-6 w-48 bg-[hsl(var(--muted))] rounded animate-pulse" />
            <div className="h-24 bg-[hsl(var(--muted))] rounded animate-pulse" />
            <div className="h-40 bg-[hsl(var(--muted))] rounded animate-pulse" />
          </div>
        ) : data ? (
          <>
            <DialogHeader>
              <DialogTitle>{data.user.display_name}</DialogTitle>
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                {data.user.email}{data.user.department ? ` — ${data.user.department}` : ''}
              </p>
            </DialogHeader>

            {/* Budget Summary */}
            <Card>
              <CardContent className="p-4">
                <h3 className="text-sm font-medium mb-3">Budget Summary</h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div>
                    <div className="text-xs text-[hsl(var(--muted-foreground))]">Total Budget</div>
                    <div className="text-lg font-semibold">{formatCents(data.budget_summary.total_budget_cents)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-[hsl(var(--muted-foreground))]">Spent</div>
                    <div className="text-lg font-semibold">{formatCents(data.budget_summary.spent_cents)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-[hsl(var(--muted-foreground))]">Adjustments</div>
                    <div className="text-lg font-semibold">{formatCents(data.budget_summary.adjustment_cents)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-[hsl(var(--muted-foreground))]">Available</div>
                    <div className="text-lg font-semibold text-green-700">{formatCents(data.budget_summary.available_cents)}</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Orders */}
            <div>
              <h3 className="text-sm font-medium mb-2">Orders ({data.orders.length})</h3>
              {data.orders.length === 0 ? (
                <p className="text-sm text-[hsl(var(--muted-foreground))]">No orders yet.</p>
              ) : (
                <Card>
                  <CardContent className="p-0">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                            <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Status</th>
                            <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Date</th>
                            <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Items</th>
                            <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.orders.map((order) => (
                            <tr key={order.id} className="border-b border-[hsl(var(--border))] last:border-b-0">
                              <td className="px-4 py-2">
                                <Badge variant={statusVariant[order.status]}>{order.status}</Badge>
                              </td>
                              <td className="px-4 py-2">{formatDate(order.created_at)}</td>
                              <td className="px-4 py-2 text-right">{order.items.length}</td>
                              <td className="px-4 py-2 text-right font-medium">{formatCents(order.total_cents)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>

            {/* Budget Adjustments */}
            <div>
              <h3 className="text-sm font-medium mb-2">Budget Adjustments ({data.adjustments.length})</h3>
              {data.adjustments.length === 0 ? (
                <p className="text-sm text-[hsl(var(--muted-foreground))]">No adjustments.</p>
              ) : (
                <Card>
                  <CardContent className="p-0">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                            <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Amount</th>
                            <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Reason</th>
                            <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Date</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.adjustments.map((adj) => (
                            <tr key={adj.id} className="border-b border-[hsl(var(--border))] last:border-b-0">
                              <td className="px-4 py-2 text-right font-medium">{formatCents(adj.amount_cents)}</td>
                              <td className="px-4 py-2 text-[hsl(var(--muted-foreground))]">{adj.reason}</td>
                              <td className="px-4 py-2">{formatDate(adj.created_at)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
