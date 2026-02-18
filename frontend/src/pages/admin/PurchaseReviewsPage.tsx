import { useEffect, useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { formatCents, formatDate } from '@/lib/utils'
import { getErrorMessage } from '@/lib/error'
import { RefreshCcw, Loader2, Link as LinkIcon, Minus, X } from 'lucide-react'
import type { HiBobPurchaseReview, Order, PaginatedResponse } from '@/types'

const STATUS_TABS = ['all', 'pending', 'matched', 'adjusted', 'dismissed'] as const

export function PurchaseReviewsPage() {
  const [reviews, setReviews] = useState<HiBobPurchaseReview[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const { addToast } = useUiStore()

  // Match dialog state
  const [matchDialog, setMatchDialog] = useState<HiBobPurchaseReview | null>(null)
  const [orderResults, setOrderResults] = useState<Order[]>([])
  const [searchingOrders, setSearchingOrders] = useState(false)
  const [matchingId, setMatchingId] = useState<string | null>(null)

  // Action loading
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const perPage = 50

  const loadReviews = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { page, per_page: perPage }
      if (statusFilter !== 'all') params.status = statusFilter
      const { data } = await adminApi.listPurchaseReviews(params)
      setReviews(data.items)
      setTotal(data.total)
    } catch (err: unknown) {
      addToast({ title: 'Failed to load reviews', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [page, statusFilter])

  useEffect(() => { loadReviews() }, [loadReviews])

  const handleSync = async () => {
    setSyncing(true)
    try {
      await adminApi.triggerPurchaseSync()
      addToast({ title: 'Purchase sync completed' })
      loadReviews()
    } catch (err: unknown) {
      addToast({ title: 'Sync failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setSyncing(false)
    }
  }

  const handleMatch = async (reviewId: string, orderId: string) => {
    setMatchingId(reviewId)
    try {
      await adminApi.matchReview(reviewId, { order_id: orderId })
      addToast({ title: 'Review matched to order' })
      setMatchDialog(null)
      loadReviews()
    } catch (err: unknown) {
      addToast({ title: 'Match failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setMatchingId(null)
    }
  }

  const handleAdjust = async (reviewId: string) => {
    setActionLoading(reviewId)
    try {
      await adminApi.adjustReview(reviewId)
      addToast({ title: 'Budget adjustment created' })
      loadReviews()
    } catch (err: unknown) {
      addToast({ title: 'Adjust failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setActionLoading(null)
    }
  }

  const handleDismiss = async (reviewId: string) => {
    setActionLoading(reviewId)
    try {
      await adminApi.dismissReview(reviewId)
      addToast({ title: 'Review dismissed' })
      loadReviews()
    } catch (err: unknown) {
      addToast({ title: 'Dismiss failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setActionLoading(null)
    }
  }

  const openMatchDialog = (review: HiBobPurchaseReview) => {
    setMatchDialog(review)
    setOrderResults([])
  }

  const searchOrders = async () => {
    if (!matchDialog) return
    setSearchingOrders(true)
    try {
      const { data } = await adminApi.listOrders({
        user_id: matchDialog.user_id,
        per_page: 20,
      }) as { data: PaginatedResponse<Order> }
      setOrderResults(data.items)
    } catch {
      setOrderResults([])
    } finally {
      setSearchingOrders(false)
    }
  }

  useEffect(() => {
    if (matchDialog) searchOrders()
  }, [matchDialog])

  const totalPages = Math.ceil(total / perPage)

  const statusVariant = (status: string) => {
    switch (status) {
      case 'pending': return 'warning' as const
      case 'matched': return 'success' as const
      case 'adjusted': return 'default' as const
      case 'dismissed': return 'secondary' as const
      default: return 'default' as const
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Purchase Reviews</h1>
        <Button onClick={handleSync} disabled={syncing}>
          {syncing ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <RefreshCcw className="h-4 w-4 mr-2" />}
          Sync Purchases
        </Button>
      </div>

      {/* Status filter tabs */}
      <div className="flex gap-2 mb-4">
        {STATUS_TABS.map(tab => (
          <button
            key={tab}
            onClick={() => { setStatusFilter(tab); setPage(1) }}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
              statusFilter === tab
                ? 'bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]'
                : 'bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))]'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-[hsl(var(--muted-foreground))]" />
        </div>
      ) : reviews.length === 0 ? (
        <p className="text-[hsl(var(--muted-foreground))] py-8 text-center">No purchase reviews found.</p>
      ) : (
        <>
          <div className="overflow-x-auto border rounded-lg">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                  <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Date</th>
                  <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Employee</th>
                  <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Description</th>
                  <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Amount</th>
                  <th className="text-center px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Status</th>
                  <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {reviews.map(review => (
                  <tr key={review.id} className="border-b border-[hsl(var(--border))] last:border-b-0 hover:bg-[hsl(var(--muted))]">
                    <td className="px-4 py-2 whitespace-nowrap">{formatDate(review.entry_date)}</td>
                    <td className="px-4 py-2">{review.user_display_name || review.hibob_employee_id}</td>
                    <td className="px-4 py-2 max-w-xs truncate">{review.description}</td>
                    <td className="px-4 py-2 text-right whitespace-nowrap font-medium text-red-600">
                      {formatCents(review.amount_cents)}
                    </td>
                    <td className="px-4 py-2 text-center">
                      <Badge variant={statusVariant(review.status)}>{review.status}</Badge>
                    </td>
                    <td className="px-4 py-2 text-right">
                      {review.status === 'pending' && (
                        <div className="flex justify-end gap-1">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openMatchDialog(review)}
                            disabled={actionLoading === review.id}
                          >
                            <LinkIcon className="h-3.5 w-3.5 mr-1" /> Match
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleAdjust(review.id)}
                            disabled={actionLoading === review.id}
                          >
                            <Minus className="h-3.5 w-3.5 mr-1" /> Adjust
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleDismiss(review.id)}
                            disabled={actionLoading === review.id}
                          >
                            <X className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      )}
                      {review.status === 'matched' && review.matched_order_id && (
                        <span className="text-xs text-[hsl(var(--muted-foreground))]">
                          Order: {review.matched_order_id.slice(0, 8)}...
                        </span>
                      )}
                      {review.status === 'adjusted' && (
                        <span className="text-xs text-[hsl(var(--muted-foreground))]">
                          -{formatCents(review.amount_cents)}
                        </span>
                      )}
                      {review.status === 'dismissed' && review.resolved_at && (
                        <span className="text-xs text-[hsl(var(--muted-foreground))]">
                          {formatDate(review.resolved_at)}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                {total} total review{total !== 1 ? 's' : ''}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(p => p - 1)}
                  disabled={page <= 1}
                >
                  Previous
                </Button>
                <span className="text-sm">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(p => p + 1)}
                  disabled={page >= totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Match to Order Dialog */}
      <Dialog open={!!matchDialog} onOpenChange={() => setMatchDialog(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Match to Order</DialogTitle>
          </DialogHeader>
          {matchDialog && (
            <div>
              <div className="mb-4 p-3 bg-[hsl(var(--muted))] rounded-lg text-sm">
                <p><strong>Employee:</strong> {matchDialog.user_display_name}</p>
                <p><strong>Description:</strong> {matchDialog.description}</p>
                <p><strong>Amount:</strong> {formatCents(matchDialog.amount_cents)}</p>
                <p><strong>Date:</strong> {formatDate(matchDialog.entry_date)}</p>
              </div>

              <h4 className="text-sm font-medium mb-2">Select an order to match:</h4>
              {searchingOrders ? (
                <div className="flex justify-center py-4">
                  <Loader2 className="h-5 w-5 animate-spin" />
                </div>
              ) : orderResults.length === 0 ? (
                <p className="text-sm text-[hsl(var(--muted-foreground))] py-4 text-center">No orders found for this user.</p>
              ) : (
                <div className="max-h-64 overflow-y-auto border rounded-lg">
                  {orderResults.map(order => {
                    const amountDiff = Math.abs(order.total_cents - matchDialog.amount_cents)
                    const isClose = amountDiff <= 100
                    return (
                      <div
                        key={order.id}
                        className="flex items-center justify-between px-4 py-2 border-b last:border-b-0 hover:bg-[hsl(var(--muted))]"
                      >
                        <div className="text-sm">
                          <span className="font-medium">{formatCents(order.total_cents)}</span>
                          <span className="ml-2 text-[hsl(var(--muted-foreground))]">{formatDate(order.created_at)}</span>
                          <Badge className="ml-2" variant={order.status === 'delivered' ? 'success' : 'default'}>{order.status}</Badge>
                          {isClose && <Badge className="ml-1" variant="success">close match</Badge>}
                        </div>
                        <Button
                          size="sm"
                          onClick={() => handleMatch(matchDialog.id, order.id)}
                          disabled={matchingId === matchDialog.id}
                        >
                          {matchingId === matchDialog.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Select'}
                        </Button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setMatchDialog(null)}>Cancel</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
