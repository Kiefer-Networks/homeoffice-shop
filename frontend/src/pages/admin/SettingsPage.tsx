import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { Save } from 'lucide-react'
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

export function AdminSettingsPage() {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [dirty, setDirty] = useState<Set<string>>(new Set())
  const { addToast } = useUiStore()

  useEffect(() => { adminApi.getSettings().then(({ data }) => setSettings(data.settings)) }, [])

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

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Settings</h1>
        <Button onClick={handleSave} disabled={dirty.size === 0}><Save className="h-4 w-4 mr-1" /> Save Changes</Button>
      </div>
      <Card>
        <CardContent className="space-y-4 pt-6">
          {Object.entries(settingLabels).map(([key, { label, description }]) => (
            <div key={key}>
              <label className="text-sm font-medium">{label}</label>
              <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">{description}</p>
              <Input value={settings[key] || ''} onChange={(e) => handleChange(key, e.target.value)} />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
