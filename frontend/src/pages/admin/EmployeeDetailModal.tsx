import { useEffect, useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { formatCents, formatDate } from '@/lib/utils'
import { getErrorMessage } from '@/lib/error'
import { Plus, Pencil, Trash2, Save } from 'lucide-react'
import type { UserDetailResponse, UserBudgetOverride, UserPurchaseReview } from '@/types'

function EmployeeAvatar({ name, avatarUrl, size = 48 }: { name: string; avatarUrl?: string | null; size?: number }) {
  const [imgError, setImgError] = useState(false)

  const initials = name
    .split(' ')
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  const hue = Math.abs(hash) % 360

  if (avatarUrl && !imgError) {
    return (
      <img
        src={avatarUrl}
        alt={name}
        className="rounded-full object-cover shrink-0"
        style={{ width: size, height: size }}
        onError={() => setImgError(true)}
      />
    )
  }

  return (
    <div
      className="rounded-full flex items-center justify-center text-white font-medium shrink-0"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.38,
        backgroundColor: `hsl(${hue}, 55%, 50%)`,
      }}
    >
      {initials}
    </div>
  )
}

const statusVariant: Record<string, 'default' | 'secondary' | 'success' | 'destructive' | 'warning'> = {
  pending: 'warning', ordered: 'default', delivered: 'success', rejected: 'destructive', cancelled: 'secondary',
}

const purchaseStatusVariant: Record<string, 'default' | 'secondary' | 'success' | 'destructive' | 'warning'> = {
  pending: 'warning', matched: 'success', adjusted: 'default', dismissed: 'secondary',
}

interface EmployeeDetailModalProps {
  userId: string | null
  onClose: () => void
}

export function EmployeeDetailModal({ userId, onClose }: EmployeeDetailModalProps) {
  const [data, setData] = useState<UserDetailResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const { addToast } = useUiStore()

  // Override form state
  const [showOverrideForm, setShowOverrideForm] = useState(false)
  const [editingOverride, setEditingOverride] = useState<UserBudgetOverride | null>(null)
  const [overrideForm, setOverrideForm] = useState({
    effective_from: '', effective_until: '', initial_cents: '', yearly_increment_cents: '', reason: '',
  })
  const [savingOverride, setSavingOverride] = useState(false)

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

  const reload = () => {
    if (!userId) return
    adminApi.getUserDetail(userId).then(({ data }) => setData(data))
  }

  const openOverrideForm = (override?: UserBudgetOverride) => {
    if (override) {
      setEditingOverride(override)
      setOverrideForm({
        effective_from: override.effective_from,
        effective_until: override.effective_until || '',
        initial_cents: String(override.initial_cents),
        yearly_increment_cents: String(override.yearly_increment_cents),
        reason: override.reason,
      })
    } else {
      setEditingOverride(null)
      setOverrideForm({ effective_from: '', effective_until: '', initial_cents: '', yearly_increment_cents: '', reason: '' })
    }
    setShowOverrideForm(true)
  }

  const handleSaveOverride = async () => {
    if (!userId) return
    setSavingOverride(true)
    try {
      const payload = {
        effective_from: overrideForm.effective_from,
        effective_until: overrideForm.effective_until || null,
        initial_cents: parseInt(overrideForm.initial_cents),
        yearly_increment_cents: parseInt(overrideForm.yearly_increment_cents),
        reason: overrideForm.reason,
      }
      if (editingOverride) {
        await adminApi.updateUserBudgetOverride(userId, editingOverride.id, payload)
      } else {
        await adminApi.createUserBudgetOverride(userId, payload)
      }
      setShowOverrideForm(false)
      addToast({ title: editingOverride ? 'Override updated' : 'Override created' })
      reload()
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setSavingOverride(false)
    }
  }

  const handleDeleteOverride = async (overrideId: string) => {
    if (!userId || !confirm('Delete this budget override?')) return
    try {
      await adminApi.deleteUserBudgetOverride(userId, overrideId)
      addToast({ title: 'Override deleted' })
      reload()
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

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
              <div className="flex items-center gap-3">
                <EmployeeAvatar name={data.user.display_name} avatarUrl={data.user.avatar_url} size={48} />
                <div>
                  <DialogTitle>{data.user.display_name}</DialogTitle>
                  <p className="text-sm text-[hsl(var(--muted-foreground))]">
                    {data.user.email}{data.user.department ? ` — ${data.user.department}` : ''}
                  </p>
                </div>
              </div>
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

            {/* Budget Timeline */}
            {data.budget_timeline && data.budget_timeline.length > 0 && (
              <div>
                <h3 className="text-sm font-medium mb-2">Budget Timeline</h3>
                <Card>
                  <CardContent className="p-0">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                            <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Year</th>
                            <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Period</th>
                            <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Amount</th>
                            <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Cumulative</th>
                            <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Source</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.budget_timeline.map((entry, i) => (
                            <tr key={i} className="border-b border-[hsl(var(--border))] last:border-b-0">
                              <td className="px-4 py-2">{entry.year}</td>
                              <td className="px-4 py-2 text-[hsl(var(--muted-foreground))]">
                                {entry.period_from} — {entry.period_to}
                              </td>
                              <td className="px-4 py-2 text-right">{formatCents(entry.amount_cents)}</td>
                              <td className="px-4 py-2 text-right font-medium">{formatCents(entry.cumulative_cents)}</td>
                              <td className="px-4 py-2">
                                <Badge variant={entry.source === 'override' ? 'warning' : 'secondary'}>
                                  {entry.source}
                                </Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}

            {/* Budget Overrides */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium">Budget Overrides ({data.budget_overrides?.length || 0})</h3>
                <Button size="sm" variant="outline" onClick={() => openOverrideForm()}>
                  <Plus className="h-3.5 w-3.5 mr-1" /> Add Override
                </Button>
              </div>

              {showOverrideForm && (
                <Card className="mb-3">
                  <CardContent className="p-4 space-y-3">
                    <h4 className="text-sm font-medium">{editingOverride ? 'Edit Override' : 'New Override'}</h4>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-medium">Effective From</label>
                        <Input
                          type="date"
                          value={overrideForm.effective_from}
                          onChange={e => setOverrideForm(f => ({ ...f, effective_from: e.target.value }))}
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium">Effective Until (optional)</label>
                        <Input
                          type="date"
                          value={overrideForm.effective_until}
                          onChange={e => setOverrideForm(f => ({ ...f, effective_until: e.target.value }))}
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium">Initial Budget (cents)</label>
                        <Input
                          type="number"
                          value={overrideForm.initial_cents}
                          onChange={e => setOverrideForm(f => ({ ...f, initial_cents: e.target.value }))}
                          placeholder="75000"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium">Yearly Increment (cents)</label>
                        <Input
                          type="number"
                          value={overrideForm.yearly_increment_cents}
                          onChange={e => setOverrideForm(f => ({ ...f, yearly_increment_cents: e.target.value }))}
                          placeholder="25000"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="text-xs font-medium">Reason</label>
                      <Input
                        value={overrideForm.reason}
                        onChange={e => setOverrideForm(f => ({ ...f, reason: e.target.value }))}
                        placeholder="Reason for override..."
                      />
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={handleSaveOverride}
                        disabled={savingOverride || !overrideForm.effective_from || !overrideForm.initial_cents || !overrideForm.reason}
                      >
                        <Save className="h-3.5 w-3.5 mr-1" /> {editingOverride ? 'Update' : 'Create'}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setShowOverrideForm(false)}>Cancel</Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {(data.budget_overrides?.length || 0) === 0 && !showOverrideForm ? (
                <p className="text-sm text-[hsl(var(--muted-foreground))]">No budget overrides.</p>
              ) : data.budget_overrides && data.budget_overrides.length > 0 ? (
                <Card>
                  <CardContent className="p-0">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                            <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Period</th>
                            <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Initial</th>
                            <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Increment</th>
                            <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Reason</th>
                            <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.budget_overrides.map((ov) => (
                            <tr key={ov.id} className="border-b border-[hsl(var(--border))] last:border-b-0">
                              <td className="px-4 py-2">
                                {ov.effective_from}{ov.effective_until ? ` — ${ov.effective_until}` : ' — ongoing'}
                              </td>
                              <td className="px-4 py-2 text-right">{formatCents(ov.initial_cents)}</td>
                              <td className="px-4 py-2 text-right">{formatCents(ov.yearly_increment_cents)}</td>
                              <td className="px-4 py-2 text-[hsl(var(--muted-foreground))]">{ov.reason}</td>
                              <td className="px-4 py-2 text-right">
                                <div className="flex justify-end gap-1">
                                  <Button size="sm" variant="ghost" onClick={() => openOverrideForm(ov)}>
                                    <Pencil className="h-3.5 w-3.5" />
                                  </Button>
                                  <Button size="sm" variant="ghost" onClick={() => handleDeleteOverride(ov.id)}>
                                    <Trash2 className="h-3.5 w-3.5 text-red-500" />
                                  </Button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              ) : null}
            </div>

            {/* HiBob Purchases */}
            <div>
              <h3 className="text-sm font-medium mb-2">HiBob Purchases ({data.purchase_reviews?.length || 0})</h3>
              {(data.purchase_reviews?.length || 0) === 0 ? (
                <p className="text-sm text-[hsl(var(--muted-foreground))]">No HiBob purchases synced.</p>
              ) : (
                <Card>
                  <CardContent className="p-0">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                            <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Date</th>
                            <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Description</th>
                            <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Amount</th>
                            <th className="text-center px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.purchase_reviews.map((pr: UserPurchaseReview) => (
                            <tr key={pr.id} className="border-b border-[hsl(var(--border))] last:border-b-0">
                              <td className="px-4 py-2 whitespace-nowrap">{formatDate(pr.entry_date)}</td>
                              <td className="px-4 py-2">{pr.description}</td>
                              <td className="px-4 py-2 text-right whitespace-nowrap font-medium text-red-600">
                                {formatCents(pr.amount_cents)}
                              </td>
                              <td className="px-4 py-2 text-center">
                                <Badge variant={purchaseStatusVariant[pr.status]}>{pr.status}</Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>

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
