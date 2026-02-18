import { useState, useEffect } from 'react'
import { Mail, Save, Loader2, User as UserIcon, Building, Calendar, Shield } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import type { NotificationPrefs } from '@/types'

const EVENT_LABELS: Record<string, string> = {
  'order.created': 'New Orders',
  'order.status_changed': 'Order Status Changes',
  'order.cancelled': 'Order Cancellations',
  'hibob.sync': 'HiBob Sync Complete',
  'hibob.sync_error': 'HiBob Sync Errors',
  'hibob.purchase_review': 'HiBob Purchase Reviews',
  'price.refresh': 'Price Refresh Complete',
}

export function ProfilePage() {
  const { user } = useAuthStore()
  const { addToast } = useUiStore()
  const isStaff = user?.role === 'admin' || user?.role === 'manager'

  const [prefs, setPrefs] = useState<NotificationPrefs | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!isStaff) return
    setLoading(true)
    adminApi.getNotificationPrefs()
      .then(({ data }) => setPrefs(data))
      .catch(() => addToast({ title: 'Failed to load notification preferences', variant: 'destructive' }))
      .finally(() => setLoading(false))
  }, [isStaff])

  const handleToggle = (channel: 'slack' | 'email', enabled: boolean) => {
    if (!prefs) return
    if (channel === 'slack') {
      setPrefs({ ...prefs, slack_enabled: enabled })
    } else {
      setPrefs({ ...prefs, email_enabled: enabled })
    }
  }

  const handleEventToggle = (channel: 'slack' | 'email', event: string, checked: boolean) => {
    if (!prefs) return
    const key = channel === 'slack' ? 'slack_events' : 'email_events'
    const current = prefs[key]
    const updated = checked ? [...current, event] : current.filter(e => e !== event)
    setPrefs({ ...prefs, [key]: updated })
  }

  const handleSave = async () => {
    if (!prefs) return
    setSaving(true)
    try {
      const { data } = await adminApi.updateNotificationPrefs({
        slack_enabled: prefs.slack_enabled,
        slack_events: prefs.slack_events,
        email_enabled: prefs.email_enabled,
        email_events: prefs.email_events,
      })
      setPrefs(data)
      addToast({ title: 'Notification preferences saved' })
    } catch {
      addToast({ title: 'Failed to save preferences', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  const memberSince = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
    : null

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
      <h1 className="text-2xl font-bold">Profile</h1>

      {/* User Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserIcon className="h-5 w-5" />
            Personal Information
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4">
            <div>
              <dt className="text-sm text-[hsl(var(--muted-foreground))]">Name</dt>
              <dd className="font-medium">{user?.display_name}</dd>
            </div>
            <div>
              <dt className="text-sm text-[hsl(var(--muted-foreground))]">Email</dt>
              <dd className="font-medium">{user?.email}</dd>
            </div>
            {user?.department && (
              <div>
                <dt className="text-sm text-[hsl(var(--muted-foreground))] flex items-center gap-1">
                  <Building className="h-3.5 w-3.5" /> Department
                </dt>
                <dd className="font-medium">{user.department}</dd>
              </div>
            )}
            <div>
              <dt className="text-sm text-[hsl(var(--muted-foreground))] flex items-center gap-1">
                <Shield className="h-3.5 w-3.5" /> Role
              </dt>
              <dd className="font-medium capitalize">{user?.role}</dd>
            </div>
            {memberSince && (
              <div>
                <dt className="text-sm text-[hsl(var(--muted-foreground))] flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5" /> Member Since
                </dt>
                <dd className="font-medium">{memberSince}</dd>
              </div>
            )}
          </dl>
        </CardContent>
      </Card>

      {/* Notification Preferences (staff only) */}
      {isStaff && (
        <>
          <h2 className="text-xl font-semibold mt-8">Notification Preferences</h2>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-[hsl(var(--muted-foreground))]" />
            </div>
          ) : prefs ? (
            <div className="space-y-4">
              {/* Email Card */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <Mail className="h-5 w-5" />
                      Email Notifications
                    </CardTitle>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <span className="text-sm text-[hsl(var(--muted-foreground))]">
                        {prefs.email_enabled ? 'Enabled' : 'Disabled'}
                      </span>
                      <input
                        type="checkbox"
                        checked={prefs.email_enabled}
                        onChange={e => handleToggle('email', e.target.checked)}
                        className="h-4 w-4 rounded border-gray-300"
                      />
                    </label>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {(prefs.available_email_events || []).map(event => (
                      <label key={event} className="flex items-center gap-3 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={prefs.email_events.includes(event)}
                          onChange={e => handleEventToggle('email', event, e.target.checked)}
                          disabled={!prefs.email_enabled}
                          className="h-4 w-4 rounded border-gray-300"
                        />
                        <span className={!prefs.email_enabled ? 'text-[hsl(var(--muted-foreground))]' : ''}>
                          {EVENT_LABELS[event] || event}
                        </span>
                      </label>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Button onClick={handleSave} disabled={saving}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                Save Preferences
              </Button>
            </div>
          ) : null}
        </>
      )}
    </div>
  )
}
