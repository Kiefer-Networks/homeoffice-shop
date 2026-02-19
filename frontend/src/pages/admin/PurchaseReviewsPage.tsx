import { useEffect, useState, useCallback, useRef } from 'react'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Pagination } from '@/components/ui/Pagination'
import { Badge } from '@/components/ui/badge'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { formatCents, formatDate } from '@/lib/utils'
import { getErrorMessage } from '@/lib/error'
import { SortHeader } from '@/components/ui/SortHeader'
import { PURCHASE_STATUS_VARIANT } from '@/lib/constants'
import { RefreshCcw, Loader2, Link as LinkIcon, Minus, X } from 'lucide-react'
import { EmployeeDetailModal } from './EmployeeDetailModal'
import type { HiBobPurchaseReview, Order, PaginatedResponse } from '@/types'

const PER_PAGE = 50

type SortKey = 'date_desc' | 'date_asc' | 'amount_desc' | 'amount_asc' | 'employee_asc' | 'employee_desc'

const STATUS_TABS = [
  { label: 'All', value: '' },
  { label: 'Pending', value: 'pending' },
  { label: 'Matched', value: 'matched' },
  { label: 'Adjusted', value: 'adjusted' },
  { label: 'Dismissed', value: 'dismissed' },
] as const

export function PurchaseReviewsPage() {
  const [reviews, setReviews] = useState<HiBobPurchaseReview[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState<SortKey>('date_desc')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 300)
  const [loading, setLoading] = useState(true)
  const [syncRunning, setSyncRunning] = useState(false)
  const { addToast } = useUiStore()

  // Match dialog state
  const [matchDialog, setMatchDialog] = useState<HiBobPurchaseReview | null>(null)
  const [orderResults, setOrderResults] = useState<Order[]>([])
  const [searchingOrders, setSearchingOrders] = useState(false)
  const [matchingId, setMatchingId] = useState<string | null>(null)

  // Employee detail modal
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)

  // Action loading
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  // Poll purchase sync status
  const checkSyncStatus = useCallback(async () => {
    try {
      const { data } = await adminApi.getPurchaseSyncStatus()
      setSyncRunning(data.running)
      return data.running
    } catch {
      return false
    }
  }, [])

  useEffect(() => {
    checkSyncStatus()
    const id = setInterval(checkSyncStatus, 5000)
    return () => clearInterval(id)
  }, [checkSyncStatus])

  // Reload data when sync finishes
  const prevSyncRunning = useRef(syncRunning)
  useEffect(() => {
    if (prevSyncRunning.current && !syncRunning) {
      loadReviews()
    }
    prevSyncRunning.current = syncRunning
  }, [syncRunning])

  const loadReviews = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { page, per_page: PER_PAGE, sort }
      if (statusFilter) params.status = statusFilter
      if (debouncedSearch) params.q = debouncedSearch
      const { data } = await adminApi.listPurchaseReviews(params)
      setReviews(data.items)
      setTotal(data.total)
    } catch (err: unknown) {
      addToast({ title: 'Failed to load reviews', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [page, sort, statusFilter, debouncedSearch])

  useEffect(() => { loadReviews() }, [loadReviews])

  // Reset to page 1 when filters change
  useEffect(() => { setPage(1) }, [debouncedSearch, statusFilter, sort])

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE))

  const handleSync = async () => {
    try {
      await adminApi.triggerPurchaseSync()
      setSyncRunning(true)
      addToast({ title: 'Purchase sync started', description: 'Running in background. Results will appear when finished.' })
    } catch (err: unknown) {
      addToast({ title: 'Sync failed', description: getErrorMessage(err), variant: 'destructive' })
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

  return (
    <div>
      {/* Sync Running Banner */}
      {syncRunning && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          <Loader2 className="h-4 w-4 animate-spin shrink-0" />
          <span>Purchase sync is running. Data on this page will refresh automatically when finished.</span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Purchase Reviews ({total})</h1>
        <Button onClick={handleSync} disabled={syncRunning}>
          <RefreshCcw className={`h-4 w-4 mr-1 ${syncRunning ? 'animate-spin' : ''}`} />
          {syncRunning ? 'Syncing...' : 'Sync Purchases'}
        </Button>
      </div>

      {/* Search */}
      <div className="mb-4">
        <Input
          placeholder="Search by employee or description..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-4 items-center">
        <div className="flex gap-1">
          {STATUS_TABS.map((tab) => (
            <Button
              key={tab.value}
              size="sm"
              variant={statusFilter === tab.value ? 'default' : 'outline'}
              onClick={() => setStatusFilter(tab.value)}
            >
              {tab.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-[hsl(var(--muted-foreground))]" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                    <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
                      <SortHeader label="Date" ascKey="date_asc" descKey="date_desc" currentSort={sort} onSort={setSort} />
                    </th>
                    <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
                      <SortHeader label="Employee" ascKey="employee_asc" descKey="employee_desc" currentSort={sort} onSort={setSort} />
                    </th>
                    <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Description</th>
                    <th className="text-right px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
                      <div className="flex justify-end">
                        <SortHeader label="Amount" ascKey="amount_asc" descKey="amount_desc" currentSort={sort} onSort={setSort} />
                      </div>
                    </th>
                    <th className="text-center px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Status</th>
                    <th className="text-right px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {reviews.map(review => (
                    <tr key={review.id} className="border-b border-[hsl(var(--border))] hover:bg-[hsl(var(--muted)/0.5)]">
                      <td className="px-4 py-3 whitespace-nowrap">{formatDate(review.entry_date)}</td>
                      <td className="px-4 py-3">
                        <button
                          className="font-medium text-left hover:underline hover:text-[hsl(var(--primary))] transition-colors"
                          onClick={() => setSelectedUserId(review.user_id)}
                        >
                          {review.user_display_name || review.hibob_employee_id}
                        </button>
                      </td>
                      <td className="px-4 py-3 max-w-xs truncate">{review.description}</td>
                      <td className="px-4 py-3 text-right whitespace-nowrap font-medium text-red-600">
                        {formatCents(review.amount_cents)}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <Badge variant={PURCHASE_STATUS_VARIANT[review.status]}>{review.status}</Badge>
                      </td>
                      <td className="px-4 py-3 text-right">
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
                  {reviews.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
                        No purchase reviews found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </CardContent>
      </Card>

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

      {selectedUserId && (
        <EmployeeDetailModal
          userId={selectedUserId}
          onClose={() => setSelectedUserId(null)}
        />
      )}
    </div>
  )
}
