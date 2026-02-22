import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { Save, Send, Plus, Pencil, Trash2 } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import { formatCents } from '@/lib/utils'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import type { BudgetRule } from '@/types'

const generalSettings: Record<string, { label: string; description: string }> = {
  probation_months: { label: 'Probation Period (months)', description: 'Months before employee can order' },
  price_refresh_cooldown_minutes: { label: 'Price Refresh Cooldown (min)', description: 'Minutes between global price refreshes' },
  price_refresh_rate_limit_per_minute: { label: 'Price Refresh Rate Limit', description: 'Max Amazon price lookups per minute' },
  company_name: { label: 'Company Name', description: 'Displayed in emails and UI' },
  cart_stale_days: { label: 'Cart Stale Days', description: 'Auto-cleanup cart items older than this' },
}

const smtpSettings: Record<string, { label: string; description: string; row: number; type?: string }> = {
  smtp_host: { label: 'SMTP Host', description: 'e.g. smtp.gmail.com', row: 1 },
  smtp_port: { label: 'SMTP Port', description: '587 for STARTTLS, 465 for SSL', row: 1 },
  smtp_username: { label: 'SMTP Username', description: 'Authentication username', row: 2 },
  smtp_password: { label: 'SMTP Password', description: 'Authentication password', row: 2, type: 'password' },
  smtp_from_address: { label: 'From Address', description: 'Sender email address', row: 3 },
  smtp_use_tls: { label: 'Use TLS', description: 'Enable TLS encryption', row: 3, type: 'checkbox' },
}

export function AdminSettingsPage() {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [generalDirty, setGeneralDirty] = useState<Set<string>>(new Set())
  const [smtpDirty, setSmtpDirty] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [testEmail, setTestEmail] = useState('')
  const [sendingTest, setSendingTest] = useState(false)
  const [savingGeneral, setSavingGeneral] = useState(false)
  const [savingSmtp, setSavingSmtp] = useState(false)
  const { addToast } = useUiStore()
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'admin'

  // HiBob Purchase Sync settings
  const [purchaseDirty, setPurchaseDirty] = useState<Set<string>>(new Set())
  const [savingPurchase, setSavingPurchase] = useState(false)

  // Budget rules state
  const [rules, setRules] = useState<BudgetRule[]>([])
  const [rulesLoading, setRulesLoading] = useState(true)
  const [editingRule, setEditingRule] = useState<BudgetRule | null>(null)
  const [showRuleForm, setShowRuleForm] = useState(false)
  const [ruleForm, setRuleForm] = useState({ effective_from: '', initial_cents: '', yearly_increment_cents: '' })
  const [savingRule, setSavingRule] = useState(false)
  const [deleteRuleTarget, setDeleteRuleTarget] = useState<string | null>(null)
  useEffect(() => {
    if (isAdmin) {
      adminApi.getSettings()
        .then(({ data }) => setSettings(data.settings))
        .catch(() => addToast({ title: 'Failed to load settings', variant: 'destructive' }))
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
    loadRules()
  }, [])

  const loadRules = () => {
    adminApi.listBudgetRules()
      .then(({ data }) => setRules(data))
      .catch(() => addToast({ title: 'Failed to load budget rules', variant: 'destructive' }))
      .finally(() => setRulesLoading(false))
  }

  const handleChange = (key: string, value: string, group: 'general' | 'smtp') => {
    setSettings(s => ({ ...s, [key]: value }))
    if (group === 'general') {
      setGeneralDirty(d => new Set(d).add(key))
    } else {
      setSmtpDirty(d => new Set(d).add(key))
    }
  }

  const saveGroup = async (dirty: Set<string>, setDirty: (s: Set<string>) => void, setSaving: (b: boolean) => void) => {
    setSaving(true)
    try {
      for (const key of dirty) {
        await adminApi.updateSetting(key, settings[key])
      }
      setDirty(new Set())
      addToast({ title: 'Settings saved' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  const handleSendTestEmail = async () => {
    if (!testEmail) return
    setSendingTest(true)
    try {
      await adminApi.sendTestEmail(testEmail)
      addToast({ title: 'Test email sent successfully' })
    } catch (err: unknown) {
      addToast({ title: 'Test email failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setSendingTest(false)
    }
  }

  const openRuleForm = (rule?: BudgetRule) => {
    if (rule) {
      setEditingRule(rule)
      setRuleForm({
        effective_from: rule.effective_from,
        initial_cents: String(rule.initial_cents),
        yearly_increment_cents: String(rule.yearly_increment_cents),
      })
    } else {
      setEditingRule(null)
      setRuleForm({ effective_from: '', initial_cents: '', yearly_increment_cents: '' })
    }
    setShowRuleForm(true)
  }

  const handleSaveRule = async () => {
    setSavingRule(true)
    try {
      const data = {
        effective_from: ruleForm.effective_from,
        initial_cents: parseInt(ruleForm.initial_cents),
        yearly_increment_cents: parseInt(ruleForm.yearly_increment_cents),
      }
      if (editingRule) {
        await adminApi.updateBudgetRule(editingRule.id, data)
      } else {
        await adminApi.createBudgetRule(data)
      }
      setShowRuleForm(false)
      addToast({ title: editingRule ? 'Rule updated' : 'Rule created' })
      loadRules()
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setSavingRule(false)
    }
  }

  const confirmDeleteRule = async () => {
    if (!deleteRuleTarget) return
    try {
      await adminApi.deleteBudgetRule(deleteRuleTarget)
      addToast({ title: 'Rule deleted' })
      loadRules()
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setDeleteRuleTarget(null)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      {loading ? (
        <Card>
          <CardContent className="space-y-4 pt-6">
            {[...Array(4)].map((_, i) => <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />)}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* General Settings (admin only) */}
          {isAdmin && (
            <Card>
              <CardContent className="space-y-4 pt-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">General</h2>
                  <Button
                    size="sm"
                    onClick={() => saveGroup(generalDirty, setGeneralDirty, setSavingGeneral)}
                    disabled={generalDirty.size === 0 || savingGeneral}
                  >
                    <Save className="h-4 w-4 mr-1" /> Save
                  </Button>
                </div>
                {Object.entries(generalSettings).map(([key, { label, description }]) => (
                  <div key={key}>
                    <label className="text-sm font-medium">{label}</label>
                    <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">{description}</p>
                    <Input
                      value={settings[key] || ''}
                      onChange={(e) => handleChange(key, e.target.value, 'general')}
                    />
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* SMTP Settings (admin only) */}
          {isAdmin && (
            <Card>
              <CardContent className="space-y-4 pt-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">Email / SMTP</h2>
                  <Button
                    size="sm"
                    onClick={() => saveGroup(smtpDirty, setSmtpDirty, setSavingSmtp)}
                    disabled={smtpDirty.size === 0 || savingSmtp}
                  >
                    <Save className="h-4 w-4 mr-1" /> Save
                  </Button>
                </div>
                {[1, 2, 3].map(row => (
                  <div key={row} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {Object.entries(smtpSettings)
                      .filter(([, meta]) => meta.row === row)
                      .map(([key, { label, description, type }]) => (
                        <div key={key}>
                          <label className="text-sm font-medium">{label}</label>
                          <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">{description}</p>
                          {type === 'checkbox' ? (
                            <label className="flex items-center gap-2 mt-1 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={(settings[key] || '').toLowerCase() === 'true'}
                                onChange={(e) => handleChange(key, e.target.checked ? 'true' : 'false', 'smtp')}
                                className="h-4 w-4 rounded border-gray-300"
                              />
                              <span className="text-sm">{(settings[key] || '').toLowerCase() === 'true' ? 'Enabled' : 'Disabled'}</span>
                            </label>
                          ) : (
                            <Input
                              type={type || 'text'}
                              value={settings[key] || ''}
                              onChange={(e) => handleChange(key, e.target.value, 'smtp')}
                            />
                          )}
                        </div>
                      ))}
                  </div>
                ))}

                <div className="border-t pt-4 mt-4">
                  <h3 className="text-sm font-medium mb-2">Send Test Email</h3>
                  <div className="flex gap-2">
                    <Input
                      type="email"
                      placeholder="admin@company.com"
                      value={testEmail}
                      onChange={(e) => setTestEmail(e.target.value)}
                      className="max-w-sm"
                    />
                    <Button
                      onClick={handleSendTestEmail}
                      disabled={!testEmail || sendingTest}
                      variant="outline"
                    >
                      <Send className="h-4 w-4 mr-1" />
                      {sendingTest ? 'Sending...' : 'Send Test'}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* HiBob Purchase Sync (admin only) */}
          {isAdmin && (
            <Card>
              <CardContent className="space-y-4 pt-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">HiBob Purchase Sync</h2>
                  <Button
                    size="sm"
                    onClick={() => saveGroup(purchaseDirty, setPurchaseDirty, setSavingPurchase)}
                    disabled={purchaseDirty.size === 0 || savingPurchase}
                  >
                    <Save className="h-4 w-4 mr-1" /> Save
                  </Button>
                </div>
                {[
                  { key: 'hibob_purchase_table_id', label: 'Table ID', description: 'HiBob custom table ID for purchases' },
                  { key: 'hibob_purchase_col_date', label: 'Column: Date', description: 'Column name for purchase date' },
                  { key: 'hibob_purchase_col_description', label: 'Column: Description', description: 'Column name for description' },
                  { key: 'hibob_purchase_col_amount', label: 'Column: Amount', description: 'Column name for amount' },
                  { key: 'hibob_purchase_col_currency', label: 'Column: Currency', description: 'Column name for currency' },
                ].map(({ key, label, description }) => (
                  <div key={key}>
                    <label className="text-sm font-medium">{label}</label>
                    <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">{description}</p>
                    <Input
                      value={settings[key] || ''}
                      onChange={(e) => {
                        setSettings(s => ({ ...s, [key]: e.target.value }))
                        setPurchaseDirty(d => new Set(d).add(key))
                      }}
                    />
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Budget Rules (staff visible) */}
          <Card>
            <CardContent className="space-y-4 pt-6">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Budget Rules</h2>
                <Button size="sm" onClick={() => openRuleForm()}>
                  <Plus className="h-4 w-4 mr-1" /> Add Rule
                </Button>
              </div>

              {showRuleForm && (
                <div className="border rounded-lg p-4 space-y-3 bg-[hsl(var(--muted))]">
                  <h3 className="text-sm font-medium">{editingRule ? 'Edit Rule' : 'New Budget Rule'}</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs font-medium">Effective From</label>
                      <Input
                        type="date"
                        value={ruleForm.effective_from}
                        onChange={e => setRuleForm(f => ({ ...f, effective_from: e.target.value }))}
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium">Initial Budget (cents)</label>
                      <Input
                        type="number"
                        value={ruleForm.initial_cents}
                        onChange={e => setRuleForm(f => ({ ...f, initial_cents: e.target.value }))}
                        placeholder="75000"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium">Yearly Increment (cents)</label>
                      <Input
                        type="number"
                        value={ruleForm.yearly_increment_cents}
                        onChange={e => setRuleForm(f => ({ ...f, yearly_increment_cents: e.target.value }))}
                        placeholder="25000"
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={handleSaveRule} disabled={savingRule || !ruleForm.effective_from || !ruleForm.initial_cents}>
                      <Save className="h-4 w-4 mr-1" /> {editingRule ? 'Update' : 'Create'}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setShowRuleForm(false)}>Cancel</Button>
                  </div>
                </div>
              )}

              {rulesLoading ? (
                <div className="h-20 bg-gray-100 rounded animate-pulse" />
              ) : rules.length === 0 ? (
                <p className="text-sm text-[hsl(var(--muted-foreground))]">No budget rules configured.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                        <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Effective From</th>
                        <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Initial Budget</th>
                        <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Yearly Increment</th>
                        <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rules.map(rule => (
                        <tr key={rule.id} className="border-b border-[hsl(var(--border))] last:border-b-0">
                          <td className="px-4 py-2">{rule.effective_from}</td>
                          <td className="px-4 py-2 text-right">{formatCents(rule.initial_cents)}</td>
                          <td className="px-4 py-2 text-right">{formatCents(rule.yearly_increment_cents)}</td>
                          <td className="px-4 py-2 text-right">
                            <div className="flex justify-end gap-1">
                              <Button size="sm" variant="ghost" onClick={() => openRuleForm(rule)}>
                                <Pencil className="h-3.5 w-3.5" />
                              </Button>
                              {isAdmin && rules.length > 1 && (
                                <Button size="sm" variant="ghost" onClick={() => setDeleteRuleTarget(rule.id)}>
                                  <Trash2 className="h-3.5 w-3.5 text-red-500" />
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      <ConfirmDialog
        open={!!deleteRuleTarget}
        onClose={() => setDeleteRuleTarget(null)}
        onConfirm={confirmDeleteRule}
        title="Delete Budget Rule"
        description="Are you sure you want to delete this budget rule? This action cannot be undone."
      />
    </div>
  )
}
