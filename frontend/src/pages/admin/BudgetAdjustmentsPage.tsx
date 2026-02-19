import { useEffect, useState, useRef, useCallback } from 'react'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { formatCents, formatDate, parseEuroToCents, centsToEuroInput } from '@/lib/utils'
import { Plus, X, Pencil, Trash2, ArrowUpDown, Search, Loader2 } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import { useAuthStore } from '@/stores/authStore'
import { EmployeeDetailModal } from './EmployeeDetailModal'
import type { BudgetAdjustment, UserSearchResult } from '@/types'

type SortKey = 'newest' | 'oldest' | 'amount_asc' | 'amount_desc'

export function AdminBudgetAdjustmentsPage() {
  const [adjustments, setAdjustments] = useState<BudgetAdjustment[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 300)
  const [sort, setSort] = useState<SortKey>('newest')

  // Create dialog
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [createForm, setCreateForm] = useState({ user_id: '', amount_euro: '', reason: '' })
  const [employeeSearch, setEmployeeSearch] = useState('')
  const [searchResults, setSearchResults] = useState<UserSearchResult[]>([])
  const [showEmployeeDropdown, setShowEmployeeDropdown] = useState(false)
  const [selectedEmployeeName, setSelectedEmployeeName] = useState('')
  const dropdownRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined)

  // Edit dialog
  const [editTarget, setEditTarget] = useState<BudgetAdjustment | null>(null)
  const [editForm, setEditForm] = useState({ amount_euro: '', reason: '' })

  // Delete dialog
  const [deleteTarget, setDeleteTarget] = useState<BudgetAdjustment | null>(null)

  // Employee detail modal
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)

  const [syncRunning, setSyncRunning] = useState(false)

  const { addToast } = useUiStore()
  const perPage = 20

  // Poll purchase sync status
  useEffect(() => {
    const check = async () => {
      try {
        const { data } = await adminApi.getPurchaseSyncStatus()
        setSyncRunning(data.running)
      } catch { /* ignore */ }
    }
    check()
    const id = setInterval(check, 5000)
    return () => clearInterval(id)
  }, [])

  // Reload data when sync finishes
  const prevSyncRunning = useRef(syncRunning)
  useEffect(() => {
    if (prevSyncRunning.current && !syncRunning) {
      load()
    }
    prevSyncRunning.current = syncRunning
  }, [syncRunning])

  const load = useCallback(() => {
    const params: Record<string, string | number> = { page, per_page: perPage, sort }
    if (debouncedSearch) params.q = debouncedSearch
    adminApi.listAdjustments(params).then(({ data }) => {
      setAdjustments(data.items)
      setTotal(data.total)
    })
  }, [page, perPage, sort, debouncedSearch])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [debouncedSearch])

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowEmployeeDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Server-side employee search with debounce
  const handleEmployeeSearch = (value: string) => {
    setEmployeeSearch(value)
    setShowEmployeeDropdown(true)

    if (debounceRef.current) clearTimeout(debounceRef.current)

    if (!value.trim()) {
      setSearchResults([])
      return
    }

    debounceRef.current = setTimeout(async () => {
      try {
        const { data } = await adminApi.searchUsers(value)
        setSearchResults(data)
      } catch {
        setSearchResults([])
      }
    }, 300)
  }

  const selectEmployee = (user: UserSearchResult) => {
    setCreateForm(f => ({ ...f, user_id: user.id }))
    setSelectedEmployeeName(`${user.display_name} (${user.email})`)
    setEmployeeSearch('')
    setSearchResults([])
    setShowEmployeeDropdown(false)
  }

  const clearEmployee = () => {
    setCreateForm(f => ({ ...f, user_id: '' }))
    setSelectedEmployeeName('')
    setEmployeeSearch('')
    setSearchResults([])
  }

  const handleCreate = async () => {
    if (!createForm.user_id) {
      addToast({ title: 'Please select an employee', variant: 'destructive' })
      return
    }
    const amountCents = parseEuroToCents(createForm.amount_euro)
    if (amountCents === 0) {
      addToast({ title: 'Please enter an amount', variant: 'destructive' })
      return
    }
    try {
      await adminApi.createAdjustment({ user_id: createForm.user_id, amount_cents: amountCents, reason: createForm.reason })
      setShowCreateDialog(false)
      setCreateForm({ user_id: '', amount_euro: '', reason: '' })
      setSelectedEmployeeName('')
      setEmployeeSearch('')
      load()
      useAuthStore.getState().refreshBudget()
      addToast({ title: 'Adjustment created' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const openEdit = (adj: BudgetAdjustment) => {
    setEditTarget(adj)
    setEditForm({
      amount_euro: centsToEuroInput(adj.amount_cents),
      reason: adj.reason,
    })
  }

  const handleUpdate = async () => {
    if (!editTarget) return
    const amountCents = parseEuroToCents(editForm.amount_euro)
    if (amountCents === 0) {
      addToast({ title: 'Please enter an amount', variant: 'destructive' })
      return
    }
    try {
      await adminApi.updateAdjustment(editTarget.id, { amount_cents: amountCents, reason: editForm.reason })
      setEditTarget(null)
      load()
      useAuthStore.getState().refreshBudget()
      addToast({ title: 'Adjustment updated' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await adminApi.deleteAdjustment(deleteTarget.id)
      setDeleteTarget(null)
      load()
      useAuthStore.getState().refreshBudget()
      addToast({ title: 'Adjustment deleted' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const toggleSort = (column: 'date' | 'amount') => {
    if (column === 'date') {
      setSort(s => s === 'newest' ? 'oldest' : 'newest')
    } else {
      setSort(s => s === 'amount_desc' ? 'amount_asc' : 'amount_desc')
    }
    setPage(1)
  }

  const totalPages = Math.ceil(total / perPage)

  return (
    <div>
      {/* Sync Running Banner */}
      {syncRunning && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          <Loader2 className="h-4 w-4 animate-spin shrink-0" />
          <span>Purchase sync is running. Budget adjustments may change when finished.</span>
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Budget Adjustments</h1>
        <Button onClick={() => setShowCreateDialog(true)}><Plus className="h-4 w-4 mr-1" /> Add Adjustment</Button>
      </div>

      {/* Search bar */}
      <div className="relative mb-4 max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[hsl(var(--muted-foreground))]" />
        <Input
          placeholder="Search by employee or reason..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Table — same style as BrandsPage */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Employee</th>
                  <th className="text-right px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
                    <button onClick={() => toggleSort('amount')} className="inline-flex items-center gap-1 hover:text-[hsl(var(--foreground))]">
                      Amount <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Reason</th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Created By</th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
                    <button onClick={() => toggleSort('date')} className="inline-flex items-center gap-1 hover:text-[hsl(var(--foreground))]">
                      Date <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </th>
                  <th className="text-right px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {adjustments.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
                      No adjustments found.
                    </td>
                  </tr>
                ) : (
                  adjustments.map((a) => (
                    <tr key={a.id} className="border-b border-[hsl(var(--border))] hover:bg-[hsl(var(--muted)/0.5)]">
                      <td className="px-4 py-3">
                        <button
                          className="font-medium text-left hover:underline hover:text-[hsl(var(--primary))] transition-colors"
                          onClick={() => setSelectedUserId(a.user_id)}
                        >
                          {a.user_display_name || '—'}
                        </button>
                      </td>
                      <td className={`px-4 py-3 text-right font-medium ${a.amount_cents < 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {formatCents(a.amount_cents)}
                      </td>
                      <td className="px-4 py-3 max-w-xs truncate text-[hsl(var(--muted-foreground))]">{a.reason}</td>
                      <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">{a.creator_display_name || '—'}</td>
                      <td className="px-4 py-3 whitespace-nowrap text-[hsl(var(--muted-foreground))]">{formatDate(a.created_at)}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-1">
                          <Button size="sm" variant="ghost" onClick={() => openEdit(a)}>
                            <Pencil className="h-3 w-3" />
                          </Button>
                          <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleteTarget(a)}>
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-4">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
            Previous
          </Button>
          <span className="flex items-center px-3 text-sm">
            Page {page} of {totalPages}
          </span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
            Next
          </Button>
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Budget Adjustment</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div ref={dropdownRef} className="relative">
              {selectedEmployeeName ? (
                <div className="flex items-center gap-2 w-full rounded-md border px-3 py-2 text-sm">
                  <span className="flex-1">{selectedEmployeeName}</span>
                  <button onClick={clearEmployee} className="text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <Input
                  placeholder="Search employee by name or email *"
                  value={employeeSearch}
                  onChange={(e) => handleEmployeeSearch(e.target.value)}
                  onFocus={() => { if (employeeSearch.trim()) setShowEmployeeDropdown(true) }}
                />
              )}
              {showEmployeeDropdown && !selectedEmployeeName && employeeSearch.trim() && (
                <div className="absolute z-10 w-full mt-1 bg-[hsl(var(--background))] border rounded-md shadow-lg max-h-48 overflow-y-auto">
                  {searchResults.length === 0 ? (
                    <div className="px-3 py-2 text-sm text-[hsl(var(--muted-foreground))]">
                      {employeeSearch.length < 2 ? 'Type to search...' : 'No employees found'}
                    </div>
                  ) : (
                    searchResults.map(u => (
                      <button
                        key={u.id}
                        onClick={() => selectEmployee(u)}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-[hsl(var(--muted))] border-b last:border-b-0"
                      >
                        <div className="font-medium">{u.display_name}</div>
                        <div className="text-xs text-[hsl(var(--muted-foreground))]">{u.email}{u.department && ` · ${u.department}`}</div>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
            <Input
              placeholder="Amount in EUR (e.g. 150,00 or -50,00)"
              value={createForm.amount_euro}
              onChange={(e) => setCreateForm(f => ({ ...f, amount_euro: e.target.value }))}
            />
            <p className="text-xs text-[hsl(var(--muted-foreground))]">
              Positive = budget increase. Negative = budget deduction.
            </p>
            <textarea placeholder="Reason *" value={createForm.reason} onChange={(e) => setCreateForm(f => ({ ...f, reason: e.target.value }))}
              className="w-full rounded-md border px-3 py-2 text-sm min-h-[60px]" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={!createForm.user_id || !createForm.reason || !createForm.amount_euro}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={!!editTarget} onOpenChange={() => setEditTarget(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Budget Adjustment</DialogTitle></DialogHeader>
          {editTarget && (
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium">Employee</label>
                <div className="mt-1 px-3 py-2 rounded-md border bg-[hsl(var(--muted)/0.5)] text-sm">
                  {editTarget.user_display_name || '—'}
                </div>
              </div>
              <div>
                <label className="text-sm font-medium">Amount (EUR)</label>
                <Input
                  className="mt-1"
                  value={editForm.amount_euro}
                  onChange={(e) => setEditForm(f => ({ ...f, amount_euro: e.target.value }))}
                />
              </div>
              <div>
                <label className="text-sm font-medium">Reason</label>
                <textarea
                  value={editForm.reason}
                  onChange={(e) => setEditForm(f => ({ ...f, reason: e.target.value }))}
                  className="mt-1 w-full rounded-md border px-3 py-2 text-sm min-h-[60px]"
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditTarget(null)}>Cancel</Button>
            <Button onClick={handleUpdate} disabled={!editForm.reason || !editForm.amount_euro}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Delete Adjustment</DialogTitle></DialogHeader>
          {deleteTarget && (
            <div className="space-y-2">
              <p className="text-sm">Are you sure you want to delete this adjustment?</p>
              <div className="p-3 rounded-md bg-[hsl(var(--muted)/0.5)] text-sm space-y-1">
                <div><strong>Employee:</strong> {deleteTarget.user_display_name || '—'}</div>
                <div><strong>Amount:</strong> {formatCents(deleteTarget.amount_cents)}</div>
                <div><strong>Reason:</strong> {deleteTarget.reason}</div>
              </div>
              <p className="text-sm text-[hsl(var(--muted-foreground))]">This will recalculate the affected user's budget.</p>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete}>Delete</Button>
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
