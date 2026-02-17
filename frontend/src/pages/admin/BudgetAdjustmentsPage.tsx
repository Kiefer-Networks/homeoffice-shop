import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { formatCents, formatDate, parseEuroToCents } from '@/lib/utils'
import { Plus } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import type { BudgetAdjustment, UserAdmin } from '@/types'

export function AdminBudgetAdjustmentsPage() {
  const [adjustments, setAdjustments] = useState<BudgetAdjustment[]>([])
  const [users, setUsers] = useState<UserAdmin[]>([])
  const [showDialog, setShowDialog] = useState(false)
  const [form, setForm] = useState({ user_id: '', amount_euro: '', reason: '' })
  const { addToast } = useUiStore()

  const load = () => adminApi.listAdjustments({ per_page: 100 }).then(({ data }) => setAdjustments(data.items))
  useEffect(() => { load(); adminApi.listUsers({ per_page: 200 }).then(({ data }) => setUsers(data.items)) }, [])

  const handleCreate = async () => {
    const amountCents = parseEuroToCents(form.amount_euro)
    if (amountCents === 0) {
      addToast({ title: 'Bitte einen Betrag eingeben', variant: 'destructive' })
      return
    }
    try {
      await adminApi.createAdjustment({ user_id: form.user_id, amount_cents: amountCents, reason: form.reason })
      setShowDialog(false)
      setForm({ user_id: '', amount_euro: '', reason: '' })
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
            <select value={form.user_id} onChange={(e) => setForm(f => ({ ...f, user_id: e.target.value }))}
              className="w-full rounded-md border px-3 py-2 text-sm">
              <option value="">Select Employee *</option>
              {users.map(u => <option key={u.id} value={u.id}>{u.display_name} ({u.email})</option>)}
            </select>
            <Input
              placeholder="Betrag in Euro (z.B. 150,00 oder -50,00)"
              value={form.amount_euro}
              onChange={(e) => setForm(f => ({ ...f, amount_euro: e.target.value }))}
            />
            <p className="text-xs text-[hsl(var(--muted-foreground))]">
              Negativ = Abzug. Beispiel: -100,00 zieht 100 EUR ab.
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
