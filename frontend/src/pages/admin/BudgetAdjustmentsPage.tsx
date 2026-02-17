import { useEffect, useState, useMemo, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { formatCents, formatDate, parseEuroToCents } from '@/lib/utils'
import { Plus, X } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import type { BudgetAdjustment, UserAdmin } from '@/types'

export function AdminBudgetAdjustmentsPage() {
  const [adjustments, setAdjustments] = useState<BudgetAdjustment[]>([])
  const [users, setUsers] = useState<UserAdmin[]>([])
  const [showDialog, setShowDialog] = useState(false)
  const [form, setForm] = useState({ user_id: '', amount_euro: '', reason: '' })
  const [employeeSearch, setEmployeeSearch] = useState('')
  const [showEmployeeDropdown, setShowEmployeeDropdown] = useState(false)
  const [selectedEmployeeName, setSelectedEmployeeName] = useState('')
  const dropdownRef = useRef<HTMLDivElement>(null)
  const { addToast } = useUiStore()

  const load = () => adminApi.listAdjustments({ per_page: 100 }).then(({ data }) => setAdjustments(data.items))
  useEffect(() => { load(); adminApi.listUsers({ per_page: 200 }).then(({ data }) => setUsers(data.items)) }, [])

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

  const filteredUsers = useMemo(() => {
    if (!employeeSearch.trim()) return users
    const search = employeeSearch.toLowerCase()
    return users.filter(u =>
      u.display_name.toLowerCase().includes(search) ||
      u.email.toLowerCase().includes(search)
    )
  }, [users, employeeSearch])

  const selectEmployee = (user: UserAdmin) => {
    setForm(f => ({ ...f, user_id: user.id }))
    setSelectedEmployeeName(`${user.display_name} (${user.email})`)
    setEmployeeSearch('')
    setShowEmployeeDropdown(false)
  }

  const clearEmployee = () => {
    setForm(f => ({ ...f, user_id: '' }))
    setSelectedEmployeeName('')
    setEmployeeSearch('')
  }

  const handleCreate = async () => {
    if (!form.user_id) {
      addToast({ title: 'Please select an employee', variant: 'destructive' })
      return
    }
    const amountCents = parseEuroToCents(form.amount_euro)
    if (amountCents === 0) {
      addToast({ title: 'Please enter an amount', variant: 'destructive' })
      return
    }
    try {
      await adminApi.createAdjustment({ user_id: form.user_id, amount_cents: amountCents, reason: form.reason })
      setShowDialog(false)
      setForm({ user_id: '', amount_euro: '', reason: '' })
      setSelectedEmployeeName('')
      setEmployeeSearch('')
      load()
      addToast({ title: 'Adjustment created' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Budget Adjustments</h1>
        <Button onClick={() => setShowDialog(true)}><Plus className="h-4 w-4 mr-1" /> Add Adjustment</Button>
      </div>
      <div className="space-y-2">
        {adjustments.map((a) => {
          const userName = users.find(u => u.id === a.user_id)?.display_name
          return (
            <Card key={a.id}>
              <CardContent className="flex items-center justify-between p-4">
                <div>
                  <div className="font-medium">{formatCents(a.amount_cents)}</div>
                  <div className="text-sm text-[hsl(var(--muted-foreground))]">{a.reason}</div>
                  <div className="text-xs text-[hsl(var(--muted-foreground))]">
                    {userName && <span>{userName} — </span>}{formatDate(a.created_at)}
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        })}
        {adjustments.length === 0 && <p className="text-[hsl(var(--muted-foreground))]">No adjustments yet.</p>}
      </div>
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Budget Adjustment</DialogTitle></DialogHeader>
          <div className="space-y-3">
            {/* Employee autocomplete */}
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
                  onChange={(e) => {
                    setEmployeeSearch(e.target.value)
                    setShowEmployeeDropdown(true)
                  }}
                  onFocus={() => setShowEmployeeDropdown(true)}
                />
              )}
              {showEmployeeDropdown && !selectedEmployeeName && (
                <div className="absolute z-10 w-full mt-1 bg-[hsl(var(--background))] border rounded-md shadow-lg max-h-48 overflow-y-auto">
                  {filteredUsers.length === 0 ? (
                    <div className="px-3 py-2 text-sm text-[hsl(var(--muted-foreground))]">No employees found</div>
                  ) : (
                    filteredUsers.map(u => (
                      <button
                        key={u.id}
                        onClick={() => selectEmployee(u)}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-[hsl(var(--muted))] border-b last:border-b-0"
                      >
                        <div className="font-medium">{u.display_name}</div>
                        <div className="text-xs text-[hsl(var(--muted-foreground))]">{u.email}</div>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
            <Input
              placeholder="Amount in EUR (e.g. 150.00 or -50.00)"
              value={form.amount_euro}
              onChange={(e) => setForm(f => ({ ...f, amount_euro: e.target.value }))}
            />
            <p className="text-xs text-[hsl(var(--muted-foreground))]">
              Negative = deduction. Example: -100.00 deducts 100 EUR.
            </p>
            <textarea placeholder="Reason *" value={form.reason} onChange={(e) => setForm(f => ({ ...f, reason: e.target.value }))}
              className="w-full rounded-md border px-3 py-2 text-sm min-h-[60px]" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={!form.user_id || !form.reason || !form.amount_euro}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
