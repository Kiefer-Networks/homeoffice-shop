import { useState, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { getErrorMessage } from '@/lib/error'
import { Save } from 'lucide-react'
import type { UserBudgetOverride } from '@/types'

interface BudgetOverrideFormProps {
  userId: string
  override?: UserBudgetOverride
  onSaved: () => void
  onCancel: () => void
}

export function BudgetOverrideForm({ userId, override, onSaved, onCancel }: BudgetOverrideFormProps) {
  const [form, setForm] = useState({
    effective_from: '', effective_until: '', initial_cents: '', yearly_increment_cents: '', reason: '',
  })
  const [saving, setSaving] = useState(false)
  const { addToast } = useUiStore()

  useEffect(() => {
    if (override) {
      setForm({
        effective_from: override.effective_from,
        effective_until: override.effective_until || '',
        initial_cents: String(override.initial_cents),
        yearly_increment_cents: String(override.yearly_increment_cents),
        reason: override.reason,
      })
    } else {
      setForm({ effective_from: '', effective_until: '', initial_cents: '', yearly_increment_cents: '', reason: '' })
    }
  }, [override])

  const handleSave = async () => {
    const initialCents = parseInt(form.initial_cents)
    const yearlyCents = parseInt(form.yearly_increment_cents)
    if (isNaN(initialCents) || isNaN(yearlyCents)) {
      addToast({ title: 'Invalid input', description: 'Budget amounts must be valid numbers', variant: 'destructive' })
      return
    }
    setSaving(true)
    try {
      const payload = {
        effective_from: form.effective_from,
        effective_until: form.effective_until || null,
        initial_cents: initialCents,
        yearly_increment_cents: yearlyCents,
        reason: form.reason,
      }
      if (override) {
        await adminApi.updateUserBudgetOverride(userId, override.id, payload)
      } else {
        await adminApi.createUserBudgetOverride(userId, payload)
      }
      addToast({ title: override ? 'Override updated' : 'Override created' })
      onSaved()
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="mb-3">
      <CardContent className="p-4 space-y-3">
        <h4 className="text-sm font-medium">{override ? 'Edit Override' : 'New Override'}</h4>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium">Effective From</label>
            <Input
              type="date"
              value={form.effective_from}
              onChange={e => setForm(f => ({ ...f, effective_from: e.target.value }))}
            />
          </div>
          <div>
            <label className="text-xs font-medium">Effective Until (optional)</label>
            <Input
              type="date"
              value={form.effective_until}
              onChange={e => setForm(f => ({ ...f, effective_until: e.target.value }))}
            />
          </div>
          <div>
            <label className="text-xs font-medium">Initial Budget (cents)</label>
            <Input
              type="number"
              value={form.initial_cents}
              onChange={e => setForm(f => ({ ...f, initial_cents: e.target.value }))}
              placeholder="75000"
            />
          </div>
          <div>
            <label className="text-xs font-medium">Yearly Increment (cents)</label>
            <Input
              type="number"
              value={form.yearly_increment_cents}
              onChange={e => setForm(f => ({ ...f, yearly_increment_cents: e.target.value }))}
              placeholder="25000"
            />
          </div>
        </div>
        <div>
          <label className="text-xs font-medium">Reason</label>
          <Input
            value={form.reason}
            onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
            placeholder="Reason for override..."
          />
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={handleSave}
            disabled={saving || !form.effective_from || !form.initial_cents || !form.reason}
          >
            <Save className="h-3.5 w-3.5 mr-1" /> {override ? 'Update' : 'Create'}
          </Button>
          <Button size="sm" variant="outline" onClick={onCancel}>Cancel</Button>
        </div>
      </CardContent>
    </Card>
  )
}
