import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { Save, Send } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'

const settingLabels: Record<string, { label: string; description: string }> = {
  budget_initial_cents: { label: 'Initial Budget (cents)', description: 'First-year budget in cents (e.g. 75000 = 750 EUR)' },
  budget_yearly_increment_cents: { label: 'Yearly Increment (cents)', description: 'Annual budget increase in cents' },
  probation_months: { label: 'Probation Period (months)', description: 'Months before employee can order' },
  price_refresh_cooldown_minutes: { label: 'Price Refresh Cooldown (min)', description: 'Minutes between global price refreshes' },
  price_refresh_rate_limit_per_minute: { label: 'Price Refresh Rate Limit', description: 'Max Amazon price lookups per minute' },
  company_name: { label: 'Company Name', description: 'Displayed in emails and UI' },
  cart_stale_days: { label: 'Cart Stale Days', description: 'Auto-cleanup cart items older than this' },
}

const smtpLabels: Record<string, { label: string; description: string }> = {
  smtp_host: { label: 'SMTP Host', description: 'e.g. smtp.gmail.com' },
  smtp_port: { label: 'SMTP Port', description: '587 for STARTTLS, 465 for SSL' },
  smtp_username: { label: 'SMTP Username', description: 'Authentication username' },
  smtp_password: { label: 'SMTP Password', description: 'Authentication password' },
  smtp_use_tls: { label: 'Use TLS', description: 'true or false' },
  smtp_from_address: { label: 'From Address', description: 'Sender email address' },
  smtp_from_name: { label: 'From Name', description: 'Sender display name' },
}

export function AdminSettingsPage() {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [dirty, setDirty] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [testEmail, setTestEmail] = useState('')
  const [sendingTest, setSendingTest] = useState(false)
  const { addToast } = useUiStore()

  useEffect(() => {
    adminApi.getSettings()
      .then(({ data }) => setSettings(data.settings))
      .catch(() => addToast({ title: 'Failed to load settings', variant: 'destructive' }))
      .finally(() => setLoading(false))
  }, [])

  const handleChange = (key: string, value: string) => {
    setSettings(s => ({ ...s, [key]: value }))
    setDirty(d => new Set(d).add(key))
  }

  const handleSave = async () => {
    try {
      for (const key of dirty) {
        await adminApi.updateSetting(key, settings[key])
      }
      setDirty(new Set())
      addToast({ title: 'Settings saved' })
    } catch (err: unknown) { addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' }) }
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

  const renderField = (key: string, label: string, description: string) => (
    <div key={key}>
      <label className="text-sm font-medium">{label}</label>
      <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">{description}</p>
      <Input
        type={key === 'smtp_password' ? 'password' : 'text'}
        value={settings[key] || ''}
        onChange={(e) => handleChange(key, e.target.value)}
      />
    </div>
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Settings</h1>
        <Button onClick={handleSave} disabled={dirty.size === 0}><Save className="h-4 w-4 mr-1" /> Save Changes</Button>
      </div>

      {loading ? (
        <Card>
          <CardContent className="space-y-4 pt-6">
            {[...Array(4)].map((_, i) => <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />)}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          <Card>
            <CardContent className="space-y-4 pt-6">
              <h2 className="text-lg font-semibold">General</h2>
              {Object.entries(settingLabels).map(([key, { label, description }]) =>
                renderField(key, label, description)
              )}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="space-y-4 pt-6">
              <h2 className="text-lg font-semibold">Email / SMTP</h2>
              {Object.entries(smtpLabels).map(([key, { label, description }]) =>
                renderField(key, label, description)
              )}

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
        </div>
      )}
    </div>
  )
}
